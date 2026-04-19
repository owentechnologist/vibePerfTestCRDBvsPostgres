#!/usr/bin/env python3
"""
CockroachDB Cluster Deployment Automation

This script automates the provisioning of CockroachDB Advanced clusters in Azure
using the CockroachDB Cloud CLI (ccloud). It supports:
- YAML-based configuration
- Automated cluster creation and status monitoring
- Connection string extraction
- Optional auto-cleanup after benchmarking
- Integration with benchmark.py

Usage:
    # Deploy cluster
    python deploy_crdb.py --config cluster_config.yaml

    # Deploy with auto-cleanup
    python deploy_crdb.py --config cluster_config.yaml --auto-cleanup

    # Cleanup existing cluster
    python deploy_crdb.py --cleanup --cluster-id <cluster-id>

    # Deploy and run benchmark
    python deploy_crdb.py --config cluster_config.yaml --run-benchmark \\
        --pg-connection "postgresql://..."

Requirements:
    - ccloud CLI installed and in PATH
    - Authenticated with CockroachDB Cloud (run: ccloud auth login)
    - PyYAML (pip install pyyaml)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import secrets
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)


class CockroachDBDeployer:
    """Manages CockroachDB cluster deployment via ccloud CLI."""

    def __init__(self, config_path: str):
        """
        Initialize deployer.

        Args:
            config_path: Path to cluster_config.yaml
        """
        self.config = self._load_config(config_path)
        self.cluster_id: Optional[str] = None
        self.cluster_info: Dict = {}

    def _load_config(self, config_path: str) -> Dict:
        """Load and validate YAML configuration."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Validate required fields
            if 'cockroachdb' not in config:
                raise ValueError("Configuration must have 'cockroachdb' section")

            crdb_config = config['cockroachdb']
            required_fields = ['cluster_name', 'cloud_provider', 'plan', 'nodes', 'regions', 'database']
            for field in required_fields:
                if field not in crdb_config:
                    raise ValueError(f"Missing required field: {field}")

            print(f"✅ Loaded configuration from {config_path}")
            return config

        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML syntax: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)


    def _run_ccloud_command(self, args: list, check: bool = True) -> Tuple[int, str, str]:
        """
        Run a ccloud CLI command.

        Args:
            args: Command arguments (without 'ccloud' prefix)
            check: Whether to raise on non-zero exit code

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        cmd = ['ccloud'] + args
        result = subprocess.run(cmd, capture_output=True, text=True)

        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"   Error: {result.stderr}")
            raise RuntimeError(f"ccloud command failed: {result.stderr}")

        return result.returncode, result.stdout, result.stderr

    def check_ccloud_installed(self) -> bool:
        """Check if ccloud CLI is installed and accessible."""
        try:
            returncode, stdout, stderr = self._run_ccloud_command(['version'], check=False)
            if returncode == 0:
                version = stdout.strip()
                print(f"✅ ccloud CLI found: {version}")
                return True
            else:
                print("❌ ccloud CLI not found or not executable")
                print("\nInstall ccloud CLI:")
                print("   macOS:  brew install cockroachdb/tap/ccloud")
                print("   Linux:  curl https://binaries.cockroachdb.com/ccloud/install.sh | bash")
                print("   Docs:   https://www.cockroachlabs.com/docs/cockroachcloud/install-ccloud")
                return False
        except FileNotFoundError:
            print("❌ ccloud CLI not found in PATH")
            print("\nInstall ccloud CLI:")
            print("   macOS:  brew install cockroachdb/tap/ccloud")
            print("   Linux:  curl https://binaries.cockroachdb.com/ccloud/install.sh | bash")
            return False

    def check_authentication(self) -> bool:
        """Check if user is authenticated with CockroachDB Cloud."""
        print("\n🔐 Checking CockroachDB Cloud authentication...")

        try:
            # Try to list clusters to verify authentication
            returncode, stdout, stderr = self._run_ccloud_command(
                ['cluster', 'list', '--output', 'json'],
                check=False
            )

            if returncode == 0:
                print("✅ Already authenticated with CockroachDB Cloud")
                return True
            else:
                print("❌ Not authenticated with CockroachDB Cloud")
                print("\nPlease authenticate using:")
                print("   ccloud auth login")
                print("\nThis will open a browser window for interactive authentication.")
                return False

        except RuntimeError:
            print("❌ Authentication check failed")
            print("\nPlease authenticate using:")
            print("   ccloud auth login")
            return False

    def cluster_exists(self, cluster_name: str) -> Optional[str]:
        """
        Check if a cluster with the given name already exists.

        Returns:
            Cluster ID if exists, None otherwise
        """
        try:
            returncode, stdout, stderr = self._run_ccloud_command(
                ['cluster', 'list', '--output', 'json'],
                check=False
            )

            if returncode == 0:
                clusters = json.loads(stdout)
                for cluster in clusters:
                    if cluster.get('name') == cluster_name:
                        return cluster.get('id')
            return None

        except (json.JSONDecodeError, RuntimeError):
            return None

    def create_cluster(self) -> str:
        """
        Create a new CockroachDB cluster.

        Returns:
            Cluster ID
        """
        cfg = self.config['cockroachdb']
        cluster_name = cfg['cluster_name']

        # Check if cluster already exists
        existing_id = self.cluster_exists(cluster_name)
        if existing_id:
            print(f"⚠️  Cluster '{cluster_name}' already exists (ID: {existing_id})")
            user_input = input("Use existing cluster? [y/N]: ").strip().lower()
            if user_input == 'y':
                self.cluster_id = existing_id
                return existing_id
            else:
                print("Please use a different cluster_name in your config or delete the existing cluster.")
                sys.exit(1)

        plan = cfg['plan'].upper()
        cloud = cfg['cloud_provider'].upper()

        # Azure ADVANCED plan limitation check
        if cloud == 'AZURE' and plan == 'ADVANCED' and len(cfg['regions']) == 1:
            print("\n" + "=" * 70)
            print("❌ AZURE ADVANCED CLUSTER LIMITATION")
            print("=" * 70)
            print("\nThe ccloud CLI does not support creating ADVANCED (dedicated)")
            print("clusters on Azure with a single region containing 3 nodes.")
            print("\nAzure enforces a multi-region requirement for ADVANCED clusters")
            print("via the CLI API, which requires >1 node per region.")
            print("\nOPTIONS:")
            print("  1. Deploy via CockroachDB Cloud Web UI:")
            print("     https://cockroachlabs.cloud/")
            print("     (The web UI may allow single-region configurations)")
            print("\n  2. Use a multi-region configuration:")
            print("     - 2 regions with 2 nodes each (4 nodes total)")
            print("     - Update cluster_config.yaml to add a second region")
            print("\n  3. Use GCP or AWS instead of Azure:")
            print("     - Change cloud_provider to 'gcp' or 'aws'")
            print("     - Use plan 'STANDARD' for single region with 3 nodes")
            print("=" * 70)
            sys.exit(1)

        print(f"\n🚀 Creating cluster '{cluster_name}'...")
        print(f"   Cloud: {cfg['cloud_provider']}")
        print(f"   Plan: {plan}")
        print(f"   Regions: {', '.join(cfg['regions'])}")

        # Build cluster create command based on plan type
        # ADVANCED plan requires regions in format "region:node_count"
        # STANDARD/BASIC plan uses simple region names
        if plan == 'ADVANCED':
            # For ADVANCED, calculate nodes per region
            num_regions = len(cfg['regions'])
            nodes_per_region = cfg['nodes'].get('nodes_per_region', 1)
            region_args = [f"{region}:{nodes_per_region}" for region in cfg['regions']]
        else:
            region_args = cfg['regions']

        cmd_args = [
            'cluster', 'create', cluster_name,
        ] + region_args + [
            '--cloud', cfg['cloud_provider'].upper(),
            '--plan', plan,
            '--output', 'json'
        ]

        if plan == 'STANDARD':
            # STANDARD plan: provisioned capacity for entire cluster
            provisioned_vcpus = cfg['nodes'].get('provisioned_vcpus', 24)

            print(f"   Provisioned vCPUs: {provisioned_vcpus} (total)")

            cmd_args.extend([
                '--provisioned-vcpus', str(provisioned_vcpus)
            ])

            # Add primary region if specified
            if 'primary_region' in cfg:
                cmd_args.extend(['--primary-region', cfg['primary_region']])

        elif plan == 'ADVANCED':
            # ADVANCED plan: per-node configuration
            vcpus = cfg['nodes'].get('vcpus', 8)
            storage = cfg['nodes'].get('storage_gib', 500)

            print(f"   vCPUs per node: {vcpus}")
            print(f"   Storage per node: {storage} GiB")

            cmd_args.extend([
                '--vcpus', str(vcpus),
                '--storage-gib', str(storage)
            ])

            # Add optional version specification for ADVANCED
            if 'options' in cfg and cfg['options'].get('version') and cfg['options']['version'] != 'latest':
                cmd_args.extend(['--version', cfg['options']['version']])

        else:
            # BASIC plan support (if needed)
            print(f"   Note: BASIC plan uses default settings")

        try:
            returncode, stdout, stderr = self._run_ccloud_command(cmd_args)

            # Parse cluster ID from output
            cluster_info = json.loads(stdout)
            self.cluster_id = cluster_info.get('id')
            self.cluster_info = cluster_info

            print(f"✅ Cluster creation initiated")
            print(f"   Cluster ID: {self.cluster_id}")
            print(f"   Status: Creating...")

            return self.cluster_id

        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ Failed to parse cluster creation response: {e}")
            sys.exit(1)

    def wait_for_ready(self, timeout: int = 900) -> bool:
        """
        Wait for cluster to reach READY state.

        Args:
            timeout: Maximum wait time in seconds (default: 15 minutes)

        Returns:
            True if cluster is ready, raises TimeoutError otherwise
        """
        if not self.cluster_id:
            raise ValueError("No cluster ID set. Create cluster first.")

        print(f"\n⏳ Waiting for cluster to be ready (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                returncode, stdout, stderr = self._run_ccloud_command(
                    ['cluster', 'status', self.cluster_id, '--output', 'json'],
                    check=False
                )

                if returncode == 0:
                    status_info = json.loads(stdout)
                    state = status_info.get('state', 'UNKNOWN')
                    elapsed = int(time.time() - start_time)

                    if state == 'READY':
                        print(f"✅ Cluster is ready! (elapsed: {elapsed}s)")
                        return True
                    elif state in ['CREATING', 'SCALING', 'STARTING']:
                        print(f"   Status: {state}... (elapsed: {elapsed}s)")
                    else:
                        print(f"⚠️  Unexpected cluster state: {state}")

            except (json.JSONDecodeError, RuntimeError) as e:
                print(f"   Warning: Failed to check status: {e}")

            # Wait 10 seconds before next check
            time.sleep(10)

        # Timeout reached
        elapsed = int(time.time() - start_time)
        print(f"❌ Cluster creation timed out after {elapsed}s")
        raise TimeoutError(f"Cluster creation exceeded {timeout}s timeout")

    def get_connection_string(self, output_file: Optional[str] = None) -> str:
        """
        Get PostgreSQL connection string for the cluster.

        Args:
            output_file: Optional file path to save connection string

        Returns:
            Connection string
        """
        if not self.cluster_id:
            raise ValueError("No cluster ID set. Create cluster first.")

        cfg = self.config['cockroachdb']
        db_name = cfg['database']['name']
        user = cfg['database']['sql_user']

        print(f"\n🔗 Retrieving connection string...")
        print(f"   Database: {db_name}")
        print(f"   User: {user}")

        # Note: The actual ccloud command for connection strings may vary
        # This is a placeholder implementation
        # You may need to adjust based on actual ccloud CLI behavior
        try:
            returncode, stdout, stderr = self._run_ccloud_command(
                ['cluster', 'connection-string', self.cluster_id,
                 '--database', db_name, '--user', user],
                check=False
            )

            if returncode == 0:
                conn_string = stdout.strip()
                print(f"✅ Connection string retrieved")

                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(conn_string)
                    print(f"   Saved to: {output_file}")

                return conn_string
            else:
                print("⚠️  Standard connection string command failed, using manual construction")
                # Fallback: construct connection string manually
                # Format: postgresql://user:password@host:26257/database?sslmode=require
                # Note: You'll need to get the actual host from cluster info
                print("   Please retrieve connection string manually from CockroachDB Cloud Console")
                print(f"   Cluster ID: {self.cluster_id}")
                return ""

        except RuntimeError as e:
            print(f"❌ Failed to retrieve connection string: {e}")
            return ""

    def cleanup(self, cluster_id: Optional[str] = None) -> bool:
        """
        Delete the cluster.

        Args:
            cluster_id: Cluster ID to delete (uses self.cluster_id if not provided)

        Returns:
            True if successful
        """
        target_id = cluster_id or self.cluster_id

        if not target_id:
            print("❌ No cluster ID provided for cleanup")
            return False

        print(f"\n🗑️  Deleting cluster {target_id}...")

        try:
            self._run_ccloud_command(
                ['cluster', 'delete', target_id, '--yes']
            )
            print(f"✅ Cluster {target_id} deleted successfully")
            return True

        except RuntimeError as e:
            print(f"❌ Failed to delete cluster: {e}")
            return False

    def display_cluster_info(self) -> None:
        """Display summary of created cluster."""
        if not self.cluster_id:
            print("No cluster information available")
            return

        cfg = self.config['cockroachdb']
        plan = cfg['plan'].upper()

        print("\n" + "=" * 70)
        print("CLUSTER INFORMATION")
        print("=" * 70)
        print(f"Cluster Name:    {cfg['cluster_name']}")
        print(f"Cluster ID:      {self.cluster_id}")
        print(f"Cloud Provider:  {cfg['cloud_provider']}")
        print(f"Plan:            {plan}")
        print(f"Region(s):       {', '.join(cfg['regions'])}")

        if plan == 'STANDARD':
            print(f"Provisioned:     {cfg['nodes'].get('provisioned_vcpus', 24)} vCPUs total")
            print(f"Storage Limit:   {cfg['nodes'].get('storage_gib_limit', 1500)} GiB total")
        elif plan == 'ADVANCED':
            print(f"vCPUs/Node:      {cfg['nodes'].get('vcpus', 8)}")
            print(f"Storage/Node:    {cfg['nodes'].get('storage_gib', 500)} GiB")

        print(f"Database:        {cfg['database']['name']}")
        print(f"SQL User:        {cfg['database']['sql_user']}")
        print("=" * 70)
        print("\n💡 Next steps:")
        print("   1. Wait for cluster to be fully ready")
        print("   2. Use the connection string with benchmark.py")
        print("   3. Run: python benchmark.py --crdb $(cat crdb_connection.txt) --pg <azure-pg-conn>")
        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy CockroachDB Advanced cluster for performance benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Deploy cluster
  %(prog)s --config cluster_config.yaml

  # Deploy with auto-cleanup after benchmark
  %(prog)s --config cluster_config.yaml --auto-cleanup

  # Deploy and run benchmark automatically
  %(prog)s --config cluster_config.yaml --run-benchmark \\
      --pg-connection "postgresql://user:pass@host:5432/db"

  # Cleanup existing cluster
  %(prog)s --cleanup --cluster-id abc-123-def
        '''
    )

    # Deployment arguments
    parser.add_argument('--config', type=str, default='cluster_config.yaml',
                        help='Path to cluster configuration YAML file (default: cluster_config.yaml)')
    parser.add_argument('--output-connection', type=str, default='crdb_connection.txt',
                        help='File to save connection string (default: crdb_connection.txt)')

    # Cleanup arguments
    parser.add_argument('--cleanup', action='store_true',
                        help='Delete cluster instead of creating')
    parser.add_argument('--cluster-id', type=str,
                        help='Cluster ID for cleanup operation')

    # Integration arguments
    parser.add_argument('--auto-cleanup', action='store_true',
                        help='Automatically delete cluster after benchmark completes')
    parser.add_argument('--run-benchmark', action='store_true',
                        help='Automatically run benchmark.py after cluster is ready')
    parser.add_argument('--pg-connection', type=str,
                        help='Azure PostgreSQL connection string (required with --run-benchmark)')

    # General arguments
    parser.add_argument('--timeout', type=int, default=900,
                        help='Cluster creation timeout in seconds (default: 900)')

    args = parser.parse_args()

    # Handle cleanup mode
    if args.cleanup:
        if not args.cluster_id:
            print("❌ --cluster-id required for cleanup operation")
            sys.exit(1)

        deployer = CockroachDBDeployer(args.config if os.path.exists(args.config) else 'cluster_config.yaml')
        if deployer.check_ccloud_installed() and deployer.check_authentication():
            deployer.cleanup(args.cluster_id)
        else:
            sys.exit(1)
        sys.exit(0)

    # Normal deployment flow
    print("=" * 70)
    print("CockroachDB Cluster Deployment")
    print("=" * 70)

    # Initialize deployer
    deployer = CockroachDBDeployer(args.config)

    # Check prerequisites
    if not deployer.check_ccloud_installed():
        sys.exit(1)

    # Check authentication
    if not deployer.check_authentication():
        sys.exit(1)

    # Create cluster
    try:
        cluster_id = deployer.create_cluster()

        # Wait for ready
        deployer.wait_for_ready(timeout=args.timeout)

        # Get connection string
        conn_string = deployer.get_connection_string(output_file=args.output_connection)

        # Display cluster info
        deployer.display_cluster_info()

        # Run benchmark if requested
        if args.run_benchmark:
            if not args.pg_connection:
                print("❌ --pg-connection required with --run-benchmark")
                sys.exit(1)

            print("\n🏃 Running benchmark...")
            benchmark_cmd = [
                'python', 'benchmark.py',
                '--crdb', conn_string,
                '--pg', args.pg_connection,
                '--output-dir', './outputs'
            ]

            result = subprocess.run(benchmark_cmd)

            if result.returncode != 0:
                print("⚠️  Benchmark failed or was interrupted")

        # Auto-cleanup if requested
        if args.auto_cleanup:
            print("\n⏰ Auto-cleanup enabled, deleting cluster...")
            deployer.cleanup()
        else:
            print(f"\n💰 Remember to delete cluster when done to avoid charges:")
            print(f"   python {sys.argv[0]} --cleanup --cluster-id {cluster_id}")

    except (KeyboardInterrupt, SystemExit):
        print("\n⚠️  Operation interrupted by user")
        if args.auto_cleanup and deployer.cluster_id:
            print("Cleaning up cluster due to auto-cleanup flag...")
            deployer.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        if args.auto_cleanup and deployer.cluster_id:
            print("Cleaning up cluster due to failure with auto-cleanup flag...")
            deployer.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()

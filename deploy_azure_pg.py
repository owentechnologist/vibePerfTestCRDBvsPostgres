#!/usr/bin/env python3
"""
Azure PostgreSQL Flexible Server Deployment Automation

This script automates the provisioning of Azure PostgreSQL Flexible Server
using the Azure CLI (az). It supports:
- YAML-based configuration
- Automated server creation and status monitoring
- Zone-redundant high availability
- Connection string generation
- Optional auto-cleanup after benchmarking
- Integration with benchmark.py

Usage:
    # Deploy server
    python deploy_azure_pg.py --config azure_pg_config.yaml

    # Deploy with auto-cleanup
    python deploy_azure_pg.py --config azure_pg_config.yaml --auto-cleanup

    # Cleanup existing server
    python deploy_azure_pg.py --cleanup --resource-group <rg-name> --server-name <server-name>

    # Deploy and run benchmark
    python deploy_azure_pg.py --config azure_pg_config.yaml --run-benchmark \\
        --crdb-connection "postgresql://..."

Requirements:
    - Azure CLI installed and in PATH
    - Authenticated with Azure (run: az login)
    - PyYAML (pip install pyyaml)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import secrets
import string
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)


class AzurePostgreSQLDeployer:
    """Manages Azure PostgreSQL Flexible Server deployment via az CLI."""

    def __init__(self, config_path: str):
        """
        Initialize deployer.

        Args:
            config_path: Path to azure_pg_config.yaml
        """
        self.config = self._load_config(config_path)
        self.server_name: Optional[str] = None
        self.resource_group: Optional[str] = None
        self.admin_password: Optional[str] = None
        self.server_info: Dict = {}

    def _load_config(self, config_path: str) -> Dict:
        """Load and validate YAML configuration."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Validate required fields
            if 'azure_postgresql' not in config:
                raise ValueError("Configuration must have 'azure_postgresql' section")

            pg_config = config['azure_postgresql']
            # resource_group is optional - will be prompted for if not specified
            required_fields = ['location', 'server_name', 'version', 'sku', 'admin', 'database']
            for field in required_fields:
                if field not in pg_config:
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

    def _run_az_command(self, args: list, check: bool = True) -> Tuple[int, str, str]:
        """
        Run an Azure CLI command.

        Args:
            args: Command arguments (without 'az' prefix)
            check: Whether to raise on non-zero exit code

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        cmd = ['az'] + args
        result = subprocess.run(cmd, capture_output=True, text=True)

        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"   Error: {result.stderr}")
            raise RuntimeError(f"Azure CLI command failed: {result.stderr}")

        return result.returncode, result.stdout, result.stderr

    def check_az_installed(self) -> bool:
        """Check if Azure CLI is installed and accessible."""
        try:
            returncode, stdout, stderr = self._run_az_command(['version'], check=False)
            if returncode == 0:
                version_info = json.loads(stdout)
                version = version_info.get('azure-cli', 'unknown')
                print(f"✅ Azure CLI found: {version}")
                return True
            else:
                print("❌ Azure CLI not found or not executable")
                print("\nInstall Azure CLI:")
                print("   macOS:  brew install azure-cli")
                print("   Linux:  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
                print("   Windows: https://aka.ms/installazurecliwindows")
                print("   Docs:   https://docs.microsoft.com/cli/azure/install-azure-cli")
                return False
        except (FileNotFoundError, json.JSONDecodeError):
            print("❌ Azure CLI not found in PATH")
            print("\nInstall Azure CLI:")
            print("   macOS:  brew install azure-cli")
            print("   Linux:  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
            return False

    def check_authentication(self) -> bool:
        """Check if user is authenticated with Azure."""
        print("\n🔐 Checking Azure authentication...")

        try:
            # Try to get account info to verify authentication
            returncode, stdout, stderr = self._run_az_command(
                ['account', 'show'],
                check=False
            )

            if returncode == 0:
                account_info = json.loads(stdout)
                print(f"✅ Authenticated with Azure")
                print(f"   Account: {account_info.get('user', {}).get('name', 'unknown')}")
                print(f"   Subscription: {account_info.get('name', 'unknown')}")
                return True
            else:
                print("❌ Not authenticated with Azure")
                print("\nPlease authenticate using:")
                print("   az login")
                print("\nThis will open a browser window for interactive authentication.")
                return False

        except (RuntimeError, json.JSONDecodeError):
            print("❌ Authentication check failed")
            print("\nPlease authenticate using:")
            print("   az login")
            return False

    def _generate_password(self) -> str:
        """Generate a secure random password for PostgreSQL admin user."""
        # PostgreSQL password requirements:
        # - At least 8 characters
        # - Contains uppercase, lowercase, numbers, and special chars
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(16))
            # Ensure it has at least one of each required character type
            if (any(c.islower() for c in password) and
                any(c.isupper() for c in password) and
                any(c.isdigit() for c in password) and
                any(c in "!@#$%^&*()-_=+" for c in password)):
                return password

    def prompt_for_resource_group(self) -> str:
        """
        Prompt user for resource group name if not specified in config.

        Returns:
            Resource group name
        """
        cfg = self.config['azure_postgresql']

        # If already specified in config, use it
        if 'resource_group' in cfg and cfg['resource_group']:
            rg_name = cfg['resource_group']
            print(f"📦 Using resource group from config: {rg_name}")
            return rg_name

        # Otherwise, prompt the user
        default_rg = "austin-se-ot"
        user_input = input(f"📦 Enter resource group name [{default_rg}]: ").strip()

        rg_name = user_input if user_input else default_rg

        # Store it in config for later use
        cfg['resource_group'] = rg_name
        print(f"   Using resource group: {rg_name}")

        return rg_name

    def resource_group_exists(self, rg_name: str) -> bool:
        """
        Check if a resource group exists.

        Returns:
            True if exists, False otherwise
        """
        try:
            returncode, stdout, stderr = self._run_az_command(
                ['group', 'exists', '--name', rg_name],
                check=False
            )
            return returncode == 0 and stdout.strip().lower() == 'true'
        except RuntimeError:
            return False

    def server_exists(self, rg_name: str, server_name: str) -> bool:
        """
        Check if a PostgreSQL server exists.

        Returns:
            True if exists, False otherwise
        """
        try:
            returncode, stdout, stderr = self._run_az_command(
                ['postgres', 'flexible-server', 'show',
                 '--resource-group', rg_name,
                 '--name', server_name],
                check=False
            )
            return returncode == 0
        except RuntimeError:
            return False

    def create_resource_group(self) -> bool:
        """Create Azure resource group if it doesn't exist."""
        cfg = self.config['azure_postgresql']
        rg_name = cfg['resource_group']
        location = cfg['location']

        if self.resource_group_exists(rg_name):
            print(f"✅ Resource group '{rg_name}' already exists")
            return True

        print(f"\n📦 Creating resource group '{rg_name}'...")
        print(f"   Location: {location}")

        try:
            self._run_az_command([
                'group', 'create',
                '--name', rg_name,
                '--location', location
            ])
            print(f"✅ Resource group created")
            return True
        except RuntimeError as e:
            print(f"❌ Failed to create resource group: {e}")
            return False

    def create_server(self) -> str:
        """
        Create a new PostgreSQL Flexible Server.

        Returns:
            Server name
        """
        cfg = self.config['azure_postgresql']
        self.resource_group = cfg['resource_group']
        self.server_name = cfg['server_name']

        # Check if server already exists
        if self.server_exists(self.resource_group, self.server_name):
            print(f"⚠️  Server '{self.server_name}' already exists")
            user_input = input("Use existing server? [y/N]: ").strip().lower()
            if user_input == 'y':
                return self.server_name
            else:
                print("Please use a different server_name in your config or delete the existing server.")
                sys.exit(1)

        # Generate or get admin password
        self.admin_password = os.environ.get('AZURE_PG_PASSWORD')
        if not self.admin_password:
            self.admin_password = self._generate_password()
            print(f"\n🔑 Generated admin password (save this!):")
            print(f"   Password will be saved to azure_pg_password.txt")
        else:
            print(f"\n🔑 Using password from AZURE_PG_PASSWORD environment variable")

        print(f"\n🚀 Creating PostgreSQL Flexible Server '{self.server_name}'...")
        print(f"   Resource Group: {self.resource_group}")
        print(f"   Location: {cfg['location']}")
        print(f"   SKU: {cfg['sku']['name']} ({cfg['sku']['tier']})")
        print(f"   PostgreSQL Version: {cfg['version']}")
        print(f"   Storage: {cfg['storage']['size_gb']} GB")

        # Build create command
        cmd_args = [
            'postgres', 'flexible-server', 'create',
            '--resource-group', self.resource_group,
            '--name', self.server_name,
            '--location', cfg['location'],
            '--admin-user', cfg['admin']['username'],
            '--admin-password', self.admin_password,
            '--sku-name', cfg['sku']['name'],
            '--tier', cfg['sku']['tier'],
            '--version', str(cfg['version']),
            '--storage-size', str(cfg['storage']['size_gb']),
            '--public-access', cfg['network']['public_access']
        ]

        # Add high availability if configured
        ha_config = cfg.get('high_availability', {})
        if ha_config.get('mode') and ha_config['mode'] != 'Disabled':
            cmd_args.extend([
                '--high-availability', ha_config['mode'],
                '--zone', str(ha_config.get('zone', 1)),
                '--standby-zone', str(ha_config.get('standby_zone', 2))
            ])
            print(f"   High Availability: {ha_config['mode']}")
            print(f"   Primary Zone: {ha_config.get('zone', 1)}")
            print(f"   Standby Zone: {ha_config.get('standby_zone', 2)}")

        # Add backup configuration if specified
        backup_config = cfg.get('backup', {})
        if backup_config.get('retention_days'):
            cmd_args.extend(['--backup-retention', str(backup_config['retention_days'])])
        if backup_config.get('geo_redundant'):
            cmd_args.extend(['--geo-redundant-backup', backup_config['geo_redundant']])

        try:
            print("\n   Creating server (this may take 10-15 minutes)...")
            returncode, stdout, stderr = self._run_az_command(cmd_args)

            # Parse server info from output
            self.server_info = json.loads(stdout)

            print(f"✅ Server creation completed")
            print(f"   Server: {self.server_name}")
            print(f"   Status: {self.server_info.get('state', 'Unknown')}")

            # Save password to file
            self._save_password()

            return self.server_name

        except (json.JSONDecodeError, RuntimeError) as e:
            print(f"❌ Failed to create server: {e}")
            sys.exit(1)

    def _save_password(self):
        """Save admin password to file with secure permissions."""
        password_file = Path('azure_pg_password.txt')
        try:
            with open(password_file, 'w') as f:
                f.write(self.admin_password)
            os.chmod(password_file, 0o600)
            print(f"\n   💾 Password saved to: {password_file}")
            print(f"   Permissions: 600 (read/write for owner only)")
        except Exception as e:
            print(f"⚠️  Could not save password to file: {e}")
            print(f"   Password: {self.admin_password}")

    def create_database(self) -> bool:
        """Create the benchmark database."""
        cfg = self.config['azure_postgresql']
        db_config = cfg['database']
        db_name = db_config['name']

        print(f"\n📚 Creating database '{db_name}'...")

        try:
            self._run_az_command([
                'postgres', 'flexible-server', 'db', 'create',
                '--resource-group', self.resource_group,
                '--server-name', self.server_name,
                '--database-name', db_name
            ])
            print(f"✅ Database '{db_name}' created")
            return True
        except RuntimeError as e:
            # Check if database already exists
            if 'already exists' in str(e).lower():
                print(f"✅ Database '{db_name}' already exists")
                return True
            print(f"❌ Failed to create database: {e}")
            return False

    def configure_server_parameters(self) -> bool:
        """Configure PostgreSQL server parameters for performance."""
        cfg = self.config['azure_postgresql']
        params = cfg.get('parameters', {})

        if not params:
            print("\n⚙️  No custom parameters to configure")
            return True

        print(f"\n⚙️  Configuring server parameters...")

        success = True
        for param_name, param_value in params.items():
            # Convert parameter name to Azure format (snake_case to kebab-case for some params)
            # Most params work as-is, but some need adjustment
            azure_param_name = param_name

            # Convert MB/KB suffixes to actual parameter names
            if param_name.endswith('_mb'):
                base_name = param_name[:-3]
                azure_param_name = base_name
                # Convert MB to appropriate unit (some params use KB, some use MB, some use 8KB blocks)
                if base_name in ['shared_buffers', 'wal_buffers']:
                    # These use 8KB blocks
                    param_value = int(param_value) * 128  # MB to 8KB blocks
                elif base_name in ['effective_cache_size', 'maintenance_work_mem']:
                    # These use KB
                    param_value = int(param_value) * 1024  # MB to KB
            elif param_name.endswith('_kb'):
                base_name = param_name[:-3]
                azure_param_name = base_name
                # work_mem uses KB

            try:
                self._run_az_command([
                    'postgres', 'flexible-server', 'parameter', 'set',
                    '--resource-group', self.resource_group,
                    '--server-name', self.server_name,
                    '--name', azure_param_name,
                    '--value', str(param_value)
                ])
                print(f"   ✓ {azure_param_name} = {param_value}")
            except RuntimeError as e:
                print(f"   ✗ Failed to set {azure_param_name}: {e}")
                success = False

        if success:
            print(f"✅ Server parameters configured")
        return success

    def get_connection_string(self, output_file: Optional[str] = None) -> str:
        """
        Get PostgreSQL connection string for the server.

        Args:
            output_file: Optional file path to save connection string

        Returns:
            Connection string
        """
        if not self.server_name or not self.resource_group:
            raise ValueError("Server not created yet")

        cfg = self.config['azure_postgresql']
        db_name = cfg['database']['name']
        admin_user = cfg['admin']['username']

        print(f"\n🔗 Generating connection string...")

        try:
            # Get server FQDN
            returncode, stdout, stderr = self._run_az_command([
                'postgres', 'flexible-server', 'show',
                '--resource-group', self.resource_group,
                '--name', self.server_name,
                '--output', 'json'
            ])

            server_info = json.loads(stdout)
            fqdn = server_info.get('fullyQualifiedDomainName')

            if not fqdn:
                raise ValueError("Could not get server FQDN")

            # Construct connection string
            conn_string = (
                f"postgresql://{admin_user}:{self.admin_password}@"
                f"{fqdn}:5432/{db_name}?sslmode=require"
            )

            print(f"✅ Connection string generated")
            print(f"   Host: {fqdn}")
            print(f"   Database: {db_name}")
            print(f"   User: {admin_user}")

            if output_file:
                with open(output_file, 'w') as f:
                    f.write(conn_string)
                os.chmod(output_file, 0o600)
                print(f"   Saved to: {output_file} (permissions: 600)")

            return conn_string

        except (RuntimeError, json.JSONDecodeError, ValueError) as e:
            print(f"❌ Failed to generate connection string: {e}")
            return ""

    def cleanup(self, resource_group: Optional[str] = None, server_name: Optional[str] = None) -> bool:
        """
        Delete the PostgreSQL server.

        Args:
            resource_group: Resource group name (uses self.resource_group if not provided)
            server_name: Server name (uses self.server_name if not provided)

        Returns:
            True if successful
        """
        rg = resource_group or self.resource_group
        srv = server_name or self.server_name

        if not rg or not srv:
            print("❌ No resource group or server name provided for cleanup")
            return False

        print(f"\n🗑️  Deleting server '{srv}' in resource group '{rg}'...")

        try:
            self._run_az_command([
                'postgres', 'flexible-server', 'delete',
                '--resource-group', rg,
                '--name', srv,
                '--yes'
            ])
            print(f"✅ Server '{srv}' deleted successfully")
            return True

        except RuntimeError as e:
            print(f"❌ Failed to delete server: {e}")
            return False

    def display_server_info(self) -> None:
        """Display summary of created server."""
        if not self.server_name:
            print("No server information available")
            return

        cfg = self.config['azure_postgresql']
        ha_config = cfg.get('high_availability', {})

        print("\n" + "=" * 70)
        print("SERVER INFORMATION")
        print("=" * 70)
        print(f"Server Name:     {self.server_name}")
        print(f"Resource Group:  {self.resource_group}")
        print(f"Location:        {cfg['location']}")
        print(f"SKU:             {cfg['sku']['name']} ({cfg['sku']['tier']})")
        print(f"vCPUs:           {cfg['sku']['name'].split('_')[1][1]}")  # Extract vCPU count
        print(f"PostgreSQL:      {cfg['version']}")
        print(f"Storage:         {cfg['storage']['size_gb']} GB")

        if ha_config.get('mode') and ha_config['mode'] != 'Disabled':
            print(f"High Availability: {ha_config['mode']}")
            print(f"Primary Zone:    {ha_config.get('zone', 1)}")
            print(f"Standby Zone:    {ha_config.get('standby_zone', 2)}")

        print(f"Database:        {cfg['database']['name']}")
        print(f"Admin User:      {cfg['admin']['username']}")
        print("=" * 70)
        print("\n💡 Next steps:")
        print("   1. Connection string saved to azure_pg_connection.txt")
        print("   2. Use with benchmark.py:")
        print("   3. python benchmark.py --crdb <crdb-conn> --pg $(cat azure_pg_connection.txt)")
        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy Azure PostgreSQL Flexible Server for performance benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Deploy server
  %(prog)s --config azure_pg_config.yaml

  # Deploy with auto-cleanup after benchmark
  %(prog)s --config azure_pg_config.yaml --auto-cleanup

  # Deploy and run benchmark automatically
  %(prog)s --config azure_pg_config.yaml --run-benchmark \\
      --crdb-connection "postgresql://user:pass@host:26257/db"

  # Cleanup existing server
  %(prog)s --cleanup --resource-group perftest-rg-2026q2 --server-name perftest-pg-2026q2
        '''
    )

    # Deployment arguments
    parser.add_argument('--config', type=str, default='azure_pg_config.yaml',
                        help='Path to server configuration YAML file (default: azure_pg_config.yaml)')
    parser.add_argument('--output-connection', type=str, default='azure_pg_connection.txt',
                        help='File to save connection string (default: azure_pg_connection.txt)')

    # Cleanup arguments
    parser.add_argument('--cleanup', action='store_true',
                        help='Delete server instead of creating')
    parser.add_argument('--resource-group', type=str,
                        help='Resource group name for cleanup operation')
    parser.add_argument('--server-name', type=str,
                        help='Server name for cleanup operation')

    # Integration arguments
    parser.add_argument('--auto-cleanup', action='store_true',
                        help='Automatically delete server after benchmark completes')
    parser.add_argument('--run-benchmark', action='store_true',
                        help='Automatically run benchmark.py after server is ready')
    parser.add_argument('--crdb-connection', type=str,
                        help='CockroachDB connection string (required with --run-benchmark)')

    args = parser.parse_args()

    # Handle cleanup mode
    if args.cleanup:
        if not args.resource_group or not args.server_name:
            print("❌ --resource-group and --server-name required for cleanup operation")
            sys.exit(1)

        deployer = AzurePostgreSQLDeployer(args.config if os.path.exists(args.config) else 'azure_pg_config.yaml')
        if deployer.check_az_installed() and deployer.check_authentication():
            deployer.cleanup(args.resource_group, args.server_name)
        else:
            sys.exit(1)
        sys.exit(0)

    # Normal deployment flow
    print("=" * 70)
    print("Azure PostgreSQL Flexible Server Deployment")
    print("=" * 70)

    # Initialize deployer
    deployer = AzurePostgreSQLDeployer(args.config)

    # Check prerequisites
    if not deployer.check_az_installed():
        sys.exit(1)

    # Check authentication
    if not deployer.check_authentication():
        sys.exit(1)

    # Prompt for resource group if not in config
    deployer.prompt_for_resource_group()

    # Create resources
    try:
        # Create resource group
        if not deployer.create_resource_group():
            sys.exit(1)

        # Create server
        server_name = deployer.create_server()

        # Create database
        if not deployer.create_database():
            sys.exit(1)

        # Configure parameters
        deployer.configure_server_parameters()

        # Get connection string
        conn_string = deployer.get_connection_string(output_file=args.output_connection)

        # Display server info
        deployer.display_server_info()

        # Run benchmark if requested
        if args.run_benchmark:
            if not args.crdb_connection:
                print("❌ --crdb-connection required with --run-benchmark")
                sys.exit(1)

            print("\n🏃 Running benchmark...")
            benchmark_cmd = [
                'python', 'benchmark.py',
                '--crdb', args.crdb_connection,
                '--pg', conn_string,
                '--output-dir', './outputs'
            ]

            result = subprocess.run(benchmark_cmd)

            if result.returncode != 0:
                print("⚠️  Benchmark failed or was interrupted")

        # Auto-cleanup if requested
        if args.auto_cleanup:
            print("\n⏰ Auto-cleanup enabled, deleting server...")
            deployer.cleanup()
        else:
            print(f"\n💰 Remember to delete server when done to avoid charges:")
            print(f"   python {sys.argv[0]} --cleanup --resource-group {deployer.resource_group} --server-name {server_name}")

    except (KeyboardInterrupt, SystemExit):
        print("\n⚠️  Operation interrupted by user")
        if args.auto_cleanup and deployer.server_name:
            print("Cleaning up server due to auto-cleanup flag...")
            deployer.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        if args.auto_cleanup and deployer.server_name:
            print("Cleaning up server due to failure with auto-cleanup flag...")
            deployer.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()

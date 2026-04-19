#!/usr/bin/env python3
"""
CockroachDB Cloud Connection String Generator

This script helps you get a properly formatted connection string for a
CockroachDB Cloud cluster deployed via the web UI. It uses the ccloud CLI
to generate a connection string with the correct CA certificate path for
your operating system.

Usage:
    python3 get_crdb_connection.py

The script will:
    1. List available clusters and capture cluster UUID
    2. Prompt for cluster name/ID, database, and username
    3. Download the CA certificate using the cluster UUID
    4. Use ccloud CLI to generate the connection string
    5. Update connection string to reference the downloaded certificate
    6. Prompt for the SQL user password
    7. Save the complete connection string to crdb_connection.txt
    8. Optionally validate the connection

Requirements:
    - ccloud CLI installed and authenticated (ccloud auth login)
    - Cluster deployed in CockroachDB Cloud
    - Database and SQL user created
    - curl command available for certificate download
"""

import argparse
import getpass
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


class CRDBConnectionHelper:
    """Helps generate and save CockroachDB Cloud connection strings."""

    def __init__(self):
        """Initialize the helper."""
        self.cluster_name = None
        self.cluster_uuid = None
        self.clusters_map = {}  # Maps cluster names to UUIDs
        self.database = None
        self.sql_user = None
        self.password = None
        self.connection_string = None

    def check_ccloud_installed(self) -> bool:
        """Check if ccloud CLI is installed and authenticated."""
        print("=" * 70)
        print("CHECKING CCLOUD CLI")
        print("=" * 70)

        # Check if ccloud is installed
        try:
            result = subprocess.run(
                ['ccloud', 'version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"✅ ccloud CLI found: {result.stdout.strip()}")
            else:
                print("❌ ccloud CLI not found or not executable")
                print("\nPlease install ccloud CLI:")
                print("  macOS:  brew install cockroachdb/tap/ccloud")
                print("  Linux:  curl https://binaries.cockroachdb.com/ccloud/install.sh | bash")
                return False
        except FileNotFoundError:
            print("❌ ccloud CLI not found in PATH")
            print("\nPlease install ccloud CLI:")
            print("  macOS:  brew install cockroachdb/tap/ccloud")
            print("  Linux:  curl https://binaries.cockroachdb.com/ccloud/install.sh | bash")
            return False

        # Check authentication
        print("\nChecking authentication...")
        try:
            result = subprocess.run(
                ['ccloud', 'auth', 'whoami'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"✅ Authenticated as: {result.stdout.strip()}")
                return True
            else:
                print("❌ Not authenticated with CockroachDB Cloud")
                print("\nPlease authenticate using:")
                print("  ccloud auth login")
                return False
        except Exception as e:
            print(f"❌ Failed to check authentication: {e}")
            return False

    def get_os_type(self) -> str:
        """Determine the OS type for ccloud connection-string command."""
        system = platform.system()
        if system == 'Darwin':
            return 'MAC'
        elif system == 'Linux':
            return 'LINUX'
        elif system == 'Windows':
            return 'WINDOWS'
        else:
            # Default to LINUX for unknown systems
            return 'LINUX'

    def download_ca_cert(self) -> bool:
        """Download the CA certificate for the cluster using its UUID."""
        if not self.cluster_uuid:
            print("⚠️  No cluster UUID available, skipping cert download.")
            return False

        print("\n" + "=" * 70)
        print("DOWNLOADING CA CERTIFICATE")
        print("=" * 70)

        # Determine cert path based on OS
        system = platform.system()
        if system == 'Darwin':
            base_path = Path.home() / "Library" / "CockroachCloud" / "certs"
        elif system == 'Linux':
            base_path = Path.home() / ".postgresql"
        elif system == 'Windows':
            base_path = Path.home() / "AppData" / "Roaming" / "postgresql"
        else:
            base_path = Path.home() / ".postgresql"

        # Create cert directory with UUID
        cert_dir = base_path / self.cluster_uuid
        cert_file = cert_dir / f"{self.cluster_name}-ca.crt"

        # Create directory if it doesn't exist
        cert_dir.mkdir(parents=True, exist_ok=True)
        # Set directory permissions (755 - standard for cert directories)
        cert_dir.chmod(0o755)

        # Download the cert
        download_url = f"https://cockroachlabs.cloud/clusters/{self.cluster_uuid}/cert"

        print(f"Downloading from: {download_url}")
        print(f"Saving to: {cert_file}")

        try:
            result = subprocess.run(
                ['curl', '--create-dirs', '-o', str(cert_file), download_url],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                # Verify the file was created and has content
                if cert_file.exists() and cert_file.stat().st_size > 0:
                    # Set appropriate permissions for CA certificate
                    # 644 is standard (owner read/write, others read)
                    cert_file.chmod(0o644)

                    print(f"✅ CA certificate downloaded successfully")
                    print(f"   Location: {cert_file}")
                    print(f"   Permissions: 644 (owner read/write, others read)")
                    return True
                else:
                    print("❌ Certificate file was not created or is empty")
                    return False
            else:
                print(f"❌ Failed to download certificate")
                print(f"Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error downloading certificate: {e}")
            return False

    def list_clusters(self):
        """List available clusters to help user choose."""
        print("\n" + "=" * 70)
        print("AVAILABLE CLUSTERS")
        print("=" * 70)

        try:
            result = subprocess.run(
                ['ccloud', 'cluster', 'list', '--output', 'json'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                clusters = json.loads(result.stdout)
                if clusters:
                    print("\nYour CockroachDB Cloud clusters:")
                    print(f"{'Name':<30} {'UUID':<40} {'State':<10}")
                    print("-" * 85)
                    for cluster in clusters:
                        name = cluster.get('name', 'N/A')
                        cluster_id = cluster.get('id', 'N/A')
                        state = cluster.get('state', 'N/A')
                        print(f"{name:<30} {cluster_id:<40} {state:<10}")
                        # Store the mapping for later use
                        if name != 'N/A' and cluster_id != 'N/A':
                            self.clusters_map[name] = cluster_id
                else:
                    print("No clusters found in your organization.")
            else:
                print("⚠️  Could not list clusters. You can still enter the cluster name manually.")

        except Exception as e:
            print(f"⚠️  Error listing clusters: {e}")

    def prompt_for_info(self):
        """Prompt user for cluster information."""
        print("\n" + "=" * 70)
        print("CLUSTER CONNECTION INFORMATION")
        print("=" * 70)

        # Cluster name/ID
        print("\nEnter your cluster name or ID from the list above.")
        print("Example: perftest-crdb-2026q2")
        self.cluster_name = input("Cluster name/ID: ").strip()
        if not self.cluster_name:
            print("❌ Cluster name is required")
            sys.exit(1)

        # Try to get UUID from the clusters map
        if self.cluster_name in self.clusters_map:
            self.cluster_uuid = self.clusters_map[self.cluster_name]
            print(f"✅ Found cluster UUID: {self.cluster_uuid}")
        else:
            # If user entered a UUID directly, use it
            if len(self.cluster_name) == 36 and '-' in self.cluster_name:
                self.cluster_uuid = self.cluster_name
                print(f"✅ Using provided UUID: {self.cluster_uuid}")
            else:
                print("⚠️  Could not find UUID for cluster. Will attempt connection without pre-downloading cert.")

        # Database name
        print("\nEnter the database name.")
        print("Example: perftest")
        self.database = input("Database name [perftest]: ").strip() or "perftest"

        # SQL user
        print("\nEnter the SQL username.")
        print("Example: perftest_user")
        self.sql_user = input("SQL username [perftest_user]: ").strip() or "perftest_user"

        print("\n✅ Information collected:")
        print(f"   Cluster: {self.cluster_name}")
        print(f"   Database: {self.database}")
        print(f"   User: {self.sql_user}")

        print("\n" + "=" * 70)
        print("IMPORTANT: Required Permissions")
        print("=" * 70)
        print(f"\nThe SQL user '{self.sql_user}' must have the following privileges:")
        print("  • CREATE - To create benchmark test tables")
        print("  • INSERT, SELECT, UPDATE, DELETE - For test data operations")
        print("  • DROP - To clean up test tables after benchmarking")
        print(f"\nIf database '{self.database}' doesn't exist:")
        print(f"  • User needs CREATEDB privilege, OR")
        print(f"  • Create the database manually before running validation")
        print("\nTo grant these permissions (run as admin in SQL console):")
        print(f"  GRANT CREATE ON DATABASE {self.database} TO {self.sql_user};")
        print(f"  -- Or for full admin access:")
        print(f"  GRANT admin TO {self.sql_user};")
        print("\nValidation script will verify these permissions automatically.")
        print("=" * 70)

    def get_connection_string_from_ccloud(self) -> bool:
        """Get connection string using ccloud CLI."""
        print("\n" + "=" * 70)
        print("GENERATING CONNECTION STRING")
        print("=" * 70)

        os_type = self.get_os_type()
        print(f"Detected OS: {os_type}")

        cmd = [
            'ccloud', 'cluster', 'connection-string', self.cluster_name,
            '--database', self.database,
            '--sql-user', self.sql_user,
            '--os', os_type
        ]

        print(f"\nRunning: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                # The output includes the connection string
                output = result.stdout.strip()
                # Extract the connection string (it may have extra output)
                lines = output.split('\n')
                # The connection string is usually the last line or contains postgresql://
                for line in reversed(lines):
                    if 'postgresql://' in line:
                        self.connection_string = line.strip()
                        break

                if self.connection_string:
                    print("✅ Connection string generated successfully")
                    # Show the string without password for review
                    parsed = urlparse(self.connection_string)
                    safe_string = self.connection_string.replace(parsed.password or '', '****')
                    print(f"\nConnection string template:")
                    print(f"  {safe_string}")
                    return True
                else:
                    print("❌ Could not extract connection string from output")
                    print(f"Output: {output}")
                    return False
            else:
                print(f"❌ Failed to generate connection string")
                print(f"Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error running ccloud command: {e}")
            return False

    def prompt_for_password(self):
        """Prompt for SQL user password."""
        print("\n" + "=" * 70)
        print("SQL USER PASSWORD")
        print("=" * 70)
        print(f"\nEnter the password for SQL user '{self.sql_user}'")
        print("(Password will not be displayed)")

        self.password = getpass.getpass("Password: ")
        if not self.password:
            print("❌ Password is required")
            sys.exit(1)

    def build_final_connection_string(self) -> str:
        """Build the final connection string with password and correct cert path."""
        # Parse the connection string
        parsed = urlparse(self.connection_string)

        # Rebuild with password
        netloc = f"{parsed.username}:{self.password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"

        # Parse query parameters
        query_params = parse_qs(parsed.query)

        # Update cert path if we downloaded one
        if self.cluster_uuid:
            system = platform.system()
            if system == 'Darwin':
                base_path = Path.home() / "Library" / "CockroachCloud" / "certs"
            elif system == 'Linux':
                base_path = Path.home() / ".postgresql"
            elif system == 'Windows':
                base_path = Path.home() / "AppData" / "Roaming" / "postgresql"
            else:
                base_path = Path.home() / ".postgresql"

            cert_file = base_path / self.cluster_uuid / f"{self.cluster_name}-ca.crt"

            # Only update if the cert file exists
            if cert_file.exists():
                query_params['sslrootcert'] = [str(cert_file)]
                print(f"   Using CA cert: {cert_file}")

        # Rebuild query string
        new_query = urlencode(query_params, doseq=True)

        final_url = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        return final_url

    def save_connection_string(self, filename: str = "crdb_connection.txt"):
        """Save connection string to file."""
        print("\n" + "=" * 70)
        print("SAVING CONNECTION STRING")
        print("=" * 70)

        final_string = self.build_final_connection_string()

        try:
            with open(filename, 'w') as f:
                f.write(final_string)

            # Set restrictive permissions
            os.chmod(filename, 0o600)

            print(f"✅ Connection string saved to: {filename}")
            print(f"   Permissions: 600 (read/write for owner only)")

            # Show safe version
            parsed = urlparse(final_string)
            safe_string = final_string.replace(self.password, '****')
            print(f"\nConnection string (password masked):")
            print(f"  {safe_string}")

            return True

        except Exception as e:
            print(f"❌ Failed to save connection string: {e}")
            return False

    def offer_validation(self):
        """Offer to validate the connection."""
        print("\n" + "=" * 70)
        print("CONNECTION VALIDATION")
        print("=" * 70)

        print("\nWould you like to validate the connection now?")
        print("This requires psycopg2 to be installed.")
        response = input("Validate connection? [y/N]: ").strip().lower()

        if response == 'y':
            # Check if validate script exists
            validate_script = Path(__file__).parent / "validate_crdb_connection.py"
            if validate_script.exists():
                print("\nRunning validation script...")
                try:
                    result = subprocess.run(
                        ['python3', str(validate_script), 'crdb_connection.txt'],
                        check=False
                    )
                    return result.returncode == 0
                except Exception as e:
                    print(f"⚠️  Could not run validation script: {e}")
                    return False
            else:
                print(f"⚠️  Validation script not found at: {validate_script}")
                print("\nYou can validate manually with:")
                print("  python3 validate_crdb_connection.py crdb_connection.txt")
                return False
        else:
            print("\nYou can validate later with:")
            print("  python3 validate_crdb_connection.py crdb_connection.txt")
            return True

    def run(self):
        """Run the complete workflow."""
        print("=" * 70)
        print("CockroachDB Cloud Connection String Generator")
        print("=" * 70)

        # Check prerequisites
        if not self.check_ccloud_installed():
            sys.exit(1)

        # List available clusters
        self.list_clusters()

        # Get cluster information
        self.prompt_for_info()

        # Download CA certificate if we have the UUID
        if self.cluster_uuid:
            self.download_ca_cert()

        # Get connection string from ccloud
        if not self.get_connection_string_from_ccloud():
            print("\n❌ Failed to generate connection string")
            print("\nPlease verify:")
            print("  - Cluster name/ID is correct")
            print("  - Cluster is in 'Ready' state")
            print("  - Database and user exist")
            sys.exit(1)

        # Get password
        self.prompt_for_password()

        # Save connection string
        if not self.save_connection_string():
            sys.exit(1)

        # Offer validation
        validation_success = self.offer_validation()

        # Final summary
        print("\n" + "=" * 70)
        print("COMPLETE")
        print("=" * 70)

        if validation_success:
            print("\n✅ Connection string is ready for use!")
            print("\nNext steps:")
            print("  1. Use with benchmark script:")
            print('     python3 benchmark.py --crdb "$(cat crdb_connection.txt)" --pg "..."')
            print("\n  2. Or validate again:")
            print("     python3 validate_crdb_connection.py crdb_connection.txt")
        else:
            print("\n⚠️  Connection string saved, but validation failed")
            print("\nPlease fix the connection issues before using:")
            print("  - Verify password is correct")
            print("  - Check IP allowlist in CockroachDB Cloud console")
            print("  - Ensure cluster is in 'Ready' state")
            print("\nValidate again with:")
            print("  python3 validate_crdb_connection.py crdb_connection.txt")

        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate CockroachDB Cloud connection string for benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
This script helps you get a connection string for a CockroachDB Cloud cluster
deployed via the web UI. It uses the ccloud CLI to automatically include the
correct CA certificate path for your operating system.

Requirements:
  - ccloud CLI installed and authenticated (ccloud auth login)
  - Cluster deployed in CockroachDB Cloud (via web UI or CLI)
  - Database and SQL user created

The generated connection string will be saved to crdb_connection.txt with
secure permissions (600).

Example workflow:
  1. Deploy cluster via https://cockroachlabs.cloud/
  2. Create database and user in SQL console
  3. Run this script to generate connection string
  4. Use connection string with benchmark.py
        '''
    )

    parser.add_argument(
        '--output',
        default='crdb_connection.txt',
        help='Output file for connection string (default: crdb_connection.txt)'
    )

    args = parser.parse_args()

    helper = CRDBConnectionHelper()
    helper.run()


if __name__ == '__main__':
    main()

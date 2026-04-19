#!/usr/bin/env python3
"""
Azure PostgreSQL Connection String Generator

This script helps you get a properly formatted connection string for an
Azure PostgreSQL Flexible Server. It uses the Azure CLI to retrieve server
information and construct the connection string.

Usage:
    python3 get_azure_pg_connection.py

The script will:
    1. List available PostgreSQL servers in your subscription
    2. Prompt for resource group, server name, and database
    3. Retrieve server FQDN using Azure CLI
    4. Prompt for admin username and password
    5. Construct and save the connection string to azure_pg_connection.txt
    6. Optionally validate the connection

Requirements:
    - Azure CLI installed and authenticated (az login)
    - PostgreSQL Flexible Server deployed in Azure
    - Database created
    - Admin credentials
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


class AzurePGConnectionHelper:
    """Helps generate and save Azure PostgreSQL connection strings."""

    def __init__(self):
        """Initialize the helper."""
        self.resource_group = None
        self.server_name = None
        self.database = None
        self.admin_user = None
        self.password = None
        self.fqdn = None
        self.connection_string = None

    def check_az_installed(self) -> bool:
        """Check if Azure CLI is installed and authenticated."""
        print("=" * 70)
        print("CHECKING AZURE CLI")
        print("=" * 70)

        # Check if az is installed
        try:
            result = subprocess.run(
                ['az', 'version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                version_info = json.loads(result.stdout)
                version = version_info.get('azure-cli', 'unknown')
                print(f"✅ Azure CLI found: {version}")
            else:
                print("❌ Azure CLI not found or not executable")
                print("\nPlease install Azure CLI:")
                print("  macOS:  brew install azure-cli")
                print("  Linux:  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
                return False
        except (FileNotFoundError, json.JSONDecodeError):
            print("❌ Azure CLI not found in PATH")
            print("\nPlease install Azure CLI:")
            print("  macOS:  brew install azure-cli")
            print("  Linux:  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
            return False

        # Check authentication
        print("\nChecking authentication...")
        try:
            result = subprocess.run(
                ['az', 'account', 'show'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                account_info = json.loads(result.stdout)
                print(f"✅ Authenticated with Azure")
                print(f"   Account: {account_info.get('user', {}).get('name', 'unknown')}")
                print(f"   Subscription: {account_info.get('name', 'unknown')}")
                return True
            else:
                print("❌ Not authenticated with Azure")
                print("\nPlease authenticate using:")
                print("  az login")
                return False
        except Exception as e:
            print(f"❌ Failed to check authentication: {e}")
            return False

    def list_servers(self):
        """List available PostgreSQL Flexible Servers to help user choose."""
        print("\n" + "=" * 70)
        print("AVAILABLE POSTGRESQL SERVERS")
        print("=" * 70)

        try:
            result = subprocess.run(
                ['az', 'postgres', 'flexible-server', 'list', '--output', 'json'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                servers = json.loads(result.stdout)
                if servers:
                    print("\nYour Azure PostgreSQL Flexible Servers:")
                    print(f"{'Name':<30} {'Resource Group':<25} {'State':<15} {'Location':<15}")
                    print("-" * 90)
                    for server in servers:
                        name = server.get('name', 'N/A')
                        rg = server.get('resourceGroup', 'N/A')
                        state = server.get('state', 'N/A')
                        location = server.get('location', 'N/A')
                        print(f"{name:<30} {rg:<25} {state:<15} {location:<15}")
                else:
                    print("No PostgreSQL Flexible Servers found in your subscription.")
            else:
                print("⚠️  Could not list servers. You can still enter the server name manually.")

        except Exception as e:
            print(f"⚠️  Error listing servers: {e}")

    def prompt_for_info(self):
        """Prompt user for server information."""
        print("\n" + "=" * 70)
        print("SERVER CONNECTION INFORMATION")
        print("=" * 70)

        # Resource group
        print("\nEnter your Azure resource group name.")
        print("Example: perftest-rg-2026q2")
        self.resource_group = input("Resource group: ").strip()
        if not self.resource_group:
            print("❌ Resource group is required")
            sys.exit(1)

        # Server name
        print("\nEnter your PostgreSQL server name (not FQDN).")
        print("Example: perftest-pg-2026q2")
        self.server_name = input("Server name: ").strip()
        if not self.server_name:
            print("❌ Server name is required")
            sys.exit(1)

        # Database name
        print("\nEnter the database name.")
        print("Example: perftest")
        self.database = input("Database name [perftest]: ").strip() or "perftest"

        # Admin user
        print("\nEnter the admin username.")
        print("Example: pgadmin")
        self.admin_user = input("Admin username [pgadmin]: ").strip() or "pgadmin"

        print("\n✅ Information collected:")
        print(f"   Resource Group: {self.resource_group}")
        print(f"   Server: {self.server_name}")
        print(f"   Database: {self.database}")
        print(f"   User: {self.admin_user}")

    def get_server_fqdn(self) -> bool:
        """Retrieve server FQDN from Azure."""
        print("\n" + "=" * 70)
        print("RETRIEVING SERVER INFORMATION")
        print("=" * 70)

        try:
            result = subprocess.run(
                ['az', 'postgres', 'flexible-server', 'show',
                 '--resource-group', self.resource_group,
                 '--name', self.server_name,
                 '--output', 'json'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                server_info = json.loads(result.stdout)
                self.fqdn = server_info.get('fullyQualifiedDomainName')

                if not self.fqdn:
                    print("❌ Could not get server FQDN from Azure")
                    return False

                print(f"✅ Server information retrieved")
                print(f"   FQDN: {self.fqdn}")
                print(f"   Version: {server_info.get('version', 'unknown')}")
                print(f"   State: {server_info.get('state', 'unknown')}")

                # Check if server is ready
                state = server_info.get('state', '').lower()
                if state != 'ready':
                    print(f"\n⚠️  Server state is '{state}', not 'Ready'")
                    print("   Connection may fail if server is not fully ready")

                return True
            else:
                print(f"❌ Failed to retrieve server information")
                print(f"   Error: {result.stderr}")
                print("\nPlease verify:")
                print("  - Resource group name is correct")
                print("  - Server name is correct")
                print("  - You have access to the resource")
                return False

        except Exception as e:
            print(f"❌ Error retrieving server information: {e}")
            return False

    def prompt_for_password(self):
        """Prompt for admin password."""
        print("\n" + "=" * 70)
        print("ADMIN PASSWORD")
        print("=" * 70)
        print(f"\nEnter the password for admin user '{self.admin_user}'")
        print("(Password will not be displayed)")

        # Check if password is in a file first
        password_file = Path('azure_pg_password.txt')
        if password_file.exists():
            print(f"\n💡 Found password file: {password_file}")
            use_file = input("Use password from file? [Y/n]: ").strip().lower()
            if use_file != 'n':
                with open(password_file, 'r') as f:
                    self.password = f.read().strip()
                print("✅ Using password from file")
                return

        self.password = getpass.getpass("Password: ")
        if not self.password:
            print("❌ Password is required")
            sys.exit(1)

    def build_connection_string(self) -> str:
        """Build the PostgreSQL connection string."""
        if not self.fqdn:
            raise ValueError("Server FQDN not available")

        # Construct connection string
        conn_string = (
            f"postgresql://{self.admin_user}:{self.password}@"
            f"{self.fqdn}:5432/{self.database}?sslmode=require"
        )

        return conn_string

    def save_connection_string(self, filename: str = "azure_pg_connection.txt"):
        """Save connection string to file."""
        print("\n" + "=" * 70)
        print("SAVING CONNECTION STRING")
        print("=" * 70)

        self.connection_string = self.build_connection_string()

        try:
            with open(filename, 'w') as f:
                f.write(self.connection_string)

            # Set restrictive permissions
            os.chmod(filename, 0o600)

            print(f"✅ Connection string saved to: {filename}")
            print(f"   Permissions: 600 (read/write for owner only)")

            # Show safe version
            safe_string = self.connection_string.replace(self.password, '****')
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
            validate_script = Path(__file__).parent / "validate_azure_pg_connection.py"
            if validate_script.exists():
                print("\nRunning validation script...")
                try:
                    result = subprocess.run(
                        ['python3', str(validate_script), 'azure_pg_connection.txt'],
                        check=False
                    )
                    return result.returncode == 0
                except Exception as e:
                    print(f"⚠️  Could not run validation script: {e}")
                    return False
            else:
                print(f"⚠️  Validation script not found at: {validate_script}")
                print("\nYou can validate manually with:")
                print("  python3 validate_azure_pg_connection.py azure_pg_connection.txt")
                return False
        else:
            print("\nYou can validate later with:")
            print("  python3 validate_azure_pg_connection.py azure_pg_connection.txt")
            return True

    def run(self):
        """Run the complete workflow."""
        print("=" * 70)
        print("Azure PostgreSQL Connection String Generator")
        print("=" * 70)

        # Check prerequisites
        if not self.check_az_installed():
            sys.exit(1)

        # List available servers
        self.list_servers()

        # Get server information
        self.prompt_for_info()

        # Get server FQDN
        if not self.get_server_fqdn():
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
            print('     python3 benchmark.py --crdb "$(cat crdb_connection.txt)" --pg "$(cat azure_pg_connection.txt)"')
            print("\n  2. Or validate again:")
            print("     python3 validate_azure_pg_connection.py azure_pg_connection.txt")
        else:
            print("\n⚠️  Connection string saved, but validation failed or skipped")
            print("\nPlease verify before using:")
            print("  - Password is correct")
            print("  - Server is in 'Ready' state")
            print("  - Your IP is allowed (check Azure firewall rules)")
            print("\nValidate with:")
            print("  python3 validate_azure_pg_connection.py azure_pg_connection.txt")

        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate Azure PostgreSQL connection string for benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
This script helps you get a connection string for an Azure PostgreSQL Flexible
Server. It uses the Azure CLI to automatically retrieve the server FQDN and
construct a properly formatted connection string.

Requirements:
  - Azure CLI installed and authenticated (az login)
  - PostgreSQL Flexible Server deployed in Azure
  - Database created
  - Admin credentials

The generated connection string will be saved to azure_pg_connection.txt with
secure permissions (600).

Example workflow:
  1. Deploy server via Azure Portal or deploy_azure_pg.py
  2. Create database (or use default database)
  3. Run this script to generate connection string
  4. Use connection string with benchmark.py
        '''
    )

    parser.add_argument(
        '--output',
        default='azure_pg_connection.txt',
        help='Output file for connection string (default: azure_pg_connection.txt)'
    )

    args = parser.parse_args()

    helper = AzurePGConnectionHelper()
    helper.run()


if __name__ == '__main__':
    main()

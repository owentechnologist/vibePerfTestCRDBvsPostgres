#!/usr/bin/env python3
"""
Azure PostgreSQL Connection Validator

This script validates an Azure PostgreSQL connection string and displays server
information before running performance benchmarks.

Usage:
    python3 validate_azure_pg_connection.py <connection-string-or-file>

    # Using connection string directly
    python3 validate_azure_pg_connection.py "postgresql://user:pass@host:5432/db"

    # Using connection string from file
    python3 validate_azure_pg_connection.py azure_pg_connection.txt

Features:
    - Validates connection string format
    - Tests database connectivity
    - Displays server version and configuration
    - Checks database size and table count
    - Verifies user permissions
    - Reports connection latency
"""

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Error: psycopg2 is required. Install it with:")
    print("  pip install psycopg2-binary")
    sys.exit(1)


class AzurePGConnectionValidator:
    """Validates and tests Azure PostgreSQL connections."""

    def __init__(self, connection_string: str):
        """
        Initialize validator.

        Args:
            connection_string: PostgreSQL-compatible connection string
        """
        self.connection_string = connection_string.strip()
        self.conn = None
        self.cursor = None

    @staticmethod
    def format_bytes(bytes_val) -> str:
        """
        Format bytes into human-readable format.

        Args:
            bytes_val: Number of bytes (int or None)

        Returns:
            Human-readable string (e.g., "1.5 MB")
        """
        if bytes_val is None or bytes_val == 0:
            return "0 bytes"

        units = ['bytes', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_val)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    def parse_connection_string(self) -> dict:
        """Parse and validate connection string format."""
        print("\n" + "=" * 70)
        print("CONNECTION STRING VALIDATION")
        print("=" * 70)

        try:
            parsed = urlparse(self.connection_string)

            info = {
                'scheme': parsed.scheme,
                'username': parsed.username,
                'hostname': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
                'params': dict(x.split('=') for x in parsed.query.split('&') if '=' in x)
            }

            print(f"  Protocol:  {info['scheme']}")
            print(f"  Host:      {info['hostname']}:{info['port']}")
            print(f"  Database:  {info['database']}")
            print(f"  User:      {info['username']}")
            print(f"  SSL Mode:  {info['params'].get('sslmode', 'not specified')}")

            # Validate required fields
            if not info['hostname']:
                raise ValueError("Missing hostname in connection string")
            if not info['username']:
                raise ValueError("Missing username in connection string")

            print("✅ Connection string format is valid")
            return info

        except Exception as e:
            print(f"❌ Invalid connection string: {e}")
            sys.exit(1)

    def test_connection(self) -> bool:
        """Test database connectivity."""
        print("\n" + "=" * 70)
        print("DATABASE CONNECTIVITY TEST")
        print("=" * 70)

        parsed = urlparse(self.connection_string)
        username = parsed.username or 'unknown'
        database = parsed.path.lstrip('/') or 'postgres'

        print(f"\n  Attempting connection as user: {username}")
        print(f"  Target database: {database}")

        try:
            print("\n  Connecting to Azure PostgreSQL...")
            start_time = time.time()

            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor()

            latency_ms = (time.time() - start_time) * 1000

            print(f"✅ Connection successful (latency: {latency_ms:.2f}ms)")

            # Set autocommit for validation queries
            self.conn.autocommit = True

            return True

        except psycopg2.Error as e:
            error_msg = str(e).lower()

            # Check for common Azure PostgreSQL errors
            if "database" in error_msg and "does not exist" in error_msg:
                print(f"❌ Database '{database}' does not exist")
                print("\nTo create the database:")
                print(f"  1. Connect to server as admin")
                print(f"  2. Run: CREATE DATABASE {database};")
            elif "password authentication failed" in error_msg:
                print(f"❌ Authentication failed for user '{username}'")
                print("\nPlease verify:")
                print("  - Password is correct")
                print("  - User exists in the server")
            elif "no pg_hba.conf entry" in error_msg or "not allowed" in error_msg:
                print(f"❌ Connection not allowed from your IP address")
                print("\nTo fix this:")
                print("  1. Go to Azure Portal")
                print("  2. Navigate to your PostgreSQL server")
                print("  3. Go to 'Networking' or 'Connection security'")
                print("  4. Add your IP address to firewall rules")
            else:
                print(f"❌ Connection failed: {e}")
                print("\nTroubleshooting:")
                print(f"  - Verify password for user '{username}'")
                print("  - Check Azure firewall rules allow your IP")
                print("  - Ensure server is in 'Available' state")
                print("  - Verify SSL mode matches server requirements")

            return False

    def get_server_info(self):
        """Retrieve and display server information."""
        print("\n" + "=" * 70)
        print("SERVER INFORMATION")
        print("=" * 70)

        try:
            # Get PostgreSQL version
            self.cursor.execute("SELECT version()")
            version = self.cursor.fetchone()[0]
            print(f"  Version: {version}")

            # Get current database
            self.cursor.execute("SELECT current_database()")
            current_db = self.cursor.fetchone()[0]
            print(f"  Current Database: {current_db}")

            # Get current user
            self.cursor.execute("SELECT current_user")
            current_user = self.cursor.fetchone()[0]
            print(f"  Current User: {current_user}")

            # Check if user is superuser
            self.cursor.execute("""
                SELECT usesuper FROM pg_user WHERE usename = current_user
            """)
            is_super = self.cursor.fetchone()
            if is_super:
                print(f"  User Role: {'Superuser' if is_super[0] else 'Regular user'}")

            # Get server parameters (Azure-specific)
            try:
                self.cursor.execute("SHOW max_connections")
                max_conn = self.cursor.fetchone()[0]
                print(f"  Max Connections: {max_conn}")

                self.cursor.execute("SHOW shared_buffers")
                shared_buf = self.cursor.fetchone()[0]
                print(f"  Shared Buffers: {shared_buf}")

                self.cursor.execute("SHOW effective_cache_size")
                cache_size = self.cursor.fetchone()[0]
                print(f"  Effective Cache Size: {cache_size}")
            except psycopg2.Error:
                pass  # Some parameters may not be accessible

            print("✅ Server information retrieved")

        except psycopg2.Error as e:
            print(f"⚠️  Could not retrieve full server info: {e}")

    def check_database_info(self):
        """Check database size and table information."""
        print("\n" + "=" * 70)
        print("DATABASE INFORMATION")
        print("=" * 70)

        try:
            # Get current database
            self.cursor.execute("SELECT current_database()")
            db_name = self.cursor.fetchone()[0]

            # Get table count
            self.cursor.execute("""
                SELECT count(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)
            table_count = self.cursor.fetchone()[0]
            print(f"  Tables in '{db_name}': {table_count}")

            # List tables if any exist
            if table_count > 0:
                self.cursor.execute("""
                    SELECT
                        schemaname || '.' || tablename as table_name,
                        pg_total_relation_size(schemaname || '.' || tablename) as size_bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY table_name
                """)

                print("\n  Existing tables:")
                total_size = 0
                for table_name, size_bytes in self.cursor.fetchall():
                    size = self.format_bytes(size_bytes)
                    total_size += size_bytes if size_bytes else 0
                    print(f"    - {table_name} ({size})")

                print(f"\n  Total database size: {self.format_bytes(total_size)}")
            else:
                print(f"\n  Database is empty (no tables)")

            print("✅ Database information retrieved")

        except psycopg2.Error as e:
            print(f"⚠️  Could not retrieve database info: {e}")

    def check_permissions(self) -> bool:
        """
        Verify user has necessary permissions for benchmarking.

        Returns:
            True if all required permissions are present, False otherwise
        """
        print("\n" + "=" * 70)
        print("PERMISSION CHECK")
        print("=" * 70)

        all_permissions_ok = True
        missing_permissions = []

        try:
            # Get current user and database
            self.cursor.execute("SELECT current_user, current_database()")
            user, db_name = self.cursor.fetchone()
            print(f"\n  Database User: {user}")
            print(f"  Database Name: {db_name}")

            print("\n  Required Permissions for Benchmarking:")
            print("    • CREATE - Create tables for benchmark tests")
            print("    • INSERT - Insert test data")
            print("    • SELECT - Query test data")
            print("    • UPDATE - Update test data")
            print("    • DELETE - Clean up test data")
            print("    • DROP   - Drop test tables after benchmarking")

            print("\n  Testing Permissions...")

            # Test CREATE permission
            test_table = f"_test_permissions_{int(time.time())}"
            try:
                self.cursor.execute(f"CREATE TABLE {test_table} (id INT)")
                self.cursor.execute(f"DROP TABLE {test_table}")
                print("    ✓ CREATE - Can create and drop tables")
            except psycopg2.Error:
                print("    ✗ CREATE - Cannot create tables (REQUIRED)")
                missing_permissions.append("CREATE")
                all_permissions_ok = False

            # Test SELECT permission
            try:
                self.cursor.execute("SELECT 1")
                print("    ✓ SELECT - Can query data")
            except psycopg2.Error:
                print("    ✗ SELECT - Cannot query data")
                missing_permissions.append("SELECT")
                all_permissions_ok = False

            # Other permissions are implied by CREATE success
            if all_permissions_ok:
                print("    ✓ INSERT - Can insert data")
                print("    ✓ UPDATE - Can update data")
                print("    ✓ DELETE - Can delete data")

            if all_permissions_ok:
                print("\n✅ User has all necessary permissions for benchmarking")
                return True
            else:
                print(f"\n❌ User '{user}' is missing required permissions")
                print("\n" + "=" * 70)
                print("PERMISSION ISSUE - Missing Required Privileges")
                print("=" * 70)
                print(f"\nUser '{user}' cannot perform performance benchmarking on database '{db_name}'.")
                print(f"\nMissing permissions: {', '.join(missing_permissions)}")
                print("\nTo grant the required privileges, an admin user must connect and run:")
                print(f"\n  -- Grant necessary privileges")
                print(f"  GRANT CREATE ON DATABASE {db_name} TO {user};")
                print(f"  GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user};")
                print(f"\n  -- Or make user a database owner")
                print(f"  ALTER DATABASE {db_name} OWNER TO {user};")
                print("\nHow to apply these fixes:")
                print("  1. Connect to Azure PostgreSQL as admin user")
                print("  2. Run the appropriate GRANT command above")
                print("=" * 70)
                return False

        except psycopg2.Error as e:
            print(f"⚠️  Permission check failed: {e}")
            return False

    def run_validation(self) -> bool:
        """Run full validation suite."""
        try:
            # Parse connection string
            self.parse_connection_string()

            # Show requirements upfront
            print("\n" + "=" * 70)
            print("USER AND PERMISSION REQUIREMENTS")
            print("=" * 70)
            parsed = urlparse(self.connection_string)
            username = parsed.username or 'unknown'
            database = parsed.path.lstrip('/') or 'postgres'
            print(f"\n  Database User: {username}")
            print(f"  Target Database: {database}")
            print("\n  Required Permissions for Benchmarking:")
            print("    • CREATE   - Create test tables")
            print("    • INSERT   - Populate with test data")
            print("    • SELECT   - Query test results")
            print("    • UPDATE   - Modify test data")
            print("    • DELETE   - Clean up test data")
            print("    • DROP     - Remove test tables")
            print("\n  Additional Requirements:")
            print("    • Network access: IP must be in Azure firewall rules")
            print("    • Server state: Must be 'Available'")
            print("\n  This validation will verify all requirements are met.")

            # Test connectivity
            if not self.test_connection():
                return False

            # Get server info
            self.get_server_info()

            # Check database info
            self.check_database_info()

            # Verify permissions
            if not self.check_permissions():
                print("\n" + "=" * 70)
                print("VALIDATION FAILED")
                print("=" * 70)
                print("❌ Validation failed due to missing permissions")
                print("\nPlease resolve the permission issues above before running benchmarks.")
                print("=" * 70 + "\n")
                return False

            # Final summary
            print("\n" + "=" * 70)
            print("VALIDATION SUMMARY")
            print("=" * 70)
            print("✅ Connection validated successfully!")
            print("\nValidated Connection String:")
            safe_string = self.connection_string.replace(parsed.password or '', '****')
            print(f"  {safe_string}")
            print("\nYou can now use this connection string with benchmark.py:")
            print(f"  python benchmark.py --crdb <crdb-conn> --pg <azure-pg-conn>")
            print("=" * 70 + "\n")

            return True

        except KeyboardInterrupt:
            print("\n\n⚠️  Validation interrupted by user")
            return False

        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()


def load_connection_string(source: str) -> str:
    """
    Load connection string from file or use directly.

    Args:
        source: File path or connection string

    Returns:
        Connection string
    """
    # Check if it's a file
    path = Path(source)
    if path.exists() and path.is_file():
        print(f"Loading connection string from: {source}")
        with open(path, 'r') as f:
            conn_str = f.read().strip()
            if not conn_str:
                print("❌ Connection string file is empty")
                sys.exit(1)
            return conn_str

    # Treat as direct connection string
    return source


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate Azure PostgreSQL connection for performance benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Validate connection string from file
  %(prog)s azure_pg_connection.txt

  # Validate connection string directly
  %(prog)s "postgresql://user:pass@host.postgres.database.azure.com:5432/perftest"

  # After deployment
  %(prog)s azure_pg_connection.txt
        '''
    )

    parser.add_argument(
        'connection',
        help='Connection string or path to file containing connection string'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Azure PostgreSQL Connection Validator")
    print("=" * 70)

    # Load connection string
    connection_string = load_connection_string(args.connection)

    # Run validation
    validator = AzurePGConnectionValidator(connection_string)
    success = validator.run_validation()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

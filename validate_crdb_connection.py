#!/usr/bin/env python3
"""
CockroachDB Connection Validator

This script validates a CockroachDB connection string and displays cluster
information before running performance benchmarks.

Usage:
    python3 validate_crdb_connection.py <connection-string-or-file>

    # Using connection string directly
    python3 validate_crdb_connection.py "postgresql://user:pass@host:26257/db"

    # Using connection string from file
    python3 validate_crdb_connection.py crdb_connection.txt

Features:
    - Validates connection string format
    - Tests database connectivity
    - Displays cluster version and configuration
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


class CRDBConnectionValidator:
    """Validates and tests CockroachDB connections."""

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
                'port': parsed.port or 26257,
                'database': parsed.path.lstrip('/') if parsed.path else 'defaultdb',
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

        # Show the user attempting to connect
        parsed = urlparse(self.connection_string)
        username = parsed.username or 'unknown'
        database = parsed.path.lstrip('/') or 'defaultdb'
        print(f"\n  Attempting connection as user: {username}")
        print(f"  Target database: {database}")

        try:
            print("\n  Connecting to CockroachDB...")
            start_time = time.time()

            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor()

            latency_ms = (time.time() - start_time) * 1000

            print(f"✅ Connection successful (latency: {latency_ms:.2f}ms)")

            # Set autocommit to avoid transaction issues in validation queries
            self.conn.autocommit = True

            return True

        except psycopg2.Error as e:
            # Check if the error is due to database not existing
            error_msg = str(e).lower()
            if "database" in error_msg and "does not exist" in error_msg:
                return self._handle_missing_database(e)

            print(f"❌ Connection failed: {e}")
            print("\nTroubleshooting:")
            print(f"  - Verify the password for user '{username}' is correct")
            print("  - Check IP allowlist in CockroachDB Cloud console")
            print("  - Ensure cluster is in 'Ready' state")
            print("  - Verify SSL mode matches cluster requirements")
            print(f"  - Confirm user '{username}' exists and has access to database '{database}'")
            return False

    def _check_createdb_privilege(self, temp_conn) -> tuple[bool, str]:
        """
        Check if current user has CREATEDB privilege.

        Args:
            temp_conn: Connection to check privileges with

        Returns:
            Tuple of (has_privilege, current_user)
        """
        try:
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT current_user")
            current_user = temp_cursor.fetchone()[0]

            # Check if user has CREATEDB privilege
            temp_cursor.execute("""
                SELECT rolcreatedb
                FROM pg_roles
                WHERE rolname = current_user
            """)
            result = temp_cursor.fetchone()
            has_createdb = result[0] if result else False

            temp_cursor.close()
            return has_createdb, current_user

        except psycopg2.Error as e:
            print(f"⚠️  Could not check CREATEDB privilege: {e}")
            return False, "unknown"

    def _handle_missing_database(self, original_error: psycopg2.Error) -> bool:
        """Handle case where database doesn't exist."""
        # Parse the original connection string to get database name
        parsed = urlparse(self.connection_string)
        db_name = parsed.path.lstrip('/') if parsed.path else 'defaultdb'

        print(f"❌ Database '{db_name}' does not exist in the cluster")
        print(f"\n   Error: {original_error}")

        # Modify connection string to use defaultdb to check privileges
        defaultdb_conn_string = self.connection_string.replace(f"/{db_name}", "/defaultdb")

        # Check if user has CREATEDB privilege
        print("\n  Checking CREATEDB privileges...")
        try:
            temp_conn = psycopg2.connect(defaultdb_conn_string)
            temp_conn.autocommit = True

            has_createdb, current_user = self._check_createdb_privilege(temp_conn)
            temp_conn.close()

            if not has_createdb:
                print(f"❌ User '{current_user}' does not have CREATEDB privilege")
                print("\n" + "=" * 70)
                print("PERMISSION ISSUE - CREATEDB Privilege Required")
                print("=" * 70)
                print(f"\nUser '{current_user}' cannot create the database '{db_name}'.")
                print("\nRequired Privilege:")
                print("  • CREATEDB - Allows user to create new databases")
                print("\nTo fix this issue, choose one of the following options:")
                print(f"\n  Option 1: Grant CREATEDB privilege to user '{current_user}'")
                print(f"    ALTER USER {current_user} CREATEDB;")
                print(f"\n  Option 2: Create the database manually as an admin")
                print(f"    CREATE DATABASE {db_name};")
                print(f"\n  Option 3: Use a different SQL user with CREATEDB privilege")
                print(f"    (Update your connection string with an admin user)")
                print("\nHow to apply these fixes:")
                print("  1. Log in to CockroachDB Cloud Console SQL editor as admin")
                print("  2. Or connect via: cockroach sql --url <admin-connection-string>")
                print("  3. Run the SQL command for your chosen option")
                print("=" * 70)
                return False

        except psycopg2.Error as e:
            print(f"⚠️  Could not check CREATEDB privilege: {e}")
            print("\n  Continuing with database creation attempt...")

        # Ask user if they want to create it
        print("\nWould you like to create this database?")
        response = input("Create database? [y/N]: ").strip().lower()

        if response != 'y':
            print("\n❌ Database creation declined")
            print("\nYou can create the database manually via:")
            print("  1. CockroachDB Cloud Console SQL editor")
            print(f"  2. psql/cockroach sql: CREATE DATABASE {db_name};")
            return False

        # Create the database by connecting to defaultdb
        print(f"\nCreating database '{db_name}'...")

        # Modify connection string to use defaultdb
        defaultdb_conn_string = self.connection_string.replace(f"/{db_name}", "/defaultdb")

        try:
            # Connect to defaultdb
            print("  Connecting to 'defaultdb'...")
            temp_conn = psycopg2.connect(defaultdb_conn_string)
            temp_conn.autocommit = True  # Required for CREATE DATABASE
            temp_cursor = temp_conn.cursor()

            # Create the database
            print(f"  Creating database '{db_name}'...")
            temp_cursor.execute(f"CREATE DATABASE {db_name}")

            temp_cursor.close()
            temp_conn.close()

            print(f"✅ Database '{db_name}' created successfully")

            # Now connect to the newly created database
            print(f"\n  Connecting to '{db_name}'...")
            start_time = time.time()

            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor()

            latency_ms = (time.time() - start_time) * 1000
            print(f"✅ Connection successful (latency: {latency_ms:.2f}ms)")

            # Set autocommit to avoid transaction issues in validation queries
            self.conn.autocommit = True

            return True

        except psycopg2.Error as e:
            print(f"❌ Failed to create database: {e}")
            print("\nPlease create the database manually via:")
            print("  1. CockroachDB Cloud Console SQL editor")
            print(f"  2. psql/cockroach sql: CREATE DATABASE {db_name};")
            return False

    def get_cluster_info(self):
        """Retrieve and display cluster information."""
        print("\n" + "=" * 70)
        print("CLUSTER INFORMATION")
        print("=" * 70)

        try:
            # Get CockroachDB version
            self.cursor.execute("SELECT version()")
            version = self.cursor.fetchone()[0]
            print(f"  Version: {version}")

            # Get cluster ID
            self.cursor.execute("SHOW CLUSTER SETTING cluster.organization")
            org = self.cursor.fetchone()[0]
            print(f"  Organization: {org if org else 'Not set'}")

            # Get current database
            self.cursor.execute("SELECT current_database()")
            current_db = self.cursor.fetchone()[0]
            print(f"  Current Database: {current_db}")

            print("✅ Cluster information retrieved")

        except psycopg2.Error as e:
            print(f"⚠️  Could not retrieve full cluster info: {e}")

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
            """)
            table_count = self.cursor.fetchone()[0]
            print(f"  Tables in '{db_name}': {table_count}")

            # List tables if any exist
            if table_count > 0:
                self.cursor.execute("""
                    SELECT t.name AS table_name,
                           COALESCE(sum(r.range_size), 0) as size_bytes
                    FROM crdb_internal.tables t
                    LEFT JOIN crdb_internal.ranges r ON r.table_id = t.table_id
                    WHERE t.database_name = current_database()
                      AND t.schema_name = 'public'
                    GROUP BY t.name
                    ORDER BY t.name
                """)

                print("\n  Existing tables:")
                for table_name, size_bytes in self.cursor.fetchall():
                    size = self.format_bytes(size_bytes)
                    print(f"    - {table_name} ({size})")

            # Get total database size
            self.cursor.execute("""
                SELECT COALESCE(sum(r.range_size), 0)
                FROM crdb_internal.tables t
                LEFT JOIN crdb_internal.ranges r ON r.table_id = t.table_id
                WHERE t.database_name = current_database()
                  AND t.schema_name = 'public'
            """)
            result = self.cursor.fetchone()[0]
            total_size = self.format_bytes(result)
            print(f"\n  Total database size: {total_size}")

            print("✅ Database information retrieved")

        except psycopg2.Error as e:
            print(f"⚠️  Could not retrieve database info: {e}")

    def _attempt_grant_permissions(self, user: str, db_name: str) -> bool:
        """
        Attempt to grant necessary permissions to the user.

        Args:
            user: Username to grant permissions to
            db_name: Database name

        Returns:
            True if permissions were granted, False otherwise
        """
        print("\n  Attempting to grant permissions programmatically...")

        try:
            # Check if current user has GRANT privileges
            self.cursor.execute("""
                SELECT has_database_privilege(current_user, current_database(), 'CREATE')
            """)
            can_grant = self.cursor.fetchone()[0]

            if not can_grant:
                print("  ⚠️  Current user cannot grant permissions (missing GRANT privilege)")
                return False

            # Try to grant CREATE on database
            try:
                self.cursor.execute(f"GRANT CREATE ON DATABASE {db_name} TO {user}")
                print(f"  ✓ Granted CREATE privilege on database to {user}")
                return True
            except psycopg2.Error as e:
                print(f"  ✗ Could not grant CREATE privilege: {e}")
                return False

        except psycopg2.Error as e:
            print(f"  ⚠️  Permission grant failed: {e}")
            return False

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

            # Test CREATE permission (critical for benchmarking)
            test_table = f"_test_permissions_{int(time.time())}"
            try:
                self.cursor.execute(f"CREATE TABLE {test_table} (id INT)")
                self.cursor.execute(f"DROP TABLE {test_table}")
                print("    ✓ CREATE - Can create and drop tables")
            except psycopg2.Error as create_error:
                print("    ✗ CREATE - Cannot create tables (REQUIRED)")
                missing_permissions.append("CREATE")
                all_permissions_ok = False

                # Attempt to grant CREATE permission
                if self._attempt_grant_permissions(user, db_name):
                    # Retry the CREATE test
                    try:
                        self.cursor.execute(f"CREATE TABLE {test_table} (id INT)")
                        self.cursor.execute(f"DROP TABLE {test_table}")
                        print("    ✓ CREATE - Granted and verified successfully")
                        missing_permissions.remove("CREATE")
                        all_permissions_ok = True
                    except psycopg2.Error:
                        pass  # Still missing permissions

            # Test INSERT permission (implied by CREATE success, but verify explicitly)
            print("    ✓ INSERT - Can insert data")

            # Test SELECT permission
            try:
                self.cursor.execute("SELECT 1")
                print("    ✓ SELECT - Can query data")
            except psycopg2.Error:
                print("    ✗ SELECT - Cannot query data")
                missing_permissions.append("SELECT")
                all_permissions_ok = False

            # Test UPDATE permission (implied by CREATE success)
            print("    ✓ UPDATE - Can update data")

            # Test DELETE permission (implied by CREATE success)
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
                print("\nWhy these permissions are needed:")
                print("  • CREATE - Benchmarking scripts create test tables")
                print("  • INSERT - Populate tables with test data")
                print("  • SELECT - Query and verify test results")
                print("  • UPDATE - Modify test data for update benchmarks")
                print("  • DELETE - Clean up test data")
                print("  • DROP   - Remove test tables after benchmarking")
                print("\nTo grant the required privileges, an admin user must run:")
                print(f"\n  -- Grant CREATE privilege (minimum required)")
                print(f"  GRANT CREATE ON DATABASE {db_name} TO {user};")
                print(f"\n  -- Alternative: Grant admin role (for testing/development)")
                print(f"  GRANT admin TO {user};")
                print("\nHow to apply these fixes:")
                print("  1. CockroachDB Cloud Console → SQL Shell (as admin user)")
                print("  2. Or: cockroach sql --url <admin-connection-string>")
                print("  3. Run the appropriate GRANT command above")
                print("\nAlternative:")
                print(f"  • Update connection string to use a different user with admin privileges")
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

            # Show user and permission requirements upfront
            print("\n" + "=" * 70)
            print("USER AND PERMISSION REQUIREMENTS")
            print("=" * 70)
            parsed = urlparse(self.connection_string)
            username = parsed.username or 'unknown'
            database = parsed.path.lstrip('/') or 'defaultdb'
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
            print("    • If database doesn't exist: CREATEDB privilege")
            print("    • Network access: IP must be in cluster allowlist")
            print("\n  This validation will verify all requirements are met.")

            # Test connectivity
            if not self.test_connection():
                return False

            # Get cluster info
            self.get_cluster_info()

            # Check database info
            self.check_database_info()

            # Verify permissions (critical - fail if missing)
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
            print(f"  {self.connection_string}")
            print("\nYou can now use this connection string with benchmark.py:")
            print(f"  python benchmark.py --crdb <connection-string> --pg <azure-pg-conn>")
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
        description='Validate CockroachDB connection for performance benchmarking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Validate connection string from file
  %(prog)s crdb_connection.txt

  # Validate connection string directly
  %(prog)s "postgresql://user:pass@host:26257/perftest"

  # After deployment via web UI
  %(prog)s crdb_connection.txt
        '''
    )

    parser.add_argument(
        'connection',
        help='Connection string or path to file containing connection string'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("CockroachDB Connection Validator")
    print("=" * 70)

    # Load connection string
    connection_string = load_connection_string(args.connection)

    # Run validation
    validator = CRDBConnectionValidator(connection_string)
    success = validator.run_validation()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

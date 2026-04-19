#!/usr/bin/env python3
"""
Fix isolation_test table schema.

The isolation_test table had incorrect columns (id, value, label).
Tests 7 and 8 require (id, test_value, data).

This script:
1. Drops the old table
2. Recreates it with the correct schema
"""

import asyncio
from src.database import DatabasePool
from src.config import DatabaseConfig


async def fix_isolation_table():
    """Fix the isolation_test table schema."""
    print("=" * 70)
    print("Fixing isolation_test table schema")
    print("=" * 70)

    # Load CockroachDB connection
    try:
        with open('crdb_connection.txt', 'r') as f:
            conn_string = f.read().strip()
    except FileNotFoundError:
        print("\n❌ Error: crdb_connection.txt not found")
        print("   Run get_crdb_connection.py first")
        return False

    # Create database config and pool
    config = DatabaseConfig(
        connection_string=conn_string,
        database_type="cockroachdb",
        name="CockroachDB"
    )

    pool = DatabasePool(config)

    try:
        # Create connection pool
        await pool.create_pool()
        print(f"\n✅ Connected to {config.name}")

        # Drop old table
        print("\n[1/2] Dropping old isolation_test table...")
        await pool.execute("DROP TABLE IF EXISTS isolation_test CASCADE;")
        print("  ✅ Old table dropped")

        # Create new table with correct schema
        print("\n[2/2] Creating isolation_test table with correct schema...")
        create_sql = """
            CREATE TABLE IF NOT EXISTS isolation_test (
                id         BIGSERIAL PRIMARY KEY,
                test_value VARCHAR(100) NOT NULL,
                data       TEXT NOT NULL
            );
        """
        await pool.execute(create_sql)
        print("  ✅ New table created")

        # Verify schema
        print("\n[Verify] Checking table columns...")
        columns = await pool.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'isolation_test'
            ORDER BY ordinal_position
        """)

        print("  Columns:")
        for col in columns:
            print(f"    - {col['column_name']:15} {col['data_type']}")

        print("\n" + "=" * 70)
        print("✅ isolation_test table fixed successfully!")
        print("=" * 70)
        print("\nYou can now run the benchmark tests again.")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

    finally:
        await pool.close_pool()


if __name__ == '__main__':
    success = asyncio.run(fix_isolation_table())
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Drop all benchmark tables to allow fresh data load.

Usage:
    python cleanup_tables.py
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import DatabaseConfig
from src.database import DatabasePool


async def cleanup_tables(pool: DatabasePool):
    """Drop all benchmark tables."""
    print(f"\nDropping tables on {pool.config.name}...")

    tables = [
        'pgbench_history',
        'pgbench_accounts',
        'pgbench_tellers',
        'pgbench_branches',
        'isolation_test',
    ]

    # Add bench_events_1 through bench_events_16
    for i in range(1, 17):
        tables.append(f'bench_events_{i}')

    for table in tables:
        try:
            await pool.execute(f'DROP TABLE IF EXISTS {table} CASCADE;')
            print(f"  ✅ Dropped {table}")
        except Exception as e:
            print(f"  ⚠️  Could not drop {table}: {e}")

    print(f"\n✅ Cleanup complete on {pool.config.name}")


async def main():
    """Main entry point."""
    # Read connection string
    conn_file = Path('crdb_connection.txt')
    if not conn_file.exists():
        print("❌ Error: crdb_connection.txt not found")
        sys.exit(1)

    connection_string = conn_file.read_text().strip()
    if not connection_string:
        print("❌ Error: crdb_connection.txt is empty")
        sys.exit(1)

    print("=" * 70)
    print("CLEANUP BENCHMARK TABLES")
    print("=" * 70)

    # Create config and pool
    config = DatabaseConfig(
        connection_string=connection_string,
        database_type='cockroachdb',
        name='CockroachDB',
    )

    pool = DatabasePool(config)

    try:
        await pool.create_pool(min_size=1, max_size=2)
        await cleanup_tables(pool)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    finally:
        await pool.close_pool()

    print("\n" + "=" * 70)
    print("You can now run: python benchmark.py")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

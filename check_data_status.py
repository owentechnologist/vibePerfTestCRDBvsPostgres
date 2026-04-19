#!/usr/bin/env python3
"""
Check data loading status for CockroachDB benchmark tables.

This utility checks how much data has been loaded into the database
and reports which tables are complete, incomplete, or empty.

Usage:
    python check_data_status.py
    python check_data_status.py --crdb "postgresql://..."
"""

import asyncio
import argparse
from pathlib import Path

from src.config import DatabaseConfig
from src.database import DatabasePool
from src.data_loader import DataLoader


async def check_status(connection_string: str):
    """
    Check and display data loading status.

    Args:
        connection_string: Database connection string
    """
    print("\n" + "=" * 70)
    print("DATA LOADING STATUS CHECK")
    print("=" * 70)

    # Create database pool
    config = DatabaseConfig(
        connection_string=connection_string,
        database_type='cockroachdb',
        name='CockroachDB',
    )

    pool = DatabasePool(config)

    try:
        # Connect
        print("\nConnecting to database...")
        await pool.create_pool(min_size=1, max_size=5)
        version = await pool.get_version()
        print(f"✅ Connected: {version}")

        # Check status
        loader = DataLoader(pool)
        await loader.print_loading_status()

        print("\nTo resume loading, run:")
        print("  python benchmark.py --crdb <connection_string>")
        print("\nOr to check individual tables:")
        print("  python -c 'from src.database import *; from src.data_loader import *; asyncio.run(...)'")

    finally:
        await pool.close_pool()


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Check data loading status for benchmark tables',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--crdb',
        required=False,
        metavar='URL',
        help='CockroachDB connection string (default: read from crdb_connection.txt)'
    )

    args = parser.parse_args()

    # If --crdb not provided, try to read from crdb_connection.txt
    if not args.crdb:
        conn_file = Path('crdb_connection.txt')
        if conn_file.exists():
            try:
                connection_string = conn_file.read_text().strip()
                if connection_string:
                    args.crdb = connection_string
                    print(f"✅ Using connection from crdb_connection.txt")
                else:
                    print("⚠️  crdb_connection.txt exists but is empty")
            except Exception as e:
                print(f"⚠️  Could not read crdb_connection.txt: {e}")

    if not args.crdb:
        parser.error('Connection string required. Either pass --crdb or create crdb_connection.txt')

    return args


async def main():
    """Main entry point."""
    args = parse_arguments()
    await check_status(args.crdb)


if __name__ == '__main__':
    asyncio.run(main())

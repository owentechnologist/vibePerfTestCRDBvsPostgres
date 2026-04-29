"""
Configuration management for PostgreSQL benchmark.

Handles CLI argument parsing, connection string validation, and database
configuration for both CockroachDB and Azure PostgreSQL.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


@dataclass
class DatabaseConfig:
    """Configuration for a single database connection."""

    connection_string: str
    database_type: str  # 'cockroachdb' or 'postgresql'
    name: str  # Human-readable name for display

    # Connection pool settings (can be overridden per test)
    default_pool_min: int = 1
    default_pool_max: int = 10

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.connection_string:
            raise ValueError("Connection string cannot be empty")

        if self.database_type not in ['cockroachdb', 'postgresql']:
            raise ValueError(f"Invalid database type: {self.database_type}")

        # Validate connection string format
        if not self.is_valid_connection_string(self.connection_string):
            raise ValueError(f"Invalid PostgreSQL connection string for {self.name}")

    @staticmethod
    def is_valid_connection_string(conn_str: str) -> bool:
        """
        Validate PostgreSQL connection string format.

        Expected format: postgresql://user:pass@host:port/database?params

        Args:
            conn_str: Connection string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = urlparse(conn_str)

            # Check scheme
            if parsed.scheme not in ['postgresql', 'postgres']:
                return False

            # Check required components
            if not parsed.hostname:
                return False

            if not parsed.path or len(parsed.path) <= 1:
                # Path should be /database_name
                return False

            return True

        except Exception:
            return False

    def get_host(self) -> str:
        """Extract hostname from connection string."""
        parsed = urlparse(self.connection_string)
        return parsed.hostname or ""

    def get_port(self) -> int:
        """Extract port from connection string."""
        parsed = urlparse(self.connection_string)
        # Default ports: CockroachDB=26257, PostgreSQL=5432
        if parsed.port:
            return parsed.port
        return 26257 if self.database_type == 'cockroachdb' else 5432

    def get_database(self) -> str:
        """Extract database name from connection string."""
        parsed = urlparse(self.connection_string)
        # Remove leading slash
        return parsed.path.lstrip('/') if parsed.path else ""

    def get_user(self) -> str:
        """Extract username from connection string."""
        parsed = urlparse(self.connection_string)
        return parsed.username or ""

    @classmethod
    def from_connection_string(cls, conn_str: str, db_type: str, name: str) -> 'DatabaseConfig':
        """
        Create DatabaseConfig from connection string.

        Args:
            conn_str: PostgreSQL connection string
            db_type: 'cockroachdb' or 'postgresql'
            name: Human-readable name

        Returns:
            DatabaseConfig instance
        """
        return cls(
            connection_string=conn_str,
            database_type=db_type,
            name=name
        )


@dataclass
class BenchmarkConfig:
    """Overall benchmark configuration."""

    cockroachdb: DatabaseConfig
    postgresql: DatabaseConfig
    skip_load: bool = False
    output_dir: Path = Path('./outputs')

    def __post_init__(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)


def parse_arguments() -> Tuple[BenchmarkConfig, argparse.Namespace]:
    """
    Parse command-line arguments for benchmark.py.

    Returns:
        Tuple of (BenchmarkConfig, Namespace with additional args)
    """
    parser = argparse.ArgumentParser(
        description='PostgreSQL Database Performance Benchmark',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run full benchmark with data loading
  %(prog)s \\
    --crdb "postgresql://user:pass@crdb-host:26257/perftest?sslmode=require" \\
    --pg "postgresql://user:pass@pg-host:5432/perftest?sslmode=require"

  # Skip data loading (tables already populated)
  %(prog)s --crdb <conn> --pg <conn> --skip-load

  # Custom output directory
  %(prog)s --crdb <conn> --pg <conn> --output-dir /tmp/benchmark-results

Connection String Format:
  postgresql://username:password@hostname:port/database?sslmode=require

  CockroachDB example:
    postgresql://perftest_user:pass@perftest-crdb.eastus.cockroachlabs.cloud:26257/perftest?sslmode=require

  Azure PostgreSQL Flexible Server example:
    postgresql://dbuser:pass@server.postgres.database.azure.com:5432/postgres?sslmode=require

  Note: Azure Flexible Server uses the 'perftest' schema within the default database.
        The benchmark automatically creates and uses this schema.
        '''
    )

    # Required arguments
    parser.add_argument(
        '--crdb',
        type=str,
        required=True,
        dest='cockroachdb_connection',
        metavar='CONNECTION_STRING',
        help='CockroachDB connection string (postgresql://...)'
    )

    parser.add_argument(
        '--pg',
        type=str,
        required=True,
        dest='postgresql_connection',
        metavar='CONNECTION_STRING',
        help='Azure PostgreSQL connection string (postgresql://...)'
    )

    # Optional arguments
    parser.add_argument(
        '--skip-load',
        action='store_true',
        help='Skip data loading phase (use if tables already populated)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./outputs',
        help='Directory for output files (default: ./outputs)'
    )

    # Advanced options
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Query timeout in seconds for OLAP tests (default: 600)'
    )

    parser.add_argument(
        '--reduced-scale',
        action='store_true',
        help='Use reduced scale for testing (10k rows instead of 5M)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Validate and create database configs
    try:
        # Auto-detect database type from connection string
        # CockroachDB typically uses port 26257 or has 'cockroachlabs.cloud' in hostname
        crdb_type = 'cockroachdb'
        pg_type = 'postgresql'

        crdb_config = DatabaseConfig.from_connection_string(
            args.cockroachdb_connection,
            crdb_type,
            'CockroachDB Advanced'
        )

        pg_config = DatabaseConfig.from_connection_string(
            args.postgresql_connection,
            pg_type,
            'Azure PostgreSQL Flexible'
        )

        benchmark_config = BenchmarkConfig(
            cockroachdb=crdb_config,
            postgresql=pg_config,
            skip_load=args.skip_load,
            output_dir=Path(args.output_dir)
        )

        return benchmark_config, args

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


def validate_connection_string(conn_str: str, db_type: str) -> bool:
    """
    Validate connection string and provide helpful error messages.

    Args:
        conn_str: Connection string to validate
        db_type: 'cockroachdb' or 'postgresql'

    Returns:
        True if valid, raises ValueError otherwise
    """
    if not conn_str:
        raise ValueError(f"{db_type} connection string is required")

    if not DatabaseConfig.is_valid_connection_string(conn_str):
        raise ValueError(
            f"Invalid {db_type} connection string.\n"
            f"Expected format: postgresql://user:pass@host:port/database?sslmode=require\n"
            f"Got: {conn_str[:50]}..."
        )

    # Check SSL mode (recommended for production)
    if 'sslmode=require' not in conn_str and 'sslmode=verify-full' not in conn_str:
        print(
            f"Warning: {db_type} connection string does not specify SSL mode.\n"
            f"Recommended: Add ?sslmode=require to your connection string.",
            file=sys.stderr
        )

    return True


def get_default_pool_config(test_name: str) -> dict:
    """
    Get recommended connection pool configuration for a test.

    Args:
        test_name: Name of test (e.g., 'test_1', 'test_2', etc.)

    Returns:
        Dict with min_size and max_size
    """
    pool_configs = {
        'test_1': {'min_size': 1, 'max_size': 2},      # Serial SELECT 1
        'test_2': {'min_size': 8, 'max_size': 8},      # 8 concurrent workers
        'test_3': {'min_size': 16, 'max_size': 16},    # 16 concurrent pgbench
        'test_4': {'min_size': 1, 'max_size': 2},      # Serial OLAP
        'test_5': {'min_size': 1, 'max_size': 2},      # Serial OLAP
        'test_6': {'min_size': 1, 'max_size': 2},      # Serial OLAP
        'test_7': {'min_size': 2, 'max_size': 2},      # 2 connections for isolation test
        'test_8': {'min_size': 2, 'max_size': 2},      # 2 connections for isolation test
    }

    return pool_configs.get(test_name, {'min_size': 1, 'max_size': 10})


if __name__ == '__main__':
    # Test configuration parsing
    print("Configuration module loaded successfully")
    print("\nExample usage:")
    print("  from src.config import parse_arguments, DatabaseConfig")
    print("  config, args = parse_arguments()")

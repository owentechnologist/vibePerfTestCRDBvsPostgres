#!/usr/bin/env python3
"""
PostgreSQL Performance Benchmark Tool

Benchmarks CockroachDB Advanced vs Azure PostgreSQL Flexible Server
across 8 different test scenarios (OLTP, OLAP, isolation tests).

Usage:
    python benchmark.py \\
        --crdb "postgresql://user:pass@crdb-host:26257/dbname?sslmode=require" \\
        --pg "postgresql://user:pass@pg-host:5432/dbname?sslmode=require" \\
        --output-dir ./outputs

    python benchmark.py --help
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import DatabaseConfig
from src.database import DatabasePool
from src.schema import SchemaManager
from src.data_loader import DataLoader
from src.test_runner import TestRunner
from src.output.json_writer import write_json_results
from src.output.text_summary import write_text_summary, generate_text_summary
from src.output.html_generator import generate_html_dashboard


class BenchmarkRunner:
    """
    Main benchmark orchestrator.

    Coordinates schema creation, data loading, test execution, and output generation.
    """

    def __init__(self, args):
        """
        Initialize benchmark runner.

        Args:
            args: Parsed command-line arguments
        """
        self.args = args

        # Database pools (initialized in run())
        self.crdb_pool = None
        self.pg_pool = None

        # Output directory
        self.output_dir = Path(args.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> int:
        """
        Run the complete benchmark workflow.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        print("\n" + "=" * 70)
        print("POSTGRESQL PERFORMANCE BENCHMARK")
        print("=" * 70)

        # Determine which databases are being tested
        db_names = []
        if self.args.crdb:
            db_names.append("CockroachDB Advanced")
        if self.args.pg:
            db_names.append("Azure PostgreSQL Flexible Server")

        print(f"\n{' vs '.join(db_names)}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Output Directory: {self.output_dir.absolute()}")

        try:
            # Step 1: Create database pools
            print("\n" + "-" * 70)
            print("Step 1: Connecting to Databases")
            print("-" * 70)

            await self._create_pools()

            # Step 2: Create schemas
            print("\n" + "-" * 70)
            print("Step 2: Creating Database Schemas")
            print("-" * 70)

            await self._create_schemas()

            # Step 3: Load data (if not skipped)
            if not self.args.skip_load:
                print("\n" + "-" * 70)
                print("Step 3: Loading Test Data")
                print("-" * 70)

                await self._load_data()

                # Step 3.5: Create indexes after data load
                print("\n" + "-" * 70)
                print("Step 3.5: Creating Indexes (Post-Load)")
                print("-" * 70)

                await self._create_indexes()
            else:
                print("\n" + "-" * 70)
                print("Step 3: Skipping Data Load (--skip-load)")
                print("-" * 70)

            # Step 4: Run tests
            print("\n" + "-" * 70)
            print("Step 4: Executing Performance Tests")
            print("-" * 70)

            results = await self._run_tests()

            # Step 5: Generate outputs
            print("\n" + "-" * 70)
            print("Step 5: Generating Output Files")
            print("-" * 70)

            self._generate_outputs(results)

            # Step 6: Print summary
            print("\n" + "-" * 70)
            print("Step 6: Summary")
            print("-" * 70)

            self._print_summary(results)

            print("\n" + "=" * 70)
            print("✅ BENCHMARK COMPLETED SUCCESSFULLY")
            print("=" * 70)

            return 0

        except KeyboardInterrupt:
            print("\n\n⚠️  Benchmark interrupted by user (Ctrl+C)")
            return 130

        except Exception as e:
            print(f"\n\n❌ BENCHMARK FAILED")
            print(f"Error: {type(e).__name__}: {e}")

            if self.args.verbose:
                import traceback
                print("\nFull traceback:")
                traceback.print_exc()

            return 1

        finally:
            # Cleanup
            await self._cleanup()

    async def _create_pools(self):
        """Create database connection pools."""
        crdb_failed = False
        pg_failed = False
        crdb_error = None
        pg_error = None

        # CockroachDB pool (if provided)
        if self.args.crdb:
            print("\n[CockroachDB] Creating connection pool...")
            try:
                crdb_config = DatabaseConfig(
                    connection_string=self.args.crdb,
                    database_type='cockroachdb',
                    name='CockroachDB',
                )

                self.crdb_pool = DatabasePool(crdb_config)
                await self.crdb_pool.create_pool(min_size=5, max_size=20)
                version = await self.crdb_pool.get_version()
                print(f"✅ Connected to CockroachDB: {version}")
            except Exception as e:
                crdb_failed = True
                crdb_error = e
                self.crdb_pool = None
                print(f"❌ Failed to connect to CockroachDB: {type(e).__name__}: {e}")
        else:
            print("\n[CockroachDB] Skipped (no connection string provided)")
            self.crdb_pool = None

        # Azure PostgreSQL pool (if provided)
        if self.args.pg:
            print("\n[Azure PG] Creating connection pool...")
            try:
                pg_config = DatabaseConfig(
                    connection_string=self.args.pg,
                    database_type='postgresql',
                    name='Azure PostgreSQL',
                )

                self.pg_pool = DatabasePool(pg_config)
                await self.pg_pool.create_pool(min_size=5, max_size=20)
                version = await self.pg_pool.get_version()
                print(f"✅ Connected to Azure PostgreSQL: {version}")
            except Exception as e:
                pg_failed = True
                pg_error = e
                self.pg_pool = None
                print(f"❌ Failed to connect to Azure PostgreSQL: {type(e).__name__}: {e}")
        else:
            print("\n[Azure PG] Skipped (no connection string provided)")
            self.pg_pool = None

        # Handle connection failures
        await self._handle_connection_failures(crdb_failed, pg_failed, crdb_error, pg_error)

    async def _handle_connection_failures(self, crdb_failed, pg_failed, crdb_error, pg_error):
        """
        Handle connection failures and prompt user to continue or exit.

        Args:
            crdb_failed: Whether CockroachDB connection failed
            pg_failed: Whether PostgreSQL connection failed
            crdb_error: CockroachDB connection error (if any)
            pg_error: PostgreSQL connection error (if any)
        """
        # Both connections succeeded - continue
        if not crdb_failed and not pg_failed:
            return

        # Both connections failed - exit
        if (self.args.crdb and crdb_failed) and (self.args.pg and pg_failed):
            print("\n" + "=" * 70)
            print("❌ CONNECTION FAILURE - NO DATABASES AVAILABLE")
            print("=" * 70)
            print("\nBoth database connections failed. Cannot proceed with benchmarking.")
            print("\nCockroachDB Error:")
            print(f"  {type(crdb_error).__name__}: {crdb_error}")
            print("\nAzure PostgreSQL Error:")
            print(f"  {type(pg_error).__name__}: {pg_error}")
            print("\nPlease verify:")
            print("  - Connection strings are correct")
            print("  - Databases are running and accessible")
            print("  - Network connectivity is working")
            print("  - Firewall rules allow your IP address")
            print("=" * 70)
            raise RuntimeError("No database connections available")

        # Only one connection failed - ask user if they want to continue
        if crdb_failed or pg_failed:
            failed_db = "CockroachDB" if crdb_failed else "Azure PostgreSQL"
            working_db = "Azure PostgreSQL" if crdb_failed else "CockroachDB"
            error = crdb_error if crdb_failed else pg_error

            print("\n" + "=" * 70)
            print(f"⚠️  WARNING - {failed_db.upper()} CONNECTION FAILED")
            print("=" * 70)
            print(f"\n{failed_db} connection failed:")
            print(f"  {type(error).__name__}: {error}")
            print(f"\n{working_db} connection succeeded.")
            print(f"\nYou can continue benchmarking with only {working_db},")
            print(f"but comparison results will not be available.")
            print(f"\nDo you want to continue with only {working_db}?")

            # Prompt user for input
            try:
                response = input("\nContinue? [y/N]: ").strip().lower()
                if response not in ['y', 'yes']:
                    print("\n❌ Benchmark cancelled by user")
                    raise RuntimeError(f"User cancelled benchmark due to {failed_db} connection failure")
                else:
                    print(f"\n✅ Continuing with {working_db} only...")
            except EOFError:
                # Non-interactive mode or input redirected
                print("\n⚠️  Non-interactive mode detected, cannot prompt user")
                print(f"❌ Exiting due to {failed_db} connection failure")
                raise RuntimeError(f"{failed_db} connection failed in non-interactive mode")

    async def _create_schemas(self):
        """Create database schemas on configured databases."""
        # CockroachDB
        if self.crdb_pool:
            print("\n[CockroachDB] Creating schema...")
            crdb_schema = SchemaManager()
            await crdb_schema.create_all_tables(self.crdb_pool)
            print("✅ CockroachDB schema ready")
        else:
            print("\n[CockroachDB] Skipped (not configured)")

        # Azure PostgreSQL
        if self.pg_pool:
            print("\n[Azure PG] Creating schema...")
            pg_schema = SchemaManager()
            await pg_schema.create_all_tables(self.pg_pool)
            print("✅ Azure PostgreSQL schema ready")
        else:
            print("\n[Azure PG] Skipped (not configured)")

    async def _load_data(self):
        """Load test data into configured databases."""
        # CockroachDB
        if self.crdb_pool:
            print("\n[CockroachDB] Loading test data...")
            print("  This may take 10-30 minutes depending on hardware...")
            crdb_loader = DataLoader(self.crdb_pool)
            await crdb_loader.load_all_data()
            print("✅ CockroachDB data loaded")
        else:
            print("\n[CockroachDB] Skipped (not configured)")

        # Azure PostgreSQL
        if self.pg_pool:
            print("\n[Azure PG] Loading test data...")
            print("  This may take 10-30 minutes depending on hardware...")
            pg_loader = DataLoader(self.pg_pool)
            await pg_loader.load_all_data()
            print("✅ Azure PostgreSQL data loaded")
        else:
            print("\n[Azure PG] Skipped (not configured)")

    async def _create_indexes(self):
        """Create indexes after data is loaded (for performance)."""
        # CockroachDB
        if self.crdb_pool:
            print("\n[CockroachDB] Creating indexes...")
            print("  Creating indexes after bulk load is much faster than during inserts...")
            crdb_schema = SchemaManager()
            await crdb_schema.create_all_indexes(self.crdb_pool)
            print("✅ CockroachDB indexes created")
        else:
            print("\n[CockroachDB] Skipped (not configured)")

        # Azure PostgreSQL
        if self.pg_pool:
            print("\n[Azure PG] Creating indexes...")
            print("  Creating indexes after bulk load is much faster than during inserts...")
            pg_schema = SchemaManager()
            await pg_schema.create_all_indexes(self.pg_pool)
            print("✅ Azure PostgreSQL indexes created")
        else:
            print("\n[Azure PG] Skipped (not configured)")

    async def _run_tests(self):
        """Run all performance tests."""
        print("\n[Test Runner] Executing all 10 tests on both databases...")
        print("  Expected duration: 5-30 minutes")

        runner = TestRunner(self.crdb_pool, self.pg_pool)
        results = await runner.run_all_tests()

        return results

    def _generate_outputs(self, results):
        """Generate all output files."""
        # JSON output
        json_path = self.output_dir / 'benchmark_results.json'
        write_json_results(results, str(json_path))

        # Text summary
        text_path = self.output_dir / 'benchmark_summary.txt'
        write_text_summary(results, str(text_path))

        # HTML dashboard
        html_path = self.output_dir / 'benchmark_report.html'
        try:
            generate_html_dashboard(results, str(html_path))
        except ImportError as e:
            print(f"\n⚠️  HTML dashboard skipped (jinja2 not installed): {e}")
            print("   Install with: pip install jinja2")

        print(f"\n✅ Output files generated:")
        print(f"   📄 JSON:  {json_path}")
        print(f"   📄 Text:  {text_path}")
        if html_path.exists():
            print(f"   📄 HTML:  {html_path}")
            print(f"      Open in browser: file://{html_path.absolute()}")

    def _print_summary(self, results):
        """Print summary to console."""
        summary_text = generate_text_summary(results)
        print("\n" + summary_text)

    async def _cleanup(self):
        """Cleanup database connections."""
        print("\n[Cleanup] Closing database connections...")

        if self.crdb_pool:
            try:
                await self.crdb_pool.close_pool()
                print("✅ CockroachDB connection closed")
            except Exception as e:
                print(f"⚠️  Error closing CockroachDB connection: {e}")

        if self.pg_pool:
            try:
                await self.pg_pool.close_pool()
                print("✅ Azure PostgreSQL connection closed")
            except Exception as e:
                print(f"⚠️  Error closing PostgreSQL connection: {e}")


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='PostgreSQL Performance Benchmark: CockroachDB vs Azure PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use saved connection from crdb_connection.txt
  python benchmark.py

  # Full benchmark with both databases
  python benchmark.py \\
    --crdb "postgresql://user:pass@crdb-host:26257/perftest?sslmode=require" \\
    --pg "postgresql://user:pass@pg-host:5432/perftest?sslmode=require"

  # Test only CockroachDB
  python benchmark.py --crdb <url>

  # Test only Azure PostgreSQL
  python benchmark.py --pg <url>

  # Skip data loading (data already loaded)
  python benchmark.py --crdb <url> --pg <url> --skip-load

  # Custom output directory
  python benchmark.py --crdb <url> --output-dir ./results

Connection String Format:
  postgresql://username:password@host:port/database?sslmode=require

For more information, see README.md
        """
    )

    parser.add_argument(
        '--crdb',
        required=False,
        metavar='URL',
        help='CockroachDB connection string (default: read from crdb_connection.txt)'
    )

    parser.add_argument(
        '--pg',
        required=False,
        metavar='URL',
        help='Azure PostgreSQL connection string (PostgreSQL URL format)'
    )

    parser.add_argument(
        '--skip-load',
        action='store_true',
        help='Skip data loading (assumes data already loaded)'
    )

    parser.add_argument(
        '--output-dir',
        default='./outputs',
        metavar='DIR',
        help='Output directory for results (default: ./outputs)'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output and full error tracebacks'
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
                    print(f"✅ Using CockroachDB connection from crdb_connection.txt")
                else:
                    print("⚠️  crdb_connection.txt exists but is empty")
            except Exception as e:
                print(f"⚠️  Could not read crdb_connection.txt: {e}")

    # If --pg not provided, try to read from azure_pg_connection.txt
    if not args.pg:
        conn_file = Path('azure_pg_connection.txt')
        if conn_file.exists():
            try:
                connection_string = conn_file.read_text().strip()
                if connection_string:
                    args.pg = connection_string
                    print(f"✅ Using Azure PostgreSQL connection from azure_pg_connection.txt")
                else:
                    print("⚠️  azure_pg_connection.txt exists but is empty")
            except Exception as e:
                print(f"⚠️  Could not read azure_pg_connection.txt: {e}")

    # Validate at least one database connection is provided
    if not args.crdb and not args.pg:
        parser.error('At least one database connection (--crdb or --pg) must be provided.\n'
                     'Either pass --crdb/--pg on command line or create connection files:\n'
                     '  - crdb_connection.txt for CockroachDB\n'
                     '  - azure_pg_connection.txt for Azure PostgreSQL')

    return args


async def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()

    # Run benchmark
    runner = BenchmarkRunner(args)
    exit_code = await runner.run()

    sys.exit(exit_code)


if __name__ == '__main__':
    # Run async main
    asyncio.run(main())

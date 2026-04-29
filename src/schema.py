"""
Database schema management for PostgreSQL benchmark.

Creates and validates all 21 tables required for the benchmark:
- 4 pgbench tables (TPC-B compatible)
- 16 bench_events tables (OLAP workloads)
- 1 isolation_test table

All DDL is idempotent (uses IF NOT EXISTS).
"""

from typing import List, Dict, Tuple
from src.database import DatabasePool


class SchemaManager:
    """
    Manages database schema creation and validation.

    Creates all tables required for the benchmark on both databases.
    """

    # pgbench-compatible tables (TPC-B standard)
    PGBENCH_BRANCHES_DDL = """
        CREATE TABLE IF NOT EXISTS pgbench_branches (
            bid      SERIAL PRIMARY KEY,
            bbalance INT  NOT NULL DEFAULT 0,
            filler   CHAR(88) NOT NULL DEFAULT ''
        );
    """

    PGBENCH_TELLERS_DDL = """
        CREATE TABLE IF NOT EXISTS pgbench_tellers (
            tid      SERIAL PRIMARY KEY,
            bid      INT  NOT NULL,
            tbalance INT  NOT NULL DEFAULT 0,
            filler   CHAR(84) NOT NULL DEFAULT ''
        );
    """

    PGBENCH_ACCOUNTS_DDL = """
        CREATE TABLE IF NOT EXISTS pgbench_accounts (
            aid      BIGSERIAL PRIMARY KEY,
            bid      INT  NOT NULL,
            abalance INT  NOT NULL DEFAULT 0,
            filler   CHAR(84) NOT NULL DEFAULT ''
        );
    """

    PGBENCH_HISTORY_DDL = """
        CREATE TABLE IF NOT EXISTS pgbench_history (
            tid    INT       NOT NULL,
            bid    INT       NOT NULL,
            aid    BIGINT    NOT NULL,
            delta  INT       NOT NULL,
            mtime  TIMESTAMP NOT NULL DEFAULT NOW(),
            filler CHAR(22)  DEFAULT NULL
        );
    """

    # Isolation test table
    ISOLATION_TEST_DDL = """
        CREATE TABLE IF NOT EXISTS isolation_test (
            id         BIGSERIAL PRIMARY KEY,
            test_value VARCHAR(100) NOT NULL,
            data       TEXT NOT NULL
        );
    """

    @staticmethod
    def get_bench_events_ddl(table_num: int) -> str:
        """
        Generate DDL for bench_events_N table.

        Args:
            table_num: Table number (1-16)

        Returns:
            CREATE TABLE statement
        """
        return f"""
            CREATE TABLE IF NOT EXISTS bench_events_{table_num} (
                id          BIGSERIAL    PRIMARY KEY,
                customer_id BIGINT       NOT NULL,
                session_id  UUID         NOT NULL DEFAULT gen_random_uuid(),
                event_type  VARCHAR(50)  NOT NULL,
                region      VARCHAR(20)  NOT NULL,
                amount      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                quantity    INT          NOT NULL DEFAULT 1,
                status      VARCHAR(20)  NOT NULL DEFAULT 'completed',
                tags        TEXT[],
                metadata    JSONB,
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
            );
        """

    @staticmethod
    def get_bench_events_indexes_ddl(table_num: int) -> List[str]:
        """
        Generate index DDL for bench_events_N table.

        Args:
            table_num: Table number (1-16)

        Returns:
            List of CREATE INDEX statements
        """
        return [
            f"CREATE INDEX IF NOT EXISTS idx_bench_events_{table_num}_customer ON bench_events_{table_num}(customer_id);",
            f"CREATE INDEX IF NOT EXISTS idx_bench_events_{table_num}_created ON bench_events_{table_num}(created_at);",
            f"CREATE INDEX IF NOT EXISTS idx_bench_events_{table_num}_region ON bench_events_{table_num}(region);",
        ]

    async def create_all_tables(self, pool: DatabasePool) -> Dict[str, bool]:
        """
        Create all tables on the database.

        Args:
            pool: DatabasePool instance

        Returns:
            Dict mapping table names to creation status (True if created/exists)
        """
        print(f"\n{'='*70}")
        print(f"Creating schema on {pool.config.name}")
        print(f"{'='*70}")

        results = {}

        # Create pgbench tables
        print("\n[1/3] Creating pgbench tables...")
        pgbench_tables = [
            ('pgbench_branches', self.PGBENCH_BRANCHES_DDL),
            ('pgbench_tellers', self.PGBENCH_TELLERS_DDL),
            ('pgbench_accounts', self.PGBENCH_ACCOUNTS_DDL),
            ('pgbench_history', self.PGBENCH_HISTORY_DDL),
        ]

        for table_name, ddl in pgbench_tables:
            try:
                await pool.execute(ddl)
                results[table_name] = True
                print(f"  ✅ {table_name}")
            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
                results[table_name] = False

        # Create bench_events tables (indexes will be created after data load)
        print("\n[2/3] Creating bench_events tables (1-16)...")
        for i in range(1, 17):
            table_name = f"bench_events_{i}"
            try:
                # Create table (without indexes for faster data loading)
                ddl = self.get_bench_events_ddl(i)
                await pool.execute(ddl)

                results[table_name] = True
                print(f"  ✅ {table_name}")
            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
                results[table_name] = False

        # Create isolation test table
        print("\n[3/3] Creating isolation_test table...")
        try:
            await pool.execute(self.ISOLATION_TEST_DDL)
            results['isolation_test'] = True
            print(f"  ✅ isolation_test")
        except Exception as e:
            print(f"  ❌ isolation_test: {e}")
            results['isolation_test'] = False

        # Summary
        total = len(results)
        success = sum(1 for v in results.values() if v)
        print(f"\n{'='*70}")
        print(f"Schema creation complete: {success}/{total} tables created")
        print(f"{'='*70}")

        return results

    async def create_all_indexes(self, pool: DatabasePool) -> Dict[str, bool]:
        """
        Create all indexes on bench_events tables.

        This should be called AFTER data loading is complete for optimal performance.
        Creating indexes after bulk data loading is much faster than maintaining
        indexes during inserts.

        Args:
            pool: DatabasePool instance

        Returns:
            Dict mapping table names to index creation status
        """
        print(f"\n{'='*70}")
        print(f"Creating indexes on {pool.config.name}")
        print(f"{'='*70}")

        results = {}

        print("\nCreating indexes on bench_events tables (1-16)...")
        print("  This will improve query performance for the benchmarks...")

        for i in range(1, 17):
            table_name = f"bench_events_{i}"
            try:
                # Create all indexes for this table
                index_ddls = self.get_bench_events_indexes_ddl(i)
                for index_ddl in index_ddls:
                    await pool.execute(index_ddl)

                results[table_name] = True
                print(f"  ✅ {table_name} (3 indexes created)")
            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
                results[table_name] = False

        # Summary
        total = len(results)
        success = sum(1 for v in results.values() if v)
        print(f"\n{'='*70}")
        print(f"Index creation complete: {success}/{total} tables indexed")
        print(f"{'='*70}")

        return results

    async def validate_schema(self, pool: DatabasePool) -> Tuple[bool, Dict[str, bool]]:
        """
        Validate that all required tables exist.

        Args:
            pool: DatabasePool instance

        Returns:
            Tuple of (all_exist, dict of table_name -> exists)
        """
        print(f"\n{'='*70}")
        print(f"Validating schema on {pool.config.name}")
        print(f"{'='*70}")

        expected_tables = [
            'pgbench_branches',
            'pgbench_tellers',
            'pgbench_accounts',
            'pgbench_history',
        ] + [f'bench_events_{i}' for i in range(1, 17)] + [
            'isolation_test'
        ]

        results = {}
        for table_name in expected_tables:
            exists = await pool.table_exists(table_name)
            results[table_name] = exists
            status = "✅" if exists else "❌"
            print(f"  {status} {table_name}")

        all_exist = all(results.values())

        print(f"\n{'='*70}")
        if all_exist:
            print(f"✅ All {len(expected_tables)} tables exist")
        else:
            missing = [k for k, v in results.items() if not v]
            print(f"❌ Missing {len(missing)} tables: {', '.join(missing)}")
        print(f"{'='*70}")

        return all_exist, results

    async def get_table_row_counts(self, pool: DatabasePool) -> Dict[str, int]:
        """
        Get row counts for all tables.

        Args:
            pool: DatabasePool instance

        Returns:
            Dict mapping table names to row counts
        """
        print(f"\n{'='*70}")
        print(f"Checking row counts on {pool.config.name}")
        print(f"{'='*70}")

        tables = [
            'pgbench_branches',
            'pgbench_tellers',
            'pgbench_accounts',
            'pgbench_history',
        ] + [f'bench_events_{i}' for i in range(1, 17)] + [
            'isolation_test'
        ]

        counts = {}
        for table_name in tables:
            try:
                count = await pool.get_table_count(table_name)
                counts[table_name] = count

                # Format count with commas
                count_str = f"{count:,}"
                print(f"  {table_name:25} {count_str:>15} rows")
            except Exception as e:
                print(f"  {table_name:25} Error: {e}")
                counts[table_name] = 0

        # Calculate totals
        total_rows = sum(counts.values())
        print(f"\n  {'TOTAL':25} {total_rows:>15,} rows")
        print(f"{'='*70}")

        return counts

    async def drop_all_tables(self, pool: DatabasePool, confirm: bool = False) -> bool:
        """
        Drop all benchmark tables (DESTRUCTIVE).

        Args:
            pool: DatabasePool instance
            confirm: Must be True to actually drop tables

        Returns:
            True if successful
        """
        if not confirm:
            print("⚠️  drop_all_tables() requires confirm=True to proceed")
            return False

        print(f"\n{'='*70}")
        print(f"⚠️  DROPPING ALL TABLES on {pool.config.name}")
        print(f"{'='*70}")

        tables = [
            'pgbench_history',  # Drop in reverse order (no FK constraints, but good practice)
            'pgbench_accounts',
            'pgbench_tellers',
            'pgbench_branches',
        ] + [f'bench_events_{i}' for i in range(1, 17)] + [
            'isolation_test'
        ]

        for table_name in tables:
            try:
                await pool.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
                print(f"  ✅ Dropped {table_name}")
            except Exception as e:
                print(f"  ❌ Failed to drop {table_name}: {e}")

        print(f"{'='*70}")
        print("⚠️  All tables dropped")
        print(f"{'='*70}")

        return True

    async def check_data_loaded(self, pool: DatabasePool) -> bool:
        """
        Check if data appears to be already loaded.

        Checks if pgbench_accounts has rows - if so, assumes data is loaded.

        Args:
            pool: DatabasePool instance

        Returns:
            True if data appears loaded
        """
        try:
            count = await pool.get_table_count('pgbench_accounts')
            if count > 0:
                print(f"  ℹ️  pgbench_accounts has {count:,} rows - data appears loaded")
                return True
            return False
        except Exception:
            return False


async def test_schema_creation():
    """
    Test schema creation (requires database connection).

    This is a placeholder - actual testing requires live database connections.
    """
    print("Schema module loaded successfully")
    print("\nTo test schema creation, use:")
    print("  from src.database import DatabasePool")
    print("  from src.config import DatabaseConfig")
    print("  from src.schema import SchemaManager")
    print()
    print("  config = DatabaseConfig(...)")
    print("  pool = DatabasePool(config)")
    print("  await pool.create_pool()")
    print()
    print("  schema = SchemaManager()")
    print("  await schema.create_all_tables(pool)")
    print("  await schema.validate_schema(pool)")
    print("  await schema.get_table_row_counts(pool)")


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_schema_creation())

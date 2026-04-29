"""
Data loading for PostgreSQL benchmark.

Loads test data into all 21 tables:
- pgbench tables: 50k branches, 500k tellers, 5M accounts
- bench_events tables: 5M rows × 16 tables
- isolation_test: 10k rows

Uses batch inserts (10k rows) with concurrent workers and progress bars.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Any
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)

from src.database import DatabasePool


class DataLoader:
    """
    Manages test data loading for benchmark tables.

    Uses batch inserts with concurrent workers for efficiency.
    """

    # Batch size for inserts
    BATCH_SIZE = 10_000

    # Number of concurrent workers
    CONCURRENT_WORKERS = 6

    # Data generation parameters
    EVENT_TYPES = ['purchase', 'refund', 'view', 'click', 'signup', 'login', 'checkout', 'search']
    REGIONS = ['eastus', 'westus', 'northeurope', 'southeastasia', 'australiaeast']
    STATUSES = ['completed', 'pending', 'failed', 'cancelled']

    def __init__(self, pool: DatabasePool):
        """
        Initialize data loader.

        Args:
            pool: DatabasePool instance
        """
        self.pool = pool

    async def get_table_status(self) -> dict:
        """
        Check loading status of all tables.

        Returns:
            Dict with table status info including expected counts, actual counts, and completion status
        """
        expected_counts = {
            'pgbench_branches': 50_000,
            'pgbench_tellers': 500_000,
            'pgbench_accounts': 5_000_000,
            'isolation_test': 10_000,
        }

        # Add bench_events tables
        for i in range(1, 17):
            expected_counts[f'bench_events_{i}'] = 5_000_000

        status = {}
        for table_name, expected_count in expected_counts.items():
            actual_count = await self.pool.get_table_count(table_name)
            status[table_name] = {
                'expected': expected_count,
                'actual': actual_count,
                'complete': actual_count >= expected_count,
                'percentage': (actual_count / expected_count * 100) if expected_count > 0 else 0
            }

        return status

    async def load_all_data(self, skip_if_exists: bool = True) -> None:
        """
        Load all test data with resume capability.

        Args:
            skip_if_exists: Skip loading tables that are already complete
        """
        print(f"\n{'='*70}")
        print(f"Loading test data on {self.pool.config.name}")
        print(f"{'='*70}")

        # Check current status of all tables
        if skip_if_exists:
            print(f"\nChecking current data loading status...")
            status = await self.get_table_status()

            # Print summary
            complete_tables = [name for name, info in status.items() if info['complete']]
            incomplete_tables = [name for name, info in status.items() if not info['complete']]

            if len(complete_tables) == len(status):
                print(f"\n✅ All {len(status)} tables already fully loaded")
                print("   Use --skip-load flag or manually drop tables to reload")
                return
            elif len(complete_tables) > 0:
                print(f"\n📊 Data loading status:")
                print(f"   ✅ Complete: {len(complete_tables)}/{len(status)} tables")
                print(f"   ⚠️  Incomplete: {len(incomplete_tables)} tables")
                print(f"\n   Resuming load for incomplete tables...")

                # Show which tables need loading
                for table_name in incomplete_tables:
                    info = status[table_name]
                    print(f"      {table_name}: {info['actual']:,}/{info['expected']:,} rows ({info['percentage']:.1f}%)")

        # Load all data with resume support
        await self.load_pgbench_data()
        await self.load_all_bench_events()
        await self.load_isolation_data()

        print(f"\n{'='*70}")
        print("✅ All test data loaded successfully")
        print(f"{'='*70}")

    async def load_pgbench_data(self) -> None:
        """
        Load pgbench tables (TPC-B standard scale) with resume support.

        - pgbench_branches: 50,000 rows
        - pgbench_tellers: 500,000 rows
        - pgbench_accounts: 5,000,000 rows
        - pgbench_history: starts empty
        """
        print(f"\n{'='*70}")
        print("Loading pgbench tables")
        print(f"{'='*70}")

        # Load branches (50k rows)
        await self._load_pgbench_branches(50_000)

        # Load tellers (500k rows)
        await self._load_pgbench_tellers(500_000)

        # Load accounts (5M rows)
        await self._load_pgbench_accounts(5_000_000)

        print("\n✅ pgbench tables loaded")

    async def _load_pgbench_branches(self, total_rows: int) -> None:
        """Load pgbench_branches table with resume support."""
        current_count = await self.pool.get_table_count('pgbench_branches')

        if current_count >= total_rows:
            print(f"\n[1/3] pgbench_branches already complete ({current_count:,}/{total_rows:,} rows) ✅")
            return

        print(f"\n[1/3] Loading pgbench_branches ({current_count:,}/{total_rows:,} rows - resuming)...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Inserting branches...", total=total_rows, completed=current_count)

            # Resume from where we left off
            for start in range(current_count, total_rows, self.BATCH_SIZE):
                batch_size = min(self.BATCH_SIZE, total_rows - start)
                batch = self._generate_branches_batch(start + 1, batch_size)

                # Insert batch
                await self._insert_batch('pgbench_branches', ['bid', 'bbalance', 'filler'], batch)

                progress.update(task, advance=batch_size)

        print(f"  ✅ {total_rows:,} branches inserted")

    def _generate_branches_batch(self, start_id: int, count: int) -> List[Tuple[Any, ...]]:
        """Generate batch of branch records."""
        return [
            (start_id + i, 0, '')  # bid, bbalance, filler
            for i in range(count)
        ]

    async def _load_pgbench_tellers(self, total_rows: int) -> None:
        """Load pgbench_tellers table with resume support."""
        current_count = await self.pool.get_table_count('pgbench_tellers')

        if current_count >= total_rows:
            print(f"\n[2/3] pgbench_tellers already complete ({current_count:,}/{total_rows:,} rows) ✅")
            return

        print(f"\n[2/3] Loading pgbench_tellers ({current_count:,}/{total_rows:,} rows - resuming)...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Inserting tellers...", total=total_rows, completed=current_count)

            for start in range(current_count, total_rows, self.BATCH_SIZE):
                batch_size = min(self.BATCH_SIZE, total_rows - start)
                batch = self._generate_tellers_batch(start + 1, batch_size)

                await self._insert_batch('pgbench_tellers', ['tid', 'bid', 'tbalance', 'filler'], batch)

                progress.update(task, advance=batch_size)

        print(f"  ✅ {total_rows:,} tellers inserted")

    def _generate_tellers_batch(self, start_id: int, count: int) -> List[Tuple[Any, ...]]:
        """Generate batch of teller records."""
        return [
            (
                start_id + i,              # tid
                random.randint(1, 50_000), # bid (branch id)
                0,                         # tbalance
                ''                         # filler
            )
            for i in range(count)
        ]

    async def _load_pgbench_accounts(self, total_rows: int) -> None:
        """Load pgbench_accounts table (5M rows) with resume support."""
        current_count = await self.pool.get_table_count('pgbench_accounts')

        if current_count >= total_rows:
            print(f"\n[3/3] pgbench_accounts already complete ({current_count:,}/{total_rows:,} rows) ✅")
            return

        print(f"\n[3/3] Loading pgbench_accounts ({current_count:,}/{total_rows:,} rows - resuming)...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Inserting accounts...", total=total_rows, completed=current_count)

            for start in range(current_count, total_rows, self.BATCH_SIZE):
                batch_size = min(self.BATCH_SIZE, total_rows - start)
                batch = self._generate_accounts_batch(start + 1, batch_size)

                await self._insert_batch('pgbench_accounts', ['aid', 'bid', 'abalance', 'filler'], batch)

                progress.update(task, advance=batch_size)

        print(f"  ✅ {total_rows:,} accounts inserted")

    def _generate_accounts_batch(self, start_id: int, count: int) -> List[Tuple[Any, ...]]:
        """Generate batch of account records."""
        return [
            (
                start_id + i,              # aid
                random.randint(1, 50_000), # bid (branch id)
                0,                         # abalance
                ''                         # filler
            )
            for i in range(count)
        ]

    async def load_all_bench_events(self) -> None:
        """
        Load all 16 bench_events tables (5M rows each).

        Uses concurrent workers for efficiency.
        """
        print(f"\n{'='*70}")
        print("Loading bench_events tables (1-16)")
        print(f"{'='*70}")

        # Limit concurrent table loads to prevent pool exhaustion
        # With pool_size=20 and 6 workers per table, load 3 tables at a time (18 connections)
        max_concurrent_tables = 3
        semaphore = asyncio.Semaphore(max_concurrent_tables)

        async def load_with_semaphore(table_num: int):
            async with semaphore:
                await self.load_bench_events(table_num)

        # Load all 16 tables with concurrency control
        tasks = [
            load_with_semaphore(table_num)
            for table_num in range(1, 17)
        ]

        await asyncio.gather(*tasks)

        print("\n✅ All bench_events tables loaded (16 tables × 5M rows)")

    async def load_bench_events(self, table_num: int, total_rows: int = 5_000_000) -> None:
        """
        Load a single bench_events_N table with resume support.

        Args:
            table_num: Table number (1-16)
            total_rows: Number of rows to insert (default: 5M)
        """
        table_name = f"bench_events_{table_num}"
        current_count = await self.pool.get_table_count(table_name)

        if current_count >= total_rows:
            print(f"\n{table_name} already complete ({current_count:,}/{total_rows:,} rows) ✅")
            return

        print(f"\nLoading {table_name} ({current_count:,}/{total_rows:,} rows - resuming)...")

        # Use semaphore to limit concurrent batch inserts
        semaphore = asyncio.Semaphore(self.CONCURRENT_WORKERS)

        async def insert_batch_with_semaphore(batch_data: List[Tuple[Any, ...]]):
            async with semaphore:
                columns = [
                    'customer_id', 'event_type', 'region', 'amount',
                    'quantity', 'status', 'created_at'
                ]
                await self._insert_batch(table_name, columns, batch_data)

        # Generate batches for remaining rows only
        batches = []
        for start in range(current_count, total_rows, self.BATCH_SIZE):
            batch_size = min(self.BATCH_SIZE, total_rows - start)
            batch = self._generate_bench_events_batch(batch_size)
            batches.append(batch)

        # Use progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]{table_name}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            total_batches = (total_rows + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            completed_batches = (current_count + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            task = progress.add_task(f"Loading {table_name}...", total=total_batches, completed=completed_batches)

            # Insert batches concurrently
            for i in range(0, len(batches), self.CONCURRENT_WORKERS):
                batch_group = batches[i:i + self.CONCURRENT_WORKERS]
                await asyncio.gather(*[insert_batch_with_semaphore(b) for b in batch_group])
                progress.update(task, advance=len(batch_group))

        print(f"  ✅ {table_name}: {total_rows:,} rows inserted")

    def _generate_bench_events_batch(self, batch_size: int) -> List[Tuple[Any, ...]]:
        """
        Generate batch of bench_events records.

        Args:
            batch_size: Number of rows to generate

        Returns:
            List of tuples (customer_id, event_type, region, amount, quantity, status, created_at)
        """
        now = datetime.now()
        rows = []

        for _ in range(batch_size):
            customer_id = random.randint(1, 500_000)
            event_type = random.choice(self.EVENT_TYPES)
            region = random.choice(self.REGIONS)
            amount = round(random.uniform(0.01, 9999.99), 2)
            quantity = random.randint(1, 100)
            status = random.choice(self.STATUSES)
            # Random timestamp within past 2 years
            created_at = now - timedelta(days=random.randint(0, 730))

            rows.append((
                customer_id,
                event_type,
                region,
                amount,
                quantity,
                status,
                created_at
            ))

        return rows

    async def load_isolation_data(self) -> None:
        """
        Load isolation_test table (10k rows) with resume support.

        Values uniformly distributed between 1 and 1,000.
        """
        print(f"\n{'='*70}")
        print("Loading isolation_test table")
        print(f"{'='*70}")

        total_rows = 10_000
        current_count = await self.pool.get_table_count('isolation_test')

        if current_count >= total_rows:
            print(f"\nisolation_test already complete ({current_count:,}/{total_rows:,} rows) ✅")
            return

        print(f"\nLoading isolation_test ({current_count:,}/{total_rows:,} rows - resuming)...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Inserting isolation test data...", total=total_rows, completed=current_count)

            for start in range(current_count, total_rows, self.BATCH_SIZE):
                batch_size = min(self.BATCH_SIZE, total_rows - start)
                batch = self._generate_isolation_batch(batch_size)

                await self._insert_batch('isolation_test', ['test_value', 'data'], batch)

                progress.update(task, advance=batch_size)

        print(f"  ✅ {total_rows:,} rows inserted")

    def _generate_isolation_batch(self, batch_size: int) -> List[Tuple[Any, ...]]:
        """Generate batch of isolation_test records."""
        return [
            (f'value_{random.randint(1, 1_000)}', f'baseline_data_{i}')  # test_value, data
            for i in range(batch_size)
        ]

    async def _insert_batch(self, table_name: str, columns: List[str], data: List[Tuple[Any, ...]]) -> None:
        """
        Insert a batch of rows into a table.

        Args:
            table_name: Target table
            columns: Column names
            data: List of tuples containing row data
        """
        if not data:
            return

        # Build INSERT query
        column_list = ', '.join(columns)
        placeholders = ', '.join(f'${i+1}' for i in range(len(columns)))
        query = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"

        # Execute batch insert
        async with self.pool.acquire() as conn:
            await conn.executemany(query, data)

    async def print_loading_status(self) -> None:
        """
        Print detailed loading status for all tables.

        Useful for checking progress during or after a load operation.
        """
        print(f"\n{'='*70}")
        print(f"Data Loading Status - {self.pool.config.name}")
        print(f"{'='*70}")

        status = await self.get_table_status()

        complete_count = sum(1 for info in status.values() if info['complete'])
        total_count = len(status)

        print(f"\nOverall Progress: {complete_count}/{total_count} tables complete")
        print(f"\nTable Details:")
        print(f"{'─'*70}")

        for table_name, info in status.items():
            status_icon = "✅" if info['complete'] else "⚠️ "
            print(f"{status_icon} {table_name:25} {info['actual']:>12,}/{info['expected']:>12,} rows ({info['percentage']:>5.1f}%)")

        print(f"{'='*70}")

        if complete_count == total_count:
            print("✅ All tables fully loaded - ready for benchmarking")
        else:
            incomplete = total_count - complete_count
            print(f"⚠️  {incomplete} table(s) incomplete - run load again to resume")

        print(f"{'='*70}")

    async def verify_data_loaded(self) -> bool:
        """
        Verify that data has been loaded correctly.

        Checks row counts match expected values.

        Returns:
            True if verification passed
        """
        print(f"\n{'='*70}")
        print(f"Verifying data on {self.pool.config.name}")
        print(f"{'='*70}")

        expected_counts = {
            'pgbench_branches': 50_000,
            'pgbench_tellers': 500_000,
            'pgbench_accounts': 5_000_000,
            'isolation_test': 10_000,
        }

        # Add bench_events tables
        for i in range(1, 17):
            expected_counts[f'bench_events_{i}'] = 5_000_000

        all_correct = True

        for table_name, expected_count in expected_counts.items():
            actual_count = await self.pool.get_table_count(table_name)

            if actual_count == expected_count:
                print(f"  ✅ {table_name:25} {actual_count:>12,} rows (expected: {expected_count:,})")
            else:
                print(f"  ❌ {table_name:25} {actual_count:>12,} rows (expected: {expected_count:,})")
                all_correct = False

        print(f"{'='*70}")
        if all_correct:
            print("✅ Data verification passed")
        else:
            print("❌ Data verification failed - row counts mismatch")
        print(f"{'='*70}")

        return all_correct


async def estimate_load_time() -> None:
    """
    Estimate data loading time.

    This is approximate and depends on hardware, network, and database performance.
    """
    print("\n" + "="*70)
    print("Estimated Data Loading Time")
    print("="*70)

    # Rough estimates based on typical performance
    pgbench_time = 2  # minutes for 5.5M rows (branches + tellers + accounts)
    bench_events_time = 20  # minutes for 16 tables × 5M rows (with 6 concurrent workers)
    isolation_time = 0.5  # minutes for 10k rows

    total_time = pgbench_time + bench_events_time + isolation_time

    print(f"\nEstimated loading times:")
    print(f"  pgbench tables:      ~{pgbench_time:.1f} min")
    print(f"  bench_events (1-16): ~{bench_events_time:.1f} min")
    print(f"  isolation_test:      ~{isolation_time:.1f} min")
    print(f"  {'─'*40}")
    print(f"  TOTAL:               ~{total_time:.1f} min")
    print(f"\nNote: Actual time varies based on:")
    print(f"  - Database instance size and configuration")
    print(f"  - Network latency and bandwidth")
    print(f"  - Current database load")
    print(f"  - Storage performance (IOPS)")
    print("="*70)


if __name__ == '__main__':
    import asyncio
    asyncio.run(estimate_load_time())
    print("\nData loader module loaded successfully")
    print("\nExample usage:")
    print("  from src.database import DatabasePool")
    print("  from src.data_loader import DataLoader")
    print()
    print("  pool = DatabasePool(config)")
    print("  await pool.create_pool()")
    print()
    print("  loader = DataLoader(pool)")
    print("  await loader.load_all_data()")
    print("  await loader.verify_data_loaded()")

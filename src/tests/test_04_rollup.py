"""
Test 4: Rollup Aggregation Query

Purpose: GROUP BY ROLLUP over 5M rows - tests planner and aggregation engine.
Exercises analytical query performance with hierarchical aggregations.

Configuration:
- Query: ROLLUP aggregation on bench_events_1 (5M rows)
- Runs: 3 (report min, median, max execution time)
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import OLAPTest


class Test04Rollup(OLAPTest):
    """
    Test 4: ROLLUP aggregation query.

    Executes a complex GROUP BY ROLLUP query multiple times to test
    analytical query performance and consistency.
    """

    # The ROLLUP query - tests aggregation engine
    # Note: CockroachDB v26.1 doesn't support GROUP BY ROLLUP syntax.
    # We manually construct the rollup levels with UNION ALL (same semantics, works on both databases).
    ROLLUP_QUERY = """
        WITH base AS (
            SELECT
                date_trunc('month', created_at) AS month,
                region,
                status,
                amount
            FROM bench_events_1
        )
        -- Level 1: month, region, status (finest granularity)
        SELECT
            month,
            region,
            status,
            COUNT(*)                          AS event_count,
            SUM(amount)                       AS total_amount,
            AVG(amount)                       AS avg_amount,
            MIN(amount)                       AS min_amount,
            MAX(amount)                       AS max_amount
        FROM base
        GROUP BY month, region, status

        UNION ALL

        -- Level 2: month, region subtotals
        SELECT
            month,
            region,
            NULL AS status,
            COUNT(*),
            SUM(amount),
            AVG(amount),
            MIN(amount),
            MAX(amount)
        FROM base
        GROUP BY month, region

        UNION ALL

        -- Level 3: month subtotals
        SELECT
            month,
            NULL AS region,
            NULL AS status,
            COUNT(*),
            SUM(amount),
            AVG(amount),
            MIN(amount),
            MAX(amount)
        FROM base
        GROUP BY month

        UNION ALL

        -- Level 4: grand total
        SELECT
            NULL AS month,
            NULL AS region,
            NULL AS status,
            COUNT(*),
            SUM(amount),
            AVG(amount),
            MIN(amount),
            MAX(amount)
        FROM base

        ORDER BY month NULLS LAST, region NULLS LAST, status NULLS LAST;
    """

    def __init__(self, pool, num_runs: int = 3, timeout_seconds: int = 600):
        """
        Initialize Test 4.

        Args:
            pool: DatabasePool instance
            num_runs: Number of times to run the query (default: 3)
            timeout_seconds: Timeout per run in seconds (default: 600 = 10 minutes)
        """
        super().__init__(pool, num_runs=num_runs, timeout_seconds=timeout_seconds)

        self.rows_returned = 0

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 4: ROLLUP aggregation query.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting ROLLUP aggregation query {self.num_runs} times...")
        print(f"  Table: bench_events_1 (5M rows)")
        print(f"  Timeout: {self.timeout_seconds}s per run")
        print(f"  Aggregations: COUNT, SUM, AVG, MIN, MAX with ROLLUP")

        # Execute query multiple times
        for run_num in range(1, self.num_runs + 1):
            print(f"\n  Run {run_num}/{self.num_runs}...")

            run_start = time.perf_counter()

            try:
                # Execute query with timeout
                result = await asyncio.wait_for(
                    self._execute_rollup_query(),
                    timeout=self.timeout_seconds
                )

                run_duration = time.perf_counter() - run_start

                # Record execution time
                self.add_execution_time(run_duration)

                # Track rows returned (same for all runs)
                if run_num == 1:
                    self.rows_returned = len(result)

                print(f"    ✅ Completed in {run_duration:.2f}s ({len(result):,} rows)")

            except asyncio.TimeoutError:
                run_duration = time.perf_counter() - run_start
                print(f"    ⏱️  TIMEOUT after {run_duration:.2f}s")

                self.metrics.record_timeout()

                # Record timeout duration
                self.add_execution_time(self.timeout_seconds)

            except Exception as e:
                run_duration = time.perf_counter() - run_start
                print(f"    ❌ FAILED after {run_duration:.2f}s: {e}")

                self.metrics.record_error()

                # Still record the time
                self.add_execution_time(run_duration)

        # Compute statistics across runs
        stats = self.compute_statistics()

        print(f"\n  Statistics across {self.num_runs} runs:")
        if stats:
            print(f"    Min:    {stats['min_time_seconds']:.2f}s")
            print(f"    Median: {stats['median_time_seconds']:.2f}s")
            print(f"    Max:    {stats['max_time_seconds']:.2f}s")
            print(f"    Mean:   {stats['mean_time_seconds']:.2f}s")

        # Return summary
        result_data = {
            'query_type': 'ROLLUP aggregation',
            'table': 'bench_events_1',
            'table_size_rows': 5_000_000,
            'num_runs': self.num_runs,
            'rows_returned': self.rows_returned,
            'description': 'GROUP BY ROLLUP with COUNT, SUM, AVG, MIN, MAX aggregations'
        }

        # Add execution time statistics
        if stats:
            result_data.update(stats)

        return result_data

    async def _execute_rollup_query(self):
        """
        Execute the ROLLUP query.

        Returns:
            Query result rows
        """
        async with self.get_connection() as conn:
            result = await conn.fetch(self.ROLLUP_QUERY)
            return result


async def test_rollup():
    """Test the Test04Rollup implementation (mock)."""
    print("=" * 70)
    print("Test 04: ROLLUP Aggregation - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetch(self, query):
            await asyncio.sleep(0.5)  # Simulate 500ms query time
            # Return mock aggregation results
            return [
                {'month': '2024-01-01', 'region': 'eastus', 'status': 'completed',
                 'event_count': 1000, 'total_amount': 50000},
                {'month': '2024-01-01', 'region': 'eastus', 'status': None,
                 'event_count': 5000, 'total_amount': 250000},
            ] * 50  # Simulate 100 rows

    class MockPool:
        class config:
            name = "MockDB"

        class pool:
            @staticmethod
            async def acquire():
                return MockConnection()

            @staticmethod
            async def release(conn):
                pass

        def acquire(self):
            return MockContextManager(self.pool)

    class MockContextManager:
        def __init__(self, pool):
            self.pool = pool
            self.conn = None

        async def __aenter__(self):
            self.conn = await self.pool.acquire()
            return self.conn

        async def __aexit__(self, *args):
            await self.pool.release(self.conn)

    # Create test with reduced runs for testing
    pool = MockPool()
    test = Test04Rollup(pool, num_runs=2, timeout_seconds=10)

    print(f"\n✅ Test instantiated: {test.test_name}")
    print(f"   Runs: {test.num_runs}")
    print(f"   Timeout: {test.timeout_seconds}s")

    # Run test
    result = await test.run()

    print(f"\n✅ Test completed: {result.status}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    if result.custom_metrics:
        print(f"   Rows returned: {result.custom_metrics.get('rows_returned', 0):,}")
        if 'median_time_seconds' in result.custom_metrics:
            print(f"   Median time: {result.custom_metrics['median_time_seconds']:.2f}s")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    asyncio.run(test_rollup())

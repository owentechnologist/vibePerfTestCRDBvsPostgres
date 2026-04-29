"""
Test 5: OLAP Window Functions

Purpose: Complex analytical queries with window functions.
Tests ranking, bucketing, and cumulative aggregations over partitions.

Configuration:
- Query: Window functions (RANK, NTILE, SUM OVER) on bench_events_2 (5M rows)
- Runs: 3 (report min, median, max execution time)
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import OLAPTest


class Test05Window(OLAPTest):
    """
    Test 5: Window functions query.

    Executes a complex query with multiple window functions to test
    analytical query performance with partitioning and ordering.
    """

    # Window functions query - tests analytical engine
    WINDOW_QUERY = """
        SELECT
            customer_id,
            event_type,
            region,
            created_at,
            amount,
            RANK() OVER (PARTITION BY region ORDER BY amount DESC) AS amount_rank,
            NTILE(10) OVER (PARTITION BY region ORDER BY created_at) AS time_decile,
            SUM(amount) OVER (PARTITION BY customer_id ORDER BY created_at
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
            AVG(amount) OVER (PARTITION BY event_type ORDER BY created_at
                              ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) AS moving_avg,
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS recency_order
        FROM bench_events_2
        WHERE created_at >= NOW() - INTERVAL '90 days'
          AND status = 'completed'
        ORDER BY region, amount_rank
        LIMIT 10000;
    """

    def __init__(self, pool, num_runs: int = 3, timeout_seconds: int = 600):
        """
        Initialize Test 5.

        Args:
            pool: DatabasePool instance
            num_runs: Number of times to run the query (default: 3)
            timeout_seconds: Timeout per run in seconds (default: 600 = 10 minutes)
        """
        super().__init__(pool, num_runs=num_runs, timeout_seconds=timeout_seconds)

        self.rows_returned = 0

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 5: Window functions query.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting window functions query {self.num_runs} times...")
        print(f"  Table: bench_events_2 (5M rows)")
        print(f"  Timeout: {self.timeout_seconds}s per run")
        print(f"  Window functions: RANK, NTILE, SUM OVER, AVG OVER, ROW_NUMBER")

        # Execute query multiple times
        for run_num in range(1, self.num_runs + 1):
            print(f"\n  Run {run_num}/{self.num_runs}...")

            run_start = time.perf_counter()

            try:
                # Execute query with timeout
                result = await asyncio.wait_for(
                    self._execute_window_query(),
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
            'query_type': 'Window functions',
            'table': 'bench_events_2',
            'table_size_rows': 5_000_000,
            'num_runs': self.num_runs,
            'rows_returned': self.rows_returned,
            'description': 'RANK, NTILE, SUM OVER, AVG OVER, ROW_NUMBER window functions'
        }

        # Add execution time statistics
        if stats:
            result_data.update(stats)

        return result_data

    async def _execute_window_query(self):
        """
        Execute the window functions query.

        Returns:
            Query result rows
        """
        async with self.get_connection() as conn:
            result = await conn.fetch(self.WINDOW_QUERY)
            return result


async def test_window():
    """Test the Test05Window implementation (mock)."""
    print("=" * 70)
    print("Test 05: Window Functions - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetch(self, query):
            await asyncio.sleep(0.4)  # Simulate 400ms query time
            # Return mock window function results
            return [
                {'customer_id': i, 'event_type': 'purchase', 'region': 'eastus',
                 'amount': 100.0 * i, 'amount_rank': i, 'time_decile': 5,
                 'running_total': 500.0 * i, 'moving_avg': 100.0, 'recency_order': 1}
                for i in range(1, 101)
            ]

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
    test = Test05Window(pool, num_runs=2, timeout_seconds=10)

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
    asyncio.run(test_window())

"""
Test 6: Cross-Table JOIN

Purpose: Multi-table join performance on large datasets.
Tests join optimization and execution across two 5M row tables.

Configuration:
- Query: JOIN bench_events_1 and bench_events_2 on customer_id and region
- Tables: bench_events_1 (5M rows) ⨝ bench_events_2 (5M rows)
- Runs: 2 (report min, median, max execution time)
- Timeout: 10 minutes per run
- Metrics: Execution time per run, median time, rows returned
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import OLAPTest


class Test06Join(OLAPTest):
    """
    Test 6: Cross-table JOIN query.

    Executes a multi-table join with aggregations to test join
    performance and optimization on large tables.
    """

    # Cross-table JOIN query - tests join optimization
    JOIN_QUERY = """
        SELECT
            e1.region,
            e1.event_type AS event_type_1,
            e2.event_type AS event_type_2,
            COUNT(*) AS match_count,
            SUM(e1.amount) AS total_amount_1,
            SUM(e2.amount) AS total_amount_2,
            AVG(e1.amount) AS avg_amount_1,
            AVG(e2.amount) AS avg_amount_2,
            MAX(e1.created_at) AS latest_event_1,
            MAX(e2.created_at) AS latest_event_2
        FROM bench_events_1 e1
        INNER JOIN bench_events_2 e2
            ON e1.customer_id = e2.customer_id
            AND e1.region = e2.region
        WHERE e1.status = 'completed'
          AND e2.status = 'completed'
          AND e1.created_at >= NOW() - INTERVAL '180 days'
          AND e2.created_at >= NOW() - INTERVAL '180 days'
        GROUP BY e1.region, e1.event_type, e2.event_type
        HAVING COUNT(*) > 100
        ORDER BY match_count DESC, e1.region
        LIMIT 500;
    """

    def __init__(self, pool, num_runs: int = 2, timeout_seconds: int = 600):
        """
        Initialize Test 6.

        Args:
            pool: DatabasePool instance
            num_runs: Number of times to run the query (default: 2)
            timeout_seconds: Timeout per run in seconds (default: 600 = 10 minutes)
        """
        super().__init__(pool, num_runs=num_runs, timeout_seconds=timeout_seconds)

        self.rows_returned = 0

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 6: Cross-table JOIN query.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting cross-table JOIN query {self.num_runs} times...")
        print(f"  Tables: bench_events_1 (5M rows) ⨝ bench_events_2 (5M rows)")
        print(f"  Timeout: {self.timeout_seconds}s per run")
        print(f"  Join condition: customer_id + region")
        print(f"  Aggregations: COUNT, SUM, AVG, MAX")

        # Execute query multiple times
        for run_num in range(1, self.num_runs + 1):
            print(f"\n  Run {run_num}/{self.num_runs}...")

            run_start = time.perf_counter()

            try:
                # Execute query with timeout
                result = await asyncio.wait_for(
                    self._execute_join_query(),
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
            'query_type': 'Cross-table JOIN',
            'tables': 'bench_events_1 ⨝ bench_events_2',
            'table_size_rows': 5_000_000,
            'num_runs': self.num_runs,
            'rows_returned': self.rows_returned,
            'description': 'INNER JOIN on customer_id and region with aggregations'
        }

        # Add execution time statistics
        if stats:
            result_data.update(stats)

        return result_data

    async def _execute_join_query(self):
        """
        Execute the cross-table JOIN query.

        Returns:
            Query result rows
        """
        async with self.get_connection() as conn:
            result = await conn.fetch(self.JOIN_QUERY)
            return result


async def test_join():
    """Test the Test06Join implementation (mock)."""
    print("=" * 70)
    print("Test 06: Cross-Table JOIN - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetch(self, query):
            await asyncio.sleep(0.6)  # Simulate 600ms query time
            # Return mock join results
            return [
                {'region': 'eastus', 'event_type_1': 'purchase', 'event_type_2': 'view',
                 'match_count': 1000 + i, 'total_amount_1': 50000.0, 'total_amount_2': 30000.0}
                for i in range(50)
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
    test = Test06Join(pool, num_runs=2, timeout_seconds=10)

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
    asyncio.run(test_join())

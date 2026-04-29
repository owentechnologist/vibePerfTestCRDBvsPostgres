"""
Test 2: Primary Key Point Lookup

Purpose: Single-row indexed fetch performance.
Tests the efficiency of primary key lookups on a large table.

Configuration:
- Query: SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1;
- Table: pgbench_accounts (5M rows)
- Iterations: 50,000
- Concurrency: 8 workers
- Metrics: p50, p95, p99 latency (ms), QPS
"""

import asyncio
import random
import time
from typing import Dict, Any

from src.tests.base import LatencyTest


class Test02PointLookup(LatencyTest):
    """
    Test 2: Primary key point lookup.

    Measures latency for indexed single-row lookups on a large table
    with concurrent workers.
    """

    def __init__(self, pool, iterations: int = 50_000, concurrency: int = 8):
        """
        Initialize Test 2.

        Args:
            pool: DatabasePool instance
            iterations: Number of point lookups to execute (default: 50,000)
            concurrency: Number of concurrent workers (default: 8)
        """
        super().__init__(pool, iterations=iterations, concurrency=concurrency)

        # Account ID range (pgbench_accounts has 5M rows: 1 to 5,000,000)
        self.min_aid = 1
        self.max_aid = 5_000_000

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 2: Point lookup test.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting {self.iterations:,} point lookups with {self.concurrency} workers...")
        print(f"  Table: pgbench_accounts (5M rows)")
        print(f"  Query: SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)

        # Counter for progress tracking
        completed = {'count': 0}
        lock = asyncio.Lock()

        async def point_lookup_worker():
            """Execute a single point lookup with random aid."""
            async with semaphore:
                # Random account ID
                aid = random.randint(self.min_aid, self.max_aid)

                # Execute query with timing
                start = time.perf_counter()

                async with self.get_connection() as conn:
                    result = await conn.fetchrow(
                        'SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1',
                        aid
                    )

                latency_ms = (time.perf_counter() - start) * 1000
                self.metrics.record_latency(latency_ms)

                # Update progress
                async with lock:
                    completed['count'] += 1
                    if completed['count'] % 5000 == 0:
                        print(f"  Progress: {completed['count']:,} / {self.iterations:,} queries", end='\r')

                return result

        # Execute all lookups concurrently
        tasks = [point_lookup_worker() for _ in range(self.iterations)]
        await asyncio.gather(*tasks)

        print(f"  Progress: {self.iterations:,} / {self.iterations:,} queries ✓")

        # Return summary
        return {
            'query': 'SELECT aid, abalance FROM pgbench_accounts WHERE aid = $1',
            'table': 'pgbench_accounts',
            'table_size_rows': 5_000_000,
            'iterations': self.iterations,
            'concurrency': self.concurrency,
            'description': 'Primary key point lookup with concurrent workers'
        }


async def test_point_lookup():
    """Test the Test02PointLookup implementation (mock)."""
    print("=" * 70)
    print("Test 02: Point Lookup - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetchrow(self, query, aid):
            await asyncio.sleep(0.002)  # Simulate 2ms latency
            return {'aid': aid, 'abalance': 0}

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

    # Create test with reduced iterations for testing
    pool = MockPool()
    test = Test02PointLookup(pool, iterations=100, concurrency=4)

    print(f"\n✅ Test instantiated: {test.test_name}")
    print(f"   Iterations: {test.iterations:,}")
    print(f"   Concurrency: {test.concurrency}")

    # Run test
    result = await test.run()

    print(f"\n✅ Test completed: {result.status}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    if result.percentiles:
        print(f"   p50: {result.percentiles['p50']:.2f} ms")
        print(f"   p95: {result.percentiles['p95']:.2f} ms")
        print(f"   p99: {result.percentiles['p99']:.2f} ms")

    if result.throughput:
        print(f"   QPS: {result.throughput['qps']:,.0f}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    asyncio.run(test_point_lookup())

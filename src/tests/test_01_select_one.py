"""
Test 1: Simple Latency Baseline - SELECT 1

Purpose: Measure round-trip latency with zero data access.
This establishes a baseline for network and protocol overhead.

Configuration:
- Query: SELECT 1;
- Iterations: 10,000
- Concurrency: Serial (single connection)
- Metrics: p50, p95, p99 latency (ms), QPS
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import LatencyTest


class Test01SelectOne(LatencyTest):
    """
    Test 1: SELECT 1 latency baseline.

    Measures the minimum possible latency for the database by executing
    the simplest possible query repeatedly.
    """

    def __init__(self, pool, iterations: int = 10_000):
        """
        Initialize Test 1.

        Args:
            pool: DatabasePool instance
            iterations: Number of SELECT 1 queries to execute (default: 10,000)
        """
        super().__init__(pool, iterations=iterations, concurrency=1)

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 1: SELECT 1 latency test.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting {self.iterations:,} iterations of 'SELECT 1'...")
        print(f"  Concurrency: Serial (single connection)")

        # Acquire a single connection for all queries
        async with self.get_connection() as conn:
            # Execute iterations serially
            for i in range(self.iterations):
                start = time.perf_counter()

                # Execute SELECT 1
                await conn.fetchval('SELECT 1')

                # Record latency
                latency_ms = (time.perf_counter() - start) * 1000
                self.metrics.record_latency(latency_ms)

                # Progress update every 1000 iterations
                if (i + 1) % 1000 == 0:
                    print(f"  Progress: {i + 1:,} / {self.iterations:,} queries", end='\r')

        print(f"  Progress: {self.iterations:,} / {self.iterations:,} queries ✓")

        # Return summary
        return {
            'query': 'SELECT 1',
            'iterations': self.iterations,
            'concurrency': self.concurrency,
            'description': 'Simple latency baseline - zero data access'
        }


async def test_select_one():
    """Test the Test01SelectOne implementation (mock)."""
    print("=" * 70)
    print("Test 01: SELECT 1 - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def fetchval(self, query):
            await asyncio.sleep(0.001)  # Simulate 1ms latency
            return 1

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
    test = Test01SelectOne(pool, iterations=100)

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
    asyncio.run(test_select_one())

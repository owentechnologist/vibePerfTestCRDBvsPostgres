#!/usr/bin/env python3
"""
Test Phase 5a implementations - Tests 1-4.

Verifies that all test implementations work correctly with mocked connections.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock asyncpg before imports
class MockConnection: pass
class MockRecord: pass
class MockPool: pass

class MockAsyncPG:
    Connection = MockConnection
    Record = MockRecord
    Pool = MockPool

    class SerializationError(Exception): pass
    class DeadlockDetectedError(Exception): pass
    class InsufficientPrivilegeError(Exception): pass
    class PostgresError(Exception):
        sqlstate = None

sys.modules['asyncpg'] = MockAsyncPG()
sys.modules['asyncpg.exceptions'] = type('Module', (), {
    'SerializationError': MockAsyncPG.SerializationError,
    'DeadlockDetectedError': MockAsyncPG.DeadlockDetectedError,
    'InsufficientPrivilegeError': MockAsyncPG.InsufficientPrivilegeError,
    'PostgresError': MockAsyncPG.PostgresError
})()


def test_imports():
    """Test that all test classes can be imported."""
    print("=" * 70)
    print("Testing Phase 5a Imports")
    print("=" * 70)

    print("\n[1/4] Importing test classes...")

    try:
        from src.tests.test_01_select_one import Test01SelectOne
        from src.tests.test_02_point_lookup import Test02PointLookup
        from src.tests.test_03_pgbench import Test03PgBench
        from src.tests.test_04_rollup import Test04Rollup

        print("  ✅ Test01SelectOne imported")
        print("  ✅ Test02PointLookup imported")
        print("  ✅ Test03PgBench imported")
        print("  ✅ Test04Rollup imported")

        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


async def test_test01():
    """Test Test01SelectOne."""
    print("\n" + "=" * 70)
    print("[2/4] Testing Test01SelectOne")
    print("=" * 70)

    from src.tests.test_01_select_one import Test01SelectOne

    # Mock pool
    class MockConn:
        async def fetchval(self, query):
            await asyncio.sleep(0.001)
            return 1

    class MockPool:
        class config:
            name = "TestDB"

        class pool:
            @staticmethod
            async def acquire():
                return MockConn()

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

    pool = MockPool()
    test = Test01SelectOne(pool, iterations=50)

    print(f"\n✅ Test instantiated")
    print(f"   Iterations: {test.iterations}")
    print(f"   Concurrency: {test.concurrency}")

    result = await test.run()

    if result.status == 'SUCCESS':
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        print(f"   Samples: {result.percentiles['count'] if result.percentiles else 0}")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def test_test02():
    """Test Test02PointLookup."""
    print("\n" + "=" * 70)
    print("[3/4] Testing Test02PointLookup")
    print("=" * 70)

    from src.tests.test_02_point_lookup import Test02PointLookup

    # Mock pool
    class MockConn:
        async def fetchrow(self, query, aid):
            await asyncio.sleep(0.002)
            return {'aid': aid, 'abalance': 0}

    class MockPool:
        class config:
            name = "TestDB"

        class pool:
            @staticmethod
            async def acquire():
                return MockConn()

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

    pool = MockPool()
    test = Test02PointLookup(pool, iterations=50, concurrency=4)

    print(f"\n✅ Test instantiated")
    print(f"   Iterations: {test.iterations}")
    print(f"   Concurrency: {test.concurrency}")

    result = await test.run()

    if result.status == 'SUCCESS':
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        print(f"   Samples: {result.percentiles['count'] if result.percentiles else 0}")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def test_test03():
    """Test Test03PgBench."""
    print("\n" + "=" * 70)
    print("[4/4] Testing Test03PgBench")
    print("=" * 70)

    from src.tests.test_03_pgbench import Test03PgBench

    # Mock pool
    class MockConn:
        async def execute(self, query, *args):
            await asyncio.sleep(0.001)
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.001)
            return 0

    class MockPool:
        class config:
            name = "TestDB"

        class pool:
            @staticmethod
            async def acquire():
                return MockConn()

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

    pool = MockPool()
    test = Test03PgBench(pool, duration_seconds=1, concurrency=2)

    print(f"\n✅ Test instantiated")
    print(f"   Duration: {test.duration_seconds}s")
    print(f"   Concurrency: {test.concurrency}")

    result = await test.run()

    if result.status == 'SUCCESS':
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        txns = result.custom_metrics.get('successful_transactions', 0)
        print(f"   Transactions: {txns}")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def test_test04():
    """Test Test04Rollup."""
    print("\n" + "=" * 70)
    print("[5/5] Testing Test04Rollup")
    print("=" * 70)

    from src.tests.test_04_rollup import Test04Rollup

    # Mock pool
    class MockConn:
        async def fetch(self, query):
            await asyncio.sleep(0.3)  # Simulate 300ms query
            return [{'month': '2024-01-01', 'event_count': 1000}] * 100

    class MockPool:
        class config:
            name = "TestDB"

        class pool:
            @staticmethod
            async def acquire():
                return MockConn()

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

    pool = MockPool()
    test = Test04Rollup(pool, num_runs=2, timeout_seconds=10)

    print(f"\n✅ Test instantiated")
    print(f"   Runs: {test.num_runs}")
    print(f"   Timeout: {test.timeout_seconds}s")

    result = await test.run()

    if result.status == 'SUCCESS':
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        if 'median_time_seconds' in result.custom_metrics:
            print(f"   Median time: {result.custom_metrics['median_time_seconds']:.2f}s")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def run_async_tests():
    """Run all async tests."""
    results = []

    results.append(await test_test01())
    results.append(await test_test02())
    results.append(await test_test03())
    results.append(await test_test04())

    return results


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Phase 5a Test Suite - Tests 1-4")
    print("=" * 70)

    results = []

    # Test imports
    results.append(('Imports', test_imports()))

    # Run async tests
    async_results = asyncio.run(run_async_tests())
    results.append(('Test01SelectOne', async_results[0]))
    results.append(('Test02PointLookup', async_results[1]))
    results.append(('Test03PgBench', async_results[2]))
    results.append(('Test04Rollup', async_results[3]))

    # Summary
    print("\n" + "=" * 70)
    print("Phase 5a Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All Phase 5a tests passed!")
        print("\nImplemented tests:")
        print("  - Test 01: SELECT 1 latency baseline")
        print("  - Test 02: Primary key point lookup")
        print("  - Test 03: pgbench TPC-B workload")
        print("  - Test 04: ROLLUP aggregation query")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

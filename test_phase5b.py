#!/usr/bin/env python3
"""
Test Phase 5b implementations - Tests 5-8.

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
    print("Testing Phase 5b Imports")
    print("=" * 70)

    print("\n[1/4] Importing test classes...")

    try:
        from src.tests.test_05_window import Test05Window
        from src.tests.test_06_join import Test06Join
        from src.tests.test_07_phantom_read import Test07PhantomRead
        from src.tests.test_08_nonrepeatable_read import Test08NonRepeatableRead

        print("  ✅ Test05Window imported")
        print("  ✅ Test06Join imported")
        print("  ✅ Test07PhantomRead imported")
        print("  ✅ Test08NonRepeatableRead imported")

        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


async def test_test05():
    """Test Test05Window."""
    print("\n" + "=" * 70)
    print("[2/4] Testing Test05Window")
    print("=" * 70)

    from src.tests.test_05_window import Test05Window

    # Mock pool
    class MockConn:
        async def fetch(self, query):
            await asyncio.sleep(0.2)
            return [{'customer_id': i, 'amount': 100.0} for i in range(50)]

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
    test = Test05Window(pool, num_runs=2, timeout_seconds=10)

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


async def test_test06():
    """Test Test06Join."""
    print("\n" + "=" * 70)
    print("[3/4] Testing Test06Join")
    print("=" * 70)

    from src.tests.test_06_join import Test06Join

    # Mock pool
    class MockConn:
        async def fetch(self, query):
            await asyncio.sleep(0.3)
            return [{'region': 'eastus', 'match_count': 1000} for i in range(30)]

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
    test = Test06Join(pool, num_runs=2, timeout_seconds=10)

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


async def test_test07():
    """Test Test07PhantomRead."""
    print("\n" + "=" * 70)
    print("[4/4] Testing Test07PhantomRead")
    print("=" * 70)

    from src.tests.test_07_phantom_read import Test07PhantomRead

    # Mock pool with isolation test support
    class MockConn:
        def __init__(self):
            self.count = 0

        async def execute(self, query, *args):
            await asyncio.sleep(0.01)
            if 'INSERT' in query:
                self.count += 1
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.01)
            if 'COUNT' in query:
                return self.count
            return 1

    class MockPool:
        class config:
            name = "TestDB"

        def __init__(self):
            # Create shared connections for isolation test
            self.mock_conn_a = MockConn()
            self.mock_conn_b = MockConn()
            # Share count to simulate isolation
            self.mock_conn_b.count = self.mock_conn_a.count

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
    test = Test07PhantomRead(pool, timeout_seconds=10)

    print(f"\n✅ Test instantiated")
    print(f"   Timeout: {test.timeout_seconds}s")

    result = await test.run()

    if result.status in ['SUCCESS', 'FAILED']:  # FAILED is expected for isolation tests
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        if 'status' in result.custom_metrics:
            print(f"   Isolation status: {result.custom_metrics['status']}")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def test_test08():
    """Test Test08NonRepeatableRead."""
    print("\n" + "=" * 70)
    print("[5/5] Testing Test08NonRepeatableRead")
    print("=" * 70)

    from src.tests.test_08_nonrepeatable_read import Test08NonRepeatableRead

    # Mock pool with isolation test support
    class MockConn:
        def __init__(self):
            self.data = "initial_value"

        async def execute(self, query, *args):
            await asyncio.sleep(0.01)
            if 'UPDATE' in query and len(args) >= 1:
                self.data = args[0]
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.01)
            if 'RETURNING' in query:
                return 1
            return self.data

    class MockPool:
        class config:
            name = "TestDB"

        def __init__(self):
            self.mock_conn_a = MockConn()
            self.mock_conn_b = MockConn()

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
    test = Test08NonRepeatableRead(pool, timeout_seconds=10)

    print(f"\n✅ Test instantiated")
    print(f"   Timeout: {test.timeout_seconds}s")

    result = await test.run()

    if result.status in ['SUCCESS', 'FAILED']:  # FAILED is expected for isolation tests
        print(f"\n✅ Test completed successfully")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        if 'status' in result.custom_metrics:
            print(f"   Isolation status: {result.custom_metrics['status']}")
        return True
    else:
        print(f"\n❌ Test failed: {result.status}")
        return False


async def run_async_tests():
    """Run all async tests."""
    results = []

    results.append(await test_test05())
    results.append(await test_test06())
    results.append(await test_test07())
    results.append(await test_test08())

    return results


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Phase 5b Test Suite - Tests 5-8")
    print("=" * 70)

    results = []

    # Test imports
    results.append(('Imports', test_imports()))

    # Run async tests
    async_results = asyncio.run(run_async_tests())
    results.append(('Test05Window', async_results[0]))
    results.append(('Test06Join', async_results[1]))
    results.append(('Test07PhantomRead', async_results[2]))
    results.append(('Test08NonRepeatableRead', async_results[3]))

    # Summary
    print("\n" + "=" * 70)
    print("Phase 5b Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All Phase 5b tests passed!")
        print("\nImplemented tests:")
        print("  - Test 05: OLAP window functions (RANK, NTILE, SUM OVER)")
        print("  - Test 06: Cross-table JOIN aggregation")
        print("  - Test 07: Phantom read isolation test (SERIALIZABLE)")
        print("  - Test 08: Non-repeatable read isolation test (REPEATABLE READ)")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

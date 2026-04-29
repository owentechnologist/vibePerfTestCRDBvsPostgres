"""
Test 7: Phantom Read Isolation Test

Purpose: Validate SERIALIZABLE isolation level prevents phantom reads.
Tests whether new rows inserted by concurrent transactions are visible.

Configuration:
- Isolation level: SERIALIZABLE
- Scenario: Connection A counts rows, Connection B inserts, Connection A counts again
- Expected: Serialization error OR consistent counts (no phantom reads)
- Metrics: PASS/FAIL, actual isolation behavior, error details
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import IsolationTest


class Test07PhantomRead(IsolationTest):
    """
    Test 7: Phantom read isolation test.

    Tests SERIALIZABLE isolation level by attempting to create a phantom read
    scenario where a concurrent insert would cause count changes mid-transaction.
    """

    def __init__(self, pool, timeout_seconds: int = 60):
        """
        Initialize Test 7.

        Args:
            pool: DatabasePool instance
            timeout_seconds: Timeout for test execution (default: 60 seconds)
        """
        super().__init__(pool, timeout_seconds=timeout_seconds)

        self.test_value = f"phantom_test_{int(time.time())}"

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 7: Phantom read isolation test.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting phantom read isolation test (SERIALIZABLE)...")
        print(f"  Isolation level: SERIALIZABLE")
        print(f"  Test value: {self.test_value}")
        print(f"  Expected: Serialization error OR consistent counts")

        try:
            # Acquire two separate connections
            await self.acquire_connections()

            # Connection A: Enable multiple active portals (CockroachDB v26.1 preview feature)
            # Required for multiple queries within the same transaction
            if self.pool.is_cockroachdb:
                await self.conn_a.execute("SET multiple_active_portals_enabled = true")

            # Connection A: Start transaction with SERIALIZABLE isolation
            print(f"\n  [Conn A] BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            await self.conn_a.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE")

            # Connection A: First count
            count_1 = await self.conn_a.fetchval(
                "SELECT COUNT(*) FROM isolation_test WHERE test_value = $1",
                self.test_value
            )
            print(f"  [Conn A] Initial count: {count_1}")

            # Small delay to allow interleaving
            await asyncio.sleep(0.1)

            # Connection B: Insert new row (separate transaction)
            print(f"  [Conn B] BEGIN; INSERT; COMMIT")
            await self.conn_b.execute("BEGIN")
            await self.conn_b.execute(
                "INSERT INTO isolation_test (test_value, data) VALUES ($1, $2)",
                self.test_value,
                "phantom_row"
            )
            await self.conn_b.execute("COMMIT")
            print(f"  [Conn B] Inserted 1 row with test_value = '{self.test_value}'")

            # Connection A: Second count (should see same count or get error)
            print(f"  [Conn A] Second count...")
            count_2 = await self.conn_a.fetchval(
                "SELECT COUNT(*) FROM isolation_test WHERE test_value = $1",
                self.test_value
            )
            print(f"  [Conn A] Second count: {count_2}")

            # Connection A: Commit
            print(f"  [Conn A] COMMIT")
            await self.conn_a.execute("COMMIT")

            # Analyze results
            if count_1 == count_2:
                # No phantom read - SERIALIZABLE isolation working correctly
                result = {
                    'test': 'phantom_read',
                    'isolation_level': 'SERIALIZABLE',
                    'status': 'PASS',
                    'behavior': 'No phantom read detected',
                    'count_1': count_1,
                    'count_2': count_2,
                    'serialization_error': False,
                    'description': 'SERIALIZABLE isolation prevented phantom read'
                }
                print(f"\n  ✅ PASS: No phantom read (counts: {count_1} → {count_2})")
            else:
                # Phantom read occurred - isolation failure
                result = {
                    'test': 'phantom_read',
                    'isolation_level': 'SERIALIZABLE',
                    'status': 'FAIL',
                    'behavior': 'Phantom read occurred',
                    'count_1': count_1,
                    'count_2': count_2,
                    'serialization_error': False,
                    'description': 'New row visible mid-transaction (isolation violation)'
                }
                print(f"\n  ❌ FAIL: Phantom read detected (counts: {count_1} → {count_2})")

        except Exception as e:
            # Serialization error expected - this is correct SERIALIZABLE behavior
            error_type = type(e).__name__
            error_msg = str(e)

            # Check if it's a serialization error
            is_serialization_error = 'serialization' in error_msg.lower() or 'SQLSTATE 40001' in error_msg

            if is_serialization_error:
                result = {
                    'test': 'phantom_read',
                    'isolation_level': 'SERIALIZABLE',
                    'status': 'PASS',
                    'behavior': 'Serialization error raised',
                    'serialization_error': True,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'description': 'Database correctly raised serialization error to prevent phantom read'
                }
                print(f"\n  ✅ PASS: Serialization error raised (expected behavior)")
                print(f"     Error: {error_type}")
            else:
                # Unexpected error
                result = {
                    'test': 'phantom_read',
                    'isolation_level': 'SERIALIZABLE',
                    'status': 'ERROR',
                    'behavior': 'Unexpected error',
                    'serialization_error': False,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'description': 'Unexpected error during isolation test'
                }
                print(f"\n  ⚠️  ERROR: Unexpected error")
                print(f"     {error_type}: {error_msg}")

                # Record error in metrics
                self.metrics.record_error()

            # Attempt to rollback both connections
            try:
                await self.conn_a.execute("ROLLBACK")
            except:
                pass
            try:
                await self.conn_b.execute("ROLLBACK")
            except:
                pass

        finally:
            # Release connections
            await self.release_connections()

            # Cleanup: Delete test rows
            await self.cleanup_test_data()

        return result

    async def cleanup_test_data(self):
        """Clean up test data."""
        try:
            async with self.get_connection() as conn:
                deleted = await conn.execute(
                    "DELETE FROM isolation_test WHERE test_value = $1",
                    self.test_value
                )
                print(f"  [Cleanup] Deleted test rows: {deleted}")
        except Exception as e:
            print(f"  [Cleanup] Warning: {e}")


async def test_phantom_read():
    """Test the Test07PhantomRead implementation (mock)."""
    print("=" * 70)
    print("Test 07: Phantom Read - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        def __init__(self):
            self.count = 0

        async def execute(self, query, *args):
            await asyncio.sleep(0.01)
            # Simulate INSERT incrementing count
            if 'INSERT' in query:
                self.count += 1
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.01)
            # Return current count
            return self.count

    class MockPool:
        class config:
            name = "MockDB"

        def __init__(self):
            self.conn_a = MockConnection()
            self.conn_b = MockConnection()
            # Share count between connections to simulate isolation violation
            shared_count = [0]
            self.conn_a.count = shared_count[0]
            self.conn_b.count = shared_count[0]

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

    # Create test
    pool = MockPool()
    test = Test07PhantomRead(pool, timeout_seconds=10)

    print(f"\n✅ Test instantiated: {test.test_name}")
    print(f"   Timeout: {test.timeout_seconds}s")

    # Run test
    result = await test.run()

    print(f"\n✅ Test completed: {result.status}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    if result.custom_metrics:
        print(f"   Isolation test: {result.custom_metrics.get('status', 'UNKNOWN')}")
        if 'behavior' in result.custom_metrics:
            print(f"   Behavior: {result.custom_metrics['behavior']}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    asyncio.run(test_phantom_read())

"""
Test 8: Non-Repeatable Read Isolation Test

Purpose: Validate REPEATABLE READ isolation level prevents non-repeatable reads.
Tests whether updated values from concurrent transactions are visible.

Configuration:
- Isolation level: REPEATABLE READ
- Scenario: Connection A reads value, Connection B updates, Connection A reads again
- Expected: Serialization error OR consistent reads (same value both times)
- Metrics: PASS/FAIL, actual isolation behavior, error details
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import IsolationTest


class Test08NonRepeatableRead(IsolationTest):
    """
    Test 8: Non-repeatable read isolation test.

    Tests REPEATABLE READ isolation level by attempting to create a non-repeatable
    read scenario where a concurrent update would cause value changes mid-transaction.
    """

    def __init__(self, pool, timeout_seconds: int = 60):
        """
        Initialize Test 8.

        Args:
            pool: DatabasePool instance
            timeout_seconds: Timeout for test execution (default: 60 seconds)
        """
        super().__init__(pool, timeout_seconds=timeout_seconds)

        self.test_value = f"nonrepeatable_test_{int(time.time())}"
        self.test_row_id = None

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 8: Non-repeatable read isolation test.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting non-repeatable read isolation test (REPEATABLE READ)...")
        print(f"  Isolation level: REPEATABLE READ")
        print(f"  Test value: {self.test_value}")
        print(f"  Expected: Consistent reads OR serialization error")

        try:
            # Setup: Insert test row
            async with self.get_connection() as conn:
                self.test_row_id = await conn.fetchval(
                    "INSERT INTO isolation_test (test_value, data) VALUES ($1, $2) RETURNING id",
                    self.test_value,
                    "initial_value"
                )
                print(f"  [Setup] Inserted test row (id={self.test_row_id}, data='initial_value')")

            # Acquire two separate connections
            await self.acquire_connections()

            # Connection A: Enable multiple active portals (CockroachDB v26.1 preview feature)
            # Required for multiple queries within the same transaction
            if self.pool.is_cockroachdb:
                await self.conn_a.execute("SET multiple_active_portals_enabled = true")

            # Connection A: Start transaction with REPEATABLE READ isolation
            print(f"\n  [Conn A] BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            await self.conn_a.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ")

            # Connection A: First read
            data_1 = await self.conn_a.fetchval(
                "SELECT data FROM isolation_test WHERE id = $1",
                self.test_row_id
            )
            print(f"  [Conn A] First read: data = '{data_1}'")

            # Small delay to allow interleaving
            await asyncio.sleep(0.1)

            # Connection B: Update the row (separate transaction)
            print(f"  [Conn B] BEGIN; UPDATE; COMMIT")
            await self.conn_b.execute("BEGIN")
            await self.conn_b.execute(
                "UPDATE isolation_test SET data = $1 WHERE id = $2",
                "updated_value",
                self.test_row_id
            )
            await self.conn_b.execute("COMMIT")
            print(f"  [Conn B] Updated row {self.test_row_id}: data = 'updated_value'")

            # Connection A: Second read (should see same value or get error)
            print(f"  [Conn A] Second read...")
            data_2 = await self.conn_a.fetchval(
                "SELECT data FROM isolation_test WHERE id = $1",
                self.test_row_id
            )
            print(f"  [Conn A] Second read: data = '{data_2}'")

            # Connection A: Commit
            print(f"  [Conn A] COMMIT")
            await self.conn_a.execute("COMMIT")

            # Analyze results
            if data_1 == data_2:
                # No non-repeatable read - REPEATABLE READ isolation working correctly
                result = {
                    'test': 'nonrepeatable_read',
                    'isolation_level': 'REPEATABLE READ',
                    'status': 'PASS',
                    'behavior': 'No non-repeatable read detected',
                    'data_1': data_1,
                    'data_2': data_2,
                    'serialization_error': False,
                    'description': 'REPEATABLE READ isolation prevented non-repeatable read'
                }
                print(f"\n  ✅ PASS: Consistent reads (values: '{data_1}' → '{data_2}')")
            else:
                # Non-repeatable read occurred - isolation failure
                result = {
                    'test': 'nonrepeatable_read',
                    'isolation_level': 'REPEATABLE READ',
                    'status': 'FAIL',
                    'behavior': 'Non-repeatable read occurred',
                    'data_1': data_1,
                    'data_2': data_2,
                    'serialization_error': False,
                    'description': 'Updated value visible mid-transaction (isolation violation)'
                }
                print(f"\n  ❌ FAIL: Non-repeatable read detected (values: '{data_1}' → '{data_2}')")

        except Exception as e:
            # Serialization error may occur - this is acceptable REPEATABLE READ behavior
            error_type = type(e).__name__
            error_msg = str(e)

            # Check if it's a serialization error
            is_serialization_error = 'serialization' in error_msg.lower() or 'SQLSTATE 40001' in error_msg

            if is_serialization_error:
                result = {
                    'test': 'nonrepeatable_read',
                    'isolation_level': 'REPEATABLE READ',
                    'status': 'PASS',
                    'behavior': 'Serialization error raised',
                    'serialization_error': True,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'description': 'Database raised serialization error (acceptable behavior)'
                }
                print(f"\n  ✅ PASS: Serialization error raised (acceptable behavior)")
                print(f"     Error: {error_type}")
            else:
                # Unexpected error
                result = {
                    'test': 'nonrepeatable_read',
                    'isolation_level': 'REPEATABLE READ',
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

            # Cleanup: Delete test row
            await self.cleanup_test_data()

        return result

    async def cleanup_test_data(self):
        """Clean up test data."""
        try:
            async with self.get_connection() as conn:
                if self.test_row_id:
                    deleted = await conn.execute(
                        "DELETE FROM isolation_test WHERE id = $1",
                        self.test_row_id
                    )
                    print(f"  [Cleanup] Deleted test row {self.test_row_id}")
        except Exception as e:
            print(f"  [Cleanup] Warning: {e}")


async def test_nonrepeatable_read():
    """Test the Test08NonRepeatableRead implementation (mock)."""
    print("=" * 70)
    print("Test 08: Non-Repeatable Read - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        def __init__(self):
            self.data = "initial_value"

        async def execute(self, query, *args):
            await asyncio.sleep(0.01)
            # Simulate UPDATE changing data
            if 'UPDATE' in query and len(args) >= 1:
                self.data = args[0]
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.01)
            # Return current data
            if 'RETURNING' in query:
                return 1  # Mock ID
            return self.data

    class MockPool:
        class config:
            name = "MockDB"

        def __init__(self):
            self.conn_a = MockConnection()
            self.conn_b = MockConnection()
            # Share data reference to simulate proper isolation
            shared_data = {"value": "initial_value"}

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
    test = Test08NonRepeatableRead(pool, timeout_seconds=10)

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
    asyncio.run(test_nonrepeatable_read())

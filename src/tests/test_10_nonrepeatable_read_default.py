"""
Test 10: Non-Repeatable Read with Default Isolation Level

Purpose: Verify that default isolation level PREVENTS non-repeatable reads.
Tests whether databases prevent non-repeatable reads using their DEFAULT isolation levels.

Configuration:
- Isolation level: DEFAULT (no explicit setting)
  - CockroachDB default: SERIALIZABLE (should prevent non-repeatable reads)
  - PostgreSQL default: READ COMMITTED (allows non-repeatable reads)
- Scenario: Connection A reads value, Connection B updates, Connection A reads again
- Expected Results:
  - CockroachDB: PASS (consistent reads OR serialization error)
  - PostgreSQL: FAIL if non-repeatable read occurs (default READ COMMITTED allows this)
- Pass Criteria: PASS if non-repeatable reads are prevented, FAIL if they occur
- Purpose: Flag when default isolation is insufficient for data consistency requirements
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import IsolationTest


class Test10NonRepeatableReadDefault(IsolationTest):
    """
    Test 10: Non-repeatable read with default isolation level.

    Tests default isolation behavior by attempting to create a non-repeatable read
    scenario without explicitly setting isolation level.
    """

    def __init__(self, pool, timeout_seconds: int = 60):
        """
        Initialize Test 10.

        Args:
            pool: DatabasePool instance
            timeout_seconds: Timeout for test execution (default: 60 seconds)
        """
        super().__init__(pool, timeout_seconds=timeout_seconds)

        self.test_value = f"nonrepeatable_default_test_{int(time.time())}"
        self.test_row_id = None

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 10: Non-repeatable read with default isolation level.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting non-repeatable read test (DEFAULT isolation level)...")
        print(f"  Isolation level: DEFAULT")
        print(f"  Test value: {self.test_value}")
        print(f"  Pass criteria: Non-repeatable reads must be PREVENTED")
        print(f"  Expected behavior:")
        if self.pool.is_cockroachdb:
            print(f"    - CockroachDB (default SERIALIZABLE): PASS - prevents non-repeatable reads")
        else:
            print(f"    - PostgreSQL (default READ COMMITTED): FAIL - allows non-repeatable reads")
            print(f"    - This test will FAIL to highlight insufficient default isolation")

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

            # Connection A: Enable multiple active portals (CockroachDB only)
            if self.pool.is_cockroachdb:
                await self.conn_a.execute("SET multiple_active_portals_enabled = true")

            # Connection A: Start transaction with DEFAULT isolation (no explicit level)
            print(f"\n  [Conn A] BEGIN (using default isolation level)")
            await self.conn_a.execute("BEGIN")

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

            # Connection A: Second read
            print(f"  [Conn A] Second read...")
            data_2 = await self.conn_a.fetchval(
                "SELECT data FROM isolation_test WHERE id = $1",
                self.test_row_id
            )
            print(f"  [Conn A] Second read: data = '{data_2}'")

            # Connection A: Commit
            print(f"  [Conn A] COMMIT")
            await self.conn_a.execute("COMMIT")

            # Analyze results based on database type
            if self.pool.is_cockroachdb:
                # CockroachDB default is SERIALIZABLE - should prevent non-repeatable read
                if data_1 == data_2:
                    result = {
                        'test': 'nonrepeatable_read_default',
                        'isolation_level': 'DEFAULT (SERIALIZABLE)',
                        'status': 'PASS',
                        'behavior': 'No non-repeatable read (SERIALIZABLE default)',
                        'data_1': data_1,
                        'data_2': data_2,
                        'nonrepeatable_read_occurred': False,
                        'description': 'CockroachDB default SERIALIZABLE prevented non-repeatable read'
                    }
                    print(f"\n  ✅ PASS: Consistent reads (values: '{data_1}' → '{data_2}')")
                else:
                    result = {
                        'test': 'nonrepeatable_read_default',
                        'isolation_level': 'DEFAULT (SERIALIZABLE)',
                        'status': 'FAIL',
                        'behavior': 'Non-repeatable read occurred (unexpected)',
                        'data_1': data_1,
                        'data_2': data_2,
                        'nonrepeatable_read_occurred': True,
                        'description': 'Unexpected: CockroachDB SERIALIZABLE should prevent non-repeatable reads'
                    }
                    print(f"\n  ❌ FAIL: Non-repeatable read (values: '{data_1}' → '{data_2}')")
            else:
                # PostgreSQL default is READ COMMITTED - test FAILS if non-repeatable reads occur
                if data_1 != data_2:
                    result = {
                        'test': 'nonrepeatable_read_default',
                        'isolation_level': 'DEFAULT (READ COMMITTED)',
                        'status': 'FAIL',
                        'behavior': 'NON-REPEATABLE READ DETECTED: Default isolation level allows non-repeatable reads',
                        'data_1': data_1,
                        'data_2': data_2,
                        'nonrepeatable_read_occurred': True,
                        'description': 'FAIL: Default isolation (READ COMMITTED) does not prevent non-repeatable reads. Consider using SERIALIZABLE isolation for critical transactions.'
                    }
                    print(f"\n  ❌ FAIL: Non-repeatable read detected with default isolation")
                    print(f"     Values changed: '{data_1}' → '{data_2}'")
                    print(f"     Default READ COMMITTED allows non-repeatable reads")
                    print(f"     Recommendation: Use SERIALIZABLE isolation if non-repeatable reads are unacceptable")
                else:
                    result = {
                        'test': 'nonrepeatable_read_default',
                        'isolation_level': 'DEFAULT (READ COMMITTED)',
                        'status': 'PASS',
                        'behavior': 'No non-repeatable read with default settings',
                        'data_1': data_1,
                        'data_2': data_2,
                        'nonrepeatable_read_occurred': False,
                        'description': 'PostgreSQL default READ COMMITTED prevented non-repeatable read'
                    }
                    print(f"\n  ✅ PASS: Consistent reads (values: '{data_1}' → '{data_2}')")

        except Exception as e:
            # Handle errors (e.g., serialization errors for CockroachDB)
            error_type = type(e).__name__
            error_msg = str(e)

            is_serialization_error = 'serialization' in error_msg.lower() or 'SQLSTATE 40001' in error_msg

            if self.pool.is_cockroachdb and is_serialization_error:
                result = {
                    'test': 'nonrepeatable_read_default',
                    'isolation_level': 'DEFAULT (SERIALIZABLE)',
                    'status': 'PASS',
                    'behavior': 'Serialization error raised',
                    'serialization_error': True,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'description': 'CockroachDB correctly raised serialization error'
                }
                print(f"\n  ✅ PASS: Serialization error raised (expected for SERIALIZABLE)")
            else:
                # Unexpected error
                result = {
                    'test': 'nonrepeatable_read_default',
                    'isolation_level': 'DEFAULT',
                    'status': 'ERROR',
                    'behavior': 'Unexpected error',
                    'serialization_error': False,
                    'error_type': error_type,
                    'error_message': error_msg,
                    'description': 'Unexpected error during test'
                }
                print(f"\n  ⚠️  ERROR: Unexpected error")
                print(f"     {error_type}: {error_msg}")

                self.metrics.record_error()

            # Rollback both connections
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

            # Cleanup
            await self.cleanup_test_data()

        return result

    async def cleanup_test_data(self):
        """Clean up test data."""
        try:
            async with self.get_connection() as conn:
                deleted = await conn.execute(
                    "DELETE FROM isolation_test WHERE id = $1",
                    self.test_row_id
                )
                print(f"  [Cleanup] Deleted test row {self.test_row_id}")
        except Exception as e:
            print(f"  [Cleanup] Warning: {e}")

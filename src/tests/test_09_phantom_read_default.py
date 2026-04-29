"""
Test 9: Phantom Read with Default Isolation Level

Purpose: Verify that default isolation level PREVENTS phantom reads.
Tests whether databases prevent phantom reads using their DEFAULT isolation levels.

Configuration:
- Isolation level: DEFAULT (no explicit setting)
  - CockroachDB default: SERIALIZABLE (should prevent phantom reads)
  - PostgreSQL default: READ COMMITTED (allows phantom reads)
- Scenario: Connection A counts rows, Connection B inserts, Connection A counts again
- Expected Results:
  - CockroachDB: PASS (consistent counts OR serialization error)
  - PostgreSQL: FAIL if phantom read occurs (default READ COMMITTED allows this)
- Pass Criteria: PASS if phantom reads are prevented, FAIL if phantom reads occur
- Purpose: Flag when default isolation is insufficient for data consistency requirements
"""

import asyncio
import time
from typing import Dict, Any

from src.tests.base import IsolationTest


class Test09PhantomReadDefault(IsolationTest):
    """
    Test 9: Phantom read with default isolation level.

    Tests default isolation behavior by attempting to create a phantom read
    scenario without explicitly setting isolation level.
    """

    def __init__(self, pool, timeout_seconds: int = 60):
        """
        Initialize Test 9.

        Args:
            pool: DatabasePool instance
            timeout_seconds: Timeout for test execution (default: 60 seconds)
        """
        super().__init__(pool, timeout_seconds=timeout_seconds)

        self.test_value = f"phantom_default_test_{int(time.time())}"

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 9: Phantom read with default isolation level.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting phantom read test (DEFAULT isolation level)...")
        print(f"  Isolation level: DEFAULT")
        print(f"  Test value: {self.test_value}")
        print(f"  Pass criteria: Phantom reads must be PREVENTED")
        print(f"  Expected behavior:")
        if self.pool.is_cockroachdb:
            print(f"    - CockroachDB (default SERIALIZABLE): PASS - prevents phantom reads")
        else:
            print(f"    - PostgreSQL (default READ COMMITTED): FAIL - allows phantom reads")
            print(f"    - This test will FAIL to highlight insufficient default isolation")

        try:
            # Acquire two separate connections
            await self.acquire_connections()

            # Connection A: Enable multiple active portals (CockroachDB only)
            if self.pool.is_cockroachdb:
                await self.conn_a.execute("SET multiple_active_portals_enabled = true")

            # Connection A: Start transaction with DEFAULT isolation (no explicit level)
            print(f"\n  [Conn A] BEGIN (using default isolation level)")
            await self.conn_a.execute("BEGIN")

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
                "phantom_row_default"
            )
            await self.conn_b.execute("COMMIT")
            print(f"  [Conn B] Inserted 1 row with test_value = '{self.test_value}'")

            # Connection A: Second count
            print(f"  [Conn A] Second count...")
            count_2 = await self.conn_a.fetchval(
                "SELECT COUNT(*) FROM isolation_test WHERE test_value = $1",
                self.test_value
            )
            print(f"  [Conn A] Second count: {count_2}")

            # Connection A: Commit
            print(f"  [Conn A] COMMIT")
            await self.conn_a.execute("COMMIT")

            # Analyze results based on database type
            if self.pool.is_cockroachdb:
                # CockroachDB default is SERIALIZABLE - should prevent phantom read
                if count_1 == count_2:
                    result = {
                        'test': 'phantom_read_default',
                        'isolation_level': 'DEFAULT (SERIALIZABLE)',
                        'status': 'PASS',
                        'behavior': 'No phantom read (SERIALIZABLE default)',
                        'count_1': count_1,
                        'count_2': count_2,
                        'phantom_read_occurred': False,
                        'description': 'CockroachDB default SERIALIZABLE prevented phantom read'
                    }
                    print(f"\n  ✅ PASS: No phantom read (counts: {count_1} → {count_2})")
                else:
                    result = {
                        'test': 'phantom_read_default',
                        'isolation_level': 'DEFAULT (SERIALIZABLE)',
                        'status': 'FAIL',
                        'behavior': 'Phantom read occurred (unexpected)',
                        'count_1': count_1,
                        'count_2': count_2,
                        'phantom_read_occurred': True,
                        'description': 'Unexpected: CockroachDB SERIALIZABLE should prevent phantom reads'
                    }
                    print(f"\n  ❌ FAIL: Phantom read detected (counts: {count_1} → {count_2})")
            else:
                # PostgreSQL default is READ COMMITTED - test FAILS if phantom reads occur
                if count_1 != count_2:
                    result = {
                        'test': 'phantom_read_default',
                        'isolation_level': 'DEFAULT (READ COMMITTED)',
                        'status': 'FAIL',
                        'behavior': 'PHANTOM READ DETECTED: Default isolation level allows phantom reads',
                        'count_1': count_1,
                        'count_2': count_2,
                        'phantom_read_occurred': True,
                        'description': 'FAIL: Default isolation (READ COMMITTED) does not prevent phantom reads. Consider using SERIALIZABLE isolation for critical transactions.'
                    }
                    print(f"\n  ❌ FAIL: Phantom read detected with default isolation")
                    print(f"     Counts changed: {count_1} → {count_2}")
                    print(f"     Default READ COMMITTED allows phantom reads")
                    print(f"     Recommendation: Use SERIALIZABLE isolation if phantom reads are unacceptable")
                else:
                    result = {
                        'test': 'phantom_read_default',
                        'isolation_level': 'DEFAULT (READ COMMITTED)',
                        'status': 'PASS',
                        'behavior': 'No phantom read with default settings',
                        'count_1': count_1,
                        'count_2': count_2,
                        'phantom_read_occurred': False,
                        'description': 'PostgreSQL default READ COMMITTED prevented phantom read'
                    }
                    print(f"\n  ✅ PASS: No phantom read (counts: {count_1} → {count_2})")

        except Exception as e:
            # Handle errors (e.g., serialization errors for CockroachDB)
            error_type = type(e).__name__
            error_msg = str(e)

            is_serialization_error = 'serialization' in error_msg.lower() or 'SQLSTATE 40001' in error_msg

            if self.pool.is_cockroachdb and is_serialization_error:
                result = {
                    'test': 'phantom_read_default',
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
                    'test': 'phantom_read_default',
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
                    "DELETE FROM isolation_test WHERE test_value = $1",
                    self.test_value
                )
                print(f"  [Cleanup] Deleted test rows: {deleted}")
        except Exception as e:
            print(f"  [Cleanup] Warning: {e}")

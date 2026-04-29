"""
Test 3: Standard pgbench TPC-B Workload

Purpose: Industry-standard OLTP mixed read/write workload.
Tests transactional performance with updates and inserts.

Configuration:
- Duration: 5 minutes (300 seconds) per database
- Concurrency: 16 workers
- Transaction: UPDATE accounts, SELECT, UPDATE tellers, UPDATE branches, INSERT history
- Metrics: TPS, p50/p95/p99 transaction latency (ms), error count, retry count
"""

import asyncio
import random
import time
from typing import Dict, Any

from src.tests.base import BaseTest
from src.retry_logic import TransactionRetryHandler


class Test03PgBench(BaseTest):
    """
    Test 3: pgbench TPC-B workload.

    Executes the standard TPC-B transaction pattern with concurrent workers
    for a fixed duration. Includes retry logic for serialization errors.
    """

    def __init__(self, pool, duration_seconds: int = 300, concurrency: int = 16):
        """
        Initialize Test 3.

        Args:
            pool: DatabasePool instance
            duration_seconds: Test duration in seconds (default: 300 = 5 minutes)
            concurrency: Number of concurrent workers (default: 16)
        """
        super().__init__(pool)

        self.duration_seconds = duration_seconds
        self.concurrency = concurrency

        # TPC-B data ranges (based on loaded data)
        self.max_aid = 5_000_000    # accounts
        self.max_tid = 500_000      # tellers
        self.max_bid = 50_000       # branches

        # Transaction retry handler (separate from base retry_handler)
        self.txn_retry_handler = TransactionRetryHandler(max_retries=3)

        # Statistics
        self.successful_txns = 0
        self.failed_txns = 0

    async def execute(self) -> Dict[str, Any]:
        """
        Execute Test 3: pgbench TPC-B workload.

        Returns:
            Dictionary with test results
        """
        print(f"\nExecuting TPC-B workload for {self.duration_seconds}s with {self.concurrency} workers...")
        print(f"  Transaction: UPDATE accounts → SELECT → UPDATE tellers → UPDATE branches → INSERT history")
        print(f"  Max retries: 3 (exponential backoff)")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)

        # End time for duration-based execution
        end_time = time.time() + self.duration_seconds

        # Counters
        completed = {'count': 0, 'failed': 0, 'first_error': None}
        lock = asyncio.Lock()

        async def tpcb_worker():
            """Execute TPC-B transactions until end time."""
            try:
                async with semaphore:
                    async with self.get_connection() as conn:
                        while time.time() < end_time:
                            try:
                                # Execute one TPC-B transaction
                                latency_ms = await self._execute_tpcb_transaction(conn)

                                # Record latency
                                self.metrics.record_latency(latency_ms)

                                # Update counter
                                async with lock:
                                    completed['count'] += 1
                                    if completed['count'] % 100 == 0:
                                        elapsed = time.time() - (end_time - self.duration_seconds)
                                        tps = completed['count'] / elapsed if elapsed > 0 else 0
                                        remaining = int(end_time - time.time())
                                        print(f"  Progress: {completed['count']:,} txns, "
                                              f"{tps:.0f} TPS, {remaining}s remaining", end='\r')

                            except Exception as e:
                                # Transaction failed after retries
                                self.metrics.record_error()
                                async with lock:
                                    completed['failed'] += 1
                                    # Capture first error for detailed logging
                                    if completed['first_error'] is None:
                                        completed['first_error'] = e
                                    # Log first few errors for debugging
                                    if completed['failed'] <= 5:
                                        print(f"\n  ⚠️  Transaction failed: {type(e).__name__}: {e}")
            except Exception as e:
                # Worker-level error (e.g., connection acquisition failed)
                async with lock:
                    if completed['failed'] == 0:  # Log first worker error
                        print(f"\n  ❌ Worker failed: {type(e).__name__}: {e}")

        # Launch workers
        workers = [tpcb_worker() for _ in range(self.concurrency)]
        await asyncio.gather(*workers, return_exceptions=True)

        print(f"  Progress: {completed['count']:,} txns completed, "
              f"{completed['failed']} failed ✓")

        # Log first error details if any transactions failed
        if completed['failed'] > 0 and completed['first_error']:
            print(f"\n  First error details:")
            print(f"    Type: {type(completed['first_error']).__name__}")
            print(f"    Message: {completed['first_error']}")
            if hasattr(completed['first_error'], 'sqlstate'):
                print(f"    SQLSTATE: {completed['first_error'].sqlstate}")

        self.successful_txns = completed['count']
        self.failed_txns = completed['failed']

        # Calculate TPS
        tps = self.successful_txns / self.duration_seconds if self.duration_seconds > 0 else 0

        # Get retry statistics
        retry_stats = self.txn_retry_handler.get_stats()

        # Return summary
        return {
            'duration_seconds': self.duration_seconds,
            'concurrency': self.concurrency,
            'successful_transactions': self.successful_txns,
            'failed_transactions': self.failed_txns,
            'tps': tps,
            'retries': retry_stats.total_retries,
            'serialization_errors': retry_stats.serialization_errors,
            'description': 'Standard pgbench TPC-B workload with 16 concurrent workers'
        }

    async def _execute_tpcb_transaction(self, conn) -> float:
        """
        Execute a single TPC-B transaction.

        Args:
            conn: Database connection

        Returns:
            Transaction latency in milliseconds
        """
        # Generate random parameters
        aid = random.randint(1, self.max_aid)
        tid = random.randint(1, self.max_tid)
        bid = random.randint(1, self.max_bid)
        delta = random.randint(-5000, 5000)

        start = time.perf_counter()

        # Execute transaction with retry logic
        async def transaction_logic(conn):
            # UPDATE pgbench_accounts
            await conn.execute(
                'UPDATE pgbench_accounts SET abalance = abalance + $1 WHERE aid = $2',
                delta, aid
            )

            # SELECT from pgbench_accounts
            await conn.fetchval(
                'SELECT abalance FROM pgbench_accounts WHERE aid = $1',
                aid
            )

            # UPDATE pgbench_tellers
            await conn.execute(
                'UPDATE pgbench_tellers SET tbalance = tbalance + $1 WHERE tid = $2',
                delta, tid
            )

            # UPDATE pgbench_branches
            await conn.execute(
                'UPDATE pgbench_branches SET bbalance = bbalance + $1 WHERE bid = $2',
                delta, bid
            )

            # INSERT INTO pgbench_history
            await conn.execute(
                'INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES ($1, $2, $3, $4, NOW())',
                tid, bid, aid, delta
            )

        # Execute with retry handler
        await self.txn_retry_handler.execute_transaction(
            conn,
            transaction_logic
        )

        latency_ms = (time.perf_counter() - start) * 1000

        return latency_ms


async def test_pgbench():
    """Test the Test03PgBench implementation (mock)."""
    print("=" * 70)
    print("Test 03: pgbench TPC-B - Implementation Test")
    print("=" * 70)

    # Mock pool for testing
    class MockConnection:
        async def execute(self, query, *args):
            await asyncio.sleep(0.001)
            return None

        async def fetchval(self, query, *args):
            await asyncio.sleep(0.001)
            return 0

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

    # Create test with reduced duration for testing
    pool = MockPool()
    test = Test03PgBench(pool, duration_seconds=2, concurrency=4)

    print(f"\n✅ Test instantiated: {test.test_name}")
    print(f"   Duration: {test.duration_seconds}s")
    print(f"   Concurrency: {test.concurrency}")

    # Run test
    result = await test.run()

    print(f"\n✅ Test completed: {result.status}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    if result.custom_metrics:
        print(f"   Transactions: {result.custom_metrics.get('successful_transactions', 0):,}")
        print(f"   TPS: {result.custom_metrics.get('tps', 0):.0f}")
        print(f"   Retries: {result.custom_metrics.get('retries', 0)}")

    if result.percentiles:
        print(f"   Txn latency p50: {result.percentiles['p50']:.2f} ms")
        print(f"   Txn latency p95: {result.percentiles['p95']:.2f} ms")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    asyncio.run(test_pgbench())

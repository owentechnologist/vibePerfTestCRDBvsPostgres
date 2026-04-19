#!/usr/bin/env python3
"""
Test metrics and retry logic modules.

Comprehensive tests for MetricsCollector, RetryHandler, and related utilities.
"""

import asyncio
import sys
import time


def test_metrics_collector():
    """Test MetricsCollector functionality."""
    print("\n" + "=" * 70)
    print("Testing MetricsCollector")
    print("=" * 70)

    from src.metrics import MetricsCollector, format_latency, format_throughput

    # Create collector
    collector = MetricsCollector()

    # Test 1: Record latencies
    print("\n[1/6] Testing latency recording...")
    collector.start_timer()

    for i in range(100):
        collector.record_latency(float(i))

    if len(collector) == 100:
        print(f"  ✅ Recorded {len(collector)} samples")
    else:
        print(f"  ❌ Expected 100 samples, got {len(collector)}")
        return False

    # Test 2: Error counting
    print("\n[2/6] Testing error/retry counting...")
    collector.record_error()
    collector.record_error()
    collector.record_retry()

    if collector.error_count == 2 and collector.retry_count == 1:
        print(f"  ✅ Error count: {collector.error_count}, Retry count: {collector.retry_count}")
    else:
        print(f"  ❌ Error/retry counts incorrect")
        return False

    # Test 3: Custom metrics
    print("\n[3/6] Testing custom metrics...")
    collector.add_custom_metric('test_key', 'test_value')

    if 'test_key' in collector.custom_metrics:
        print(f"  ✅ Custom metric added: {collector.custom_metrics['test_key']}")
    else:
        print(f"  ❌ Custom metric not found")
        return False

    # Test 4: Percentiles
    print("\n[4/6] Testing percentile computation...")
    time.sleep(0.05)
    collector.stop_timer()

    try:
        percentiles = collector.compute_percentiles()
        print(f"  ✅ p50: {format_latency(percentiles.p50)}")
        print(f"  ✅ p95: {format_latency(percentiles.p95)}")
        print(f"  ✅ p99: {format_latency(percentiles.p99)}")

        if percentiles.p50 <= percentiles.p95 <= percentiles.p99:
            print(f"  ✅ Percentiles are properly ordered")
        else:
            print(f"  ❌ Percentiles not properly ordered")
            return False

    except Exception as e:
        print(f"  ❌ Percentile computation failed: {e}")
        return False

    # Test 5: Throughput
    print("\n[5/6] Testing throughput computation...")
    try:
        throughput = collector.compute_throughput()
        print(f"  ✅ QPS: {format_throughput(throughput.qps)}")

        if throughput.total_operations == 100:
            print(f"  ✅ Operation count correct: {throughput.total_operations}")
        else:
            print(f"  ❌ Operation count incorrect: {throughput.total_operations}")
            return False

    except Exception as e:
        print(f"  ❌ Throughput computation failed: {e}")
        return False

    # Test 6: Memory usage
    print("\n[6/6] Testing memory usage estimation...")
    mem_mb = collector.get_memory_usage_mb()
    print(f"  ✅ Memory usage: {mem_mb:.4f} MB")

    if mem_mb > 0:
        print(f"  ✅ Memory usage calculated")
    else:
        print(f"  ❌ Memory usage calculation failed")
        return False

    return True


def test_aggregate_metrics():
    """Test AggregateMetrics functionality."""
    print("\n" + "=" * 70)
    print("Testing AggregateMetrics")
    print("=" * 70)

    from src.metrics import AggregateMetrics

    agg = AggregateMetrics()

    # Add multiple runs
    print("\n[1/2] Testing run aggregation...")
    for i in range(3):
        run_metrics = {
            'duration_seconds': 1.0 + i * 0.5,
            'percentiles': {'p50': 10.0 + i}
        }
        agg.add_run(run_metrics)

    if len(agg.runs) == 3:
        print(f"  ✅ Added {len(agg.runs)} runs")
    else:
        print(f"  ❌ Expected 3 runs, got {len(agg.runs)}")
        return False

    # Compute stats
    print("\n[2/2] Testing statistics computation...")
    stats = agg.compute_stats()

    if 'min_time_seconds' in stats and 'median_time_seconds' in stats:
        print(f"  ✅ Min time: {stats['min_time_seconds']:.2f}s")
        print(f"  ✅ Median time: {stats['median_time_seconds']:.2f}s")
        print(f"  ✅ Max time: {stats['max_time_seconds']:.2f}s")

        # Verify ordering
        if stats['min_time_seconds'] <= stats['median_time_seconds'] <= stats['max_time_seconds']:
            print(f"  ✅ Statistics are properly ordered")
        else:
            print(f"  ❌ Statistics not properly ordered")
            return False
    else:
        print(f"  ❌ Statistics computation failed")
        return False

    return True


async def test_retry_handler():
    """Test RetryHandler functionality."""
    print("\n" + "=" * 70)
    print("Testing RetryHandler")
    print("=" * 70)

    from src.retry_logic import RetryHandler

    handler = RetryHandler(max_retries=2, base_backoff_ms=10, max_backoff_ms=100)

    # Test 1: Successful operation
    print("\n[1/4] Testing successful operation...")

    async def success_op():
        return "success"

    result = await handler.execute_with_retry(success_op)

    if result == "success" and handler.stats.total_retries == 0:
        print(f"  ✅ Operation succeeded without retries")
    else:
        print(f"  ❌ Unexpected behavior")
        return False

    # Test 2: Retryable error that succeeds
    print("\n[2/4] Testing retryable error (succeeds on retry)...")
    handler.reset_stats()

    counter = {'attempts': 0}

    async def retry_then_success():
        counter['attempts'] += 1
        if counter['attempts'] == 1:
            error = Exception("Serialization error")
            error.sqlstate = '40001'
            raise error
        return "success after retry"

    result = await handler.execute_with_retry(retry_then_success)

    if result == "success after retry" and handler.stats.total_retries == 1:
        print(f"  ✅ Operation succeeded after 1 retry")
        print(f"     Serialization errors: {handler.stats.serialization_errors}")
    else:
        print(f"  ❌ Unexpected retry behavior")
        return False

    # Test 3: Non-retryable error
    print("\n[3/4] Testing non-retryable error...")
    handler.reset_stats()

    async def non_retryable():
        raise ValueError("Not retryable")

    try:
        await handler.execute_with_retry(non_retryable)
        print(f"  ❌ Should have raised ValueError")
        return False
    except ValueError:
        if handler.stats.total_retries == 0:
            print(f"  ✅ Non-retryable error raised immediately")
        else:
            print(f"  ❌ Incorrectly retried non-retryable error")
            return False

    # Test 4: Backoff calculation
    print("\n[4/4] Testing backoff calculation...")

    backoff_0 = handler.calculate_backoff(0)
    backoff_1 = handler.calculate_backoff(1)
    backoff_2 = handler.calculate_backoff(2)

    print(f"  ✅ Backoff attempt 0: {backoff_0*1000:.1f} ms")
    print(f"  ✅ Backoff attempt 1: {backoff_1*1000:.1f} ms")
    print(f"  ✅ Backoff attempt 2: {backoff_2*1000:.1f} ms")

    if backoff_0 < backoff_1 < backoff_2:
        print(f"  ✅ Backoff increases exponentially")
    else:
        print(f"  ❌ Backoff not increasing properly")
        return False

    return True


async def test_transaction_retry_handler():
    """Test TransactionRetryHandler functionality."""
    print("\n" + "=" * 70)
    print("Testing TransactionRetryHandler")
    print("=" * 70)

    from src.retry_logic import TransactionRetryHandler

    handler = TransactionRetryHandler(max_retries=2)

    # Mock connection
    class MockConnection:
        def __init__(self):
            self.commands = []

        async def execute(self, cmd):
            self.commands.append(cmd)
            return None

    # Test successful transaction
    print("\n[1/1] Testing transaction execution...")

    conn = MockConnection()

    async def transaction_logic(conn):
        await conn.execute("SELECT 1")
        return "transaction_result"

    result = await handler.execute_transaction(conn, transaction_logic)

    if result == "transaction_result":
        print(f"  ✅ Transaction executed successfully")
    else:
        print(f"  ❌ Transaction failed")
        return False

    if 'BEGIN' in conn.commands and 'COMMIT' in conn.commands:
        print(f"  ✅ Transaction BEGIN and COMMIT executed")
    else:
        print(f"  ❌ Transaction commands not found")
        return False

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Metrics and Retry Logic Test Suite")
    print("=" * 70)

    results = []

    # Synchronous tests
    results.append(('MetricsCollector', test_metrics_collector()))
    results.append(('AggregateMetrics', test_aggregate_metrics()))

    # Asynchronous tests
    async def run_async_tests():
        retry_result = await test_retry_handler()
        txn_result = await test_transaction_retry_handler()
        return retry_result, txn_result

    async_results = asyncio.run(run_async_tests())
    results.append(('RetryHandler', async_results[0]))
    results.append(('TransactionRetryHandler', async_results[1]))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

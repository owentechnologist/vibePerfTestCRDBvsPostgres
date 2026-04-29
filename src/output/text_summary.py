"""
Text Summary Writer - Generate concise plain text summary.

Provides human-readable console output summarizing benchmark results.
Includes winner determination and key metrics comparison.
"""

from pathlib import Path
from typing import Dict, Any, Optional


def generate_text_summary(results: Dict[str, Any]) -> str:
    """
    Generate plain text summary of benchmark results.

    Args:
        results: Results dictionary from TestRunner

    Returns:
        Formatted text summary (< 50 lines)
    """
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("BENCHMARK RESULTS SUMMARY")
    lines.append("=" * 70)

    # Benchmark info
    info = results.get('benchmark_info', {})
    lines.append(f"\nExecution Time: {info.get('start_time', 'N/A')} - {info.get('end_time', 'N/A')}")
    lines.append(f"Total Duration: {info.get('total_duration_seconds', 0):.2f}s")

    # Database versions
    lines.append("\nDatabases:")
    dbs = results.get('databases', {})
    crdb = dbs.get('cockroachdb', {})
    pg = dbs.get('azure_postgresql', {})
    lines.append(f"  CockroachDB:       {crdb.get('version', 'N/A')}")
    lines.append(f"  Azure PostgreSQL:  {pg.get('version', 'N/A')}")

    # Test results comparison
    test_results_crdb = results.get('test_results', {}).get('cockroachdb', {})
    test_results_pg = results.get('test_results', {}).get('azure_postgresql', {})

    # Check if only CockroachDB is being tested
    crdb_configured = crdb.get('configured', False)
    pg_configured = pg.get('configured', False)

    if crdb_configured and not pg_configured:
        # CockroachDB-only detailed output
        lines.append("\n" + "=" * 70)
        lines.append("COCKROACHDB PERFORMANCE RESULTS")
        lines.append("=" * 70)
        lines.extend(_format_crdb_only_results(test_results_crdb))
    else:
        # Comparison mode (original format)
        lines.append("\nTest Results:")
        lines.append("-" * 70)

        # Categorize tests
        oltp_tests = ['test_01', 'test_02', 'test_03']
        olap_tests = ['test_04', 'test_05', 'test_06']
        isolation_tests = ['test_07', 'test_08', 'test_09', 'test_10']

        # OLTP Results
        lines.append("\nOLTP Tests (Lower latency is better):")
        for test_key in oltp_tests:
            test_name = _get_test_name(test_key)
            crdb_result = test_results_crdb.get(test_key, {})
            pg_result = test_results_pg.get(test_key, {})

            lines.append(f"\n  {test_name}:")
            lines.extend(_format_test_comparison(crdb_result, pg_result))

        # OLAP Results
        lines.append("\nOLAP Tests (Lower execution time is better):")
        for test_key in olap_tests:
            test_name = _get_test_name(test_key)
            crdb_result = test_results_crdb.get(test_key, {})
            pg_result = test_results_pg.get(test_key, {})

            lines.append(f"\n  {test_name}:")
            lines.extend(_format_test_comparison(crdb_result, pg_result))

        # Isolation Results
        lines.append("\nIsolation Tests:")
        for test_key in isolation_tests:
            test_name = _get_test_name(test_key)
            crdb_result = test_results_crdb.get(test_key, {})
            pg_result = test_results_pg.get(test_key, {})

            lines.append(f"\n  {test_name}:")
            lines.extend(_format_isolation_test(crdb_result, pg_result))

    # Overall summary
    lines.append("\n" + "=" * 70)
    lines.append("OVERALL SUMMARY")
    lines.append("=" * 70)

    summary = results.get('execution_summary', {})

    # CockroachDB summary
    crdb_tested = 10 - summary.get('cockroachdb_not_tested', 0)
    if crdb_tested > 0:
        lines.append(f"\nCockroachDB:       {summary.get('cockroachdb_success', 0)}/{crdb_tested} tests passed")
    else:
        lines.append(f"\nCockroachDB:       NOT TESTED (no connection configured)")

    # Azure PostgreSQL summary
    pg_tested = 10 - summary.get('azure_postgresql_not_tested', 0)
    if pg_tested > 0:
        lines.append(f"Azure PostgreSQL:  {summary.get('azure_postgresql_success', 0)}/{pg_tested} tests passed")
    else:
        lines.append(f"Azure PostgreSQL:  NOT TESTED (no connection configured)")

    # Determine overall winner (only if at least one DB was tested)
    if crdb_tested > 0 or pg_tested > 0:
        winner = _determine_overall_winner(results)
        if winner:
            lines.append(f"\n🏆 Overall Winner: {winner}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def write_text_summary(results: Dict[str, Any], output_path: str) -> None:
    """
    Write text summary to file.

    Args:
        results: Results dictionary from TestRunner
        output_path: Path to output text file

    Raises:
        IOError: If file cannot be written
    """
    print(f"\nWriting text summary to: {output_path}")

    # Create output directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate summary
    summary_text = generate_text_summary(results)

    # Write to file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)

        file_size = output_file.stat().st_size
        line_count = summary_text.count('\n') + 1
        print(f"✅ Text summary written successfully ({line_count} lines, {file_size:,} bytes)")

    except (IOError, OSError) as e:
        print(f"❌ Failed to write text summary: {e}")
        raise


def _format_crdb_only_results(test_results: Dict[str, Any]) -> list:
    """
    Format detailed CockroachDB-only results with p50, p99, p99.99 for all tests.

    Args:
        test_results: CockroachDB test results dictionary

    Returns:
        List of formatted lines
    """
    lines = []

    # Header for performance table
    lines.append("\nPerformance Metrics:")
    lines.append("-" * 70)
    lines.append(f"{'Test':<35} {'Status':<10} {'p50':<12} {'p99':<12} {'p99.99':<12}")
    lines.append("-" * 70)

    # Iterate through all 10 tests in order
    for test_num in range(1, 11):
        test_key = f'test_{test_num:02d}'
        test_result = test_results.get(test_key, {})
        test_name = _get_short_test_name(test_key)
        status = test_result.get('status', 'NOT TESTED')

        # Get percentiles
        percentiles = test_result.get('percentiles') or {}
        custom_metrics = test_result.get('custom_metrics') or {}

        if status == 'SUCCESS':
            # Check if we have latency percentiles (tests 1-2)
            if percentiles and 'p50' in percentiles:
                p50 = percentiles.get('p50', 0)
                p99 = percentiles.get('p99', 0)
                p99_99 = percentiles.get('p99_99', 0)
                lines.append(f"{test_name:<35} {'✓ PASS':<10} {p50:>10.2f}ms {p99:>10.2f}ms {p99_99:>10.2f}ms")

            # Check for OLAP tests with median time (tests 4-6)
            elif 'median_time_seconds' in custom_metrics:
                median = custom_metrics.get('median_time_seconds', 0)
                min_time = custom_metrics.get('min_time_seconds', 0)
                max_time = custom_metrics.get('max_time_seconds', 0)
                lines.append(f"{test_name:<35} {'✓ PASS':<10} {median:>10.2f}s  {min_time:>10.2f}s  {max_time:>10.2f}s")
                lines.append(f"{'':>45}  {'(median)':<10} {'(min)':<12} {'(max)':<12}")

            # Check for TPC-B test (test 3)
            elif 'tps' in custom_metrics:
                tps = custom_metrics.get('tps', 0)
                failed = custom_metrics.get('failed_transactions', 0)
                successful = custom_metrics.get('successful_transactions', 0)
                lines.append(f"{test_name:<35} {'✓ PASS':<10} {tps:>10.1f} TPS  (success: {successful}, failed: {failed})")

            # Isolation tests (tests 7-8)
            elif 'isolation_level' in custom_metrics:
                iso_status = custom_metrics.get('status', 'UNKNOWN')
                behavior = custom_metrics.get('behavior', 'N/A')
                if iso_status == 'PASS':
                    lines.append(f"{test_name:<35} {'✓ PASS':<10} {behavior}")
                elif iso_status == 'ERROR':
                    error_msg = custom_metrics.get('error_message', 'Unknown error')[:40]
                    lines.append(f"{test_name:<35} {'✗ ERROR':<10} {error_msg}")
                else:
                    lines.append(f"{test_name:<35} {'✗ FAIL':<10} {behavior}")
            else:
                lines.append(f"{test_name:<35} {'✓ PASS':<10} (no latency data)")

        elif status == 'ERROR' or status == 'FAILURE':
            error_msg = test_result.get('error_message', 'Unknown error')
            if error_msg:
                lines.append(f"{test_name:<35} {'✗ FAIL':<10} {error_msg[:40]}")
            else:
                lines.append(f"{test_name:<35} {'✗ FAIL':<10}")

        else:
            lines.append(f"{test_name:<35} {status:<10}")

    lines.append("-" * 70)

    return lines


def _get_short_test_name(test_key: str) -> str:
    """Get short test name for table display."""
    test_names = {
        'test_01': 'Test 1: SELECT 1',
        'test_02': 'Test 2: Point Lookup',
        'test_03': 'Test 3: TPC-B Workload',
        'test_04': 'Test 4: ROLLUP Aggregation',
        'test_05': 'Test 5: Window Functions',
        'test_06': 'Test 6: Cross-Table JOIN',
        'test_07': 'Test 7: Phantom Read',
        'test_08': 'Test 8: Non-Repeatable Read',
        'test_09': 'Test 9: Phantom Read (Default)',
        'test_10': 'Test 10: Non-Repeatable Read (Default)',
    }
    return test_names.get(test_key, test_key)


def _get_test_name(test_key: str) -> str:
    """Get human-readable test name."""
    test_names = {
        'test_01': 'Test 1: SELECT 1 Latency',
        'test_02': 'Test 2: Point Lookup',
        'test_03': 'Test 3: TPC-B Workload',
        'test_04': 'Test 4: ROLLUP Aggregation',
        'test_05': 'Test 5: Window Functions',
        'test_06': 'Test 6: Cross-Table JOIN',
        'test_07': 'Test 7: Phantom Read',
        'test_08': 'Test 8: Non-Repeatable Read',
        'test_09': 'Test 9: Phantom Read (Default Isolation)',
        'test_10': 'Test 10: Non-Repeatable Read (Default Isolation)',
    }
    return test_names.get(test_key, test_key)


def _format_test_comparison(crdb_result: Dict[str, Any], pg_result: Dict[str, Any]) -> list:
    """Format comparison for OLTP/OLAP tests."""
    lines = []

    crdb_status = crdb_result.get('status', 'N/A')
    pg_status = pg_result.get('status', 'N/A')

    # Handle NOT TESTED status
    if crdb_status == 'NOT TESTED' and pg_status == 'NOT TESTED':
        lines.append(f"    CRDB: NOT TESTED  |  PG: NOT TESTED")
        return lines
    elif crdb_status == 'NOT TESTED':
        lines.append(f"    CRDB: NOT TESTED  |  PG: {pg_status}")
        return lines
    elif pg_status == 'NOT TESTED':
        lines.append(f"    CRDB: {crdb_status}  |  PG: NOT TESTED")
        return lines

    # Check if both tests succeeded
    if crdb_status == 'SUCCESS' and pg_status == 'SUCCESS':
        # Get key metrics
        crdb_duration = crdb_result.get('duration_seconds', 0)
        pg_duration = pg_result.get('duration_seconds', 0)

        crdb_p50 = (crdb_result.get('percentiles') or {}).get('p50')
        pg_p50 = (pg_result.get('percentiles') or {}).get('p50')

        crdb_tps = (crdb_result.get('throughput') or {}).get('tps')
        pg_tps = (pg_result.get('throughput') or {}).get('tps')

        crdb_median = (crdb_result.get('custom_metrics') or {}).get('median_time_seconds')
        pg_median = (pg_result.get('custom_metrics') or {}).get('median_time_seconds')

        # Format based on available metrics
        if crdb_p50 and pg_p50:
            # Latency test
            winner = "CRDB" if crdb_p50 < pg_p50 else "PG"
            delta_pct = abs((pg_p50 - crdb_p50) / crdb_p50 * 100) if crdb_p50 > 0 else 0
            lines.append(f"    CRDB p50: {crdb_p50:.2f}ms  |  PG p50: {pg_p50:.2f}ms  |  Winner: {winner} ({delta_pct:.1f}% faster)")

        elif crdb_tps and pg_tps:
            # Throughput test
            winner = "CRDB" if crdb_tps > pg_tps else "PG"
            delta_pct = abs((crdb_tps - pg_tps) / pg_tps * 100) if pg_tps > 0 else 0
            lines.append(f"    CRDB TPS: {crdb_tps:.0f}  |  PG TPS: {pg_tps:.0f}  |  Winner: {winner} ({delta_pct:.1f}% higher)")

        elif crdb_median and pg_median:
            # OLAP test with median time
            winner = "CRDB" if crdb_median < pg_median else "PG"
            delta_pct = abs((pg_median - crdb_median) / crdb_median * 100) if crdb_median > 0 else 0
            lines.append(f"    CRDB median: {crdb_median:.2f}s  |  PG median: {pg_median:.2f}s  |  Winner: {winner} ({delta_pct:.1f}% faster)")

        else:
            # Fallback to duration
            winner = "CRDB" if crdb_duration < pg_duration else "PG"
            lines.append(f"    CRDB: {crdb_duration:.2f}s  |  PG: {pg_duration:.2f}s  |  Winner: {winner}")

    else:
        # One or both tests failed
        lines.append(f"    CRDB: {crdb_status}  |  PG: {pg_status}")

    return lines


def _format_isolation_test(crdb_result: Dict[str, Any], pg_result: Dict[str, Any]) -> list:
    """Format comparison for isolation tests."""
    lines = []

    # Handle NOT TESTED status
    crdb_result_status = crdb_result.get('status', 'N/A')
    pg_result_status = pg_result.get('status', 'N/A')

    if crdb_result_status == 'NOT TESTED' and pg_result_status == 'NOT TESTED':
        lines.append(f"    CRDB: NOT TESTED  |  PG: NOT TESTED")
        return lines
    elif crdb_result_status == 'NOT TESTED':
        lines.append(f"    CRDB: NOT TESTED")
        pg_metrics = pg_result.get('custom_metrics') or {}
        pg_status = pg_metrics.get('status', 'N/A')
        pg_behavior = pg_metrics.get('behavior', 'N/A')
        lines.append(f"    PG:   {pg_status} ({pg_behavior})")
        return lines
    elif pg_result_status == 'NOT TESTED':
        crdb_metrics = crdb_result.get('custom_metrics') or {}
        crdb_status = crdb_metrics.get('status', 'N/A')
        crdb_behavior = crdb_metrics.get('behavior', 'N/A')
        lines.append(f"    CRDB: {crdb_status} ({crdb_behavior})")
        lines.append(f"    PG:   NOT TESTED")
        return lines

    # Normal case - both tested
    crdb_metrics = crdb_result.get('custom_metrics') or {}
    pg_metrics = pg_result.get('custom_metrics') or {}

    crdb_status = crdb_metrics.get('status', 'N/A')
    pg_status = pg_metrics.get('status', 'N/A')

    crdb_behavior = crdb_metrics.get('behavior', 'N/A')
    pg_behavior = pg_metrics.get('behavior', 'N/A')

    lines.append(f"    CRDB: {crdb_status} ({crdb_behavior})")
    lines.append(f"    PG:   {pg_status} ({pg_behavior})")

    return lines


def _determine_overall_winner(results: Dict[str, Any]) -> Optional[str]:
    """
    Determine overall winner based on all test results.

    Args:
        results: Results dictionary

    Returns:
        Winner name or None if tie
    """
    crdb_wins = 0
    pg_wins = 0

    test_results_crdb = results.get('test_results', {}).get('cockroachdb', {})
    test_results_pg = results.get('test_results', {}).get('azure_postgresql', {})

    # Compare OLTP/OLAP tests (skip isolation tests and NOT TESTED for overall winner)
    for test_key in ['test_01', 'test_02', 'test_03', 'test_04', 'test_05', 'test_06']:
        crdb_result = test_results_crdb.get(test_key, {})
        pg_result = test_results_pg.get(test_key, {})

        crdb_status = crdb_result.get('status')
        pg_status = pg_result.get('status')

        # Skip if either database was not tested
        if crdb_status == 'NOT TESTED' or pg_status == 'NOT TESTED':
            continue

        if crdb_status == 'SUCCESS' and pg_status == 'SUCCESS':
            # Determine winner for this test
            winner = _determine_test_winner(crdb_result, pg_result)
            if winner == 'crdb':
                crdb_wins += 1
            elif winner == 'pg':
                pg_wins += 1

    # Return winner
    if crdb_wins > pg_wins:
        return "CockroachDB"
    elif pg_wins > crdb_wins:
        return "Azure PostgreSQL"
    else:
        return "Tie"


def _determine_test_winner(crdb_result: Dict[str, Any], pg_result: Dict[str, Any]) -> Optional[str]:
    """Determine winner for a single test."""
    # Check latency (lower is better)
    crdb_p50 = (crdb_result.get('percentiles') or {}).get('p50')
    pg_p50 = (pg_result.get('percentiles') or {}).get('p50')
    if crdb_p50 and pg_p50:
        return 'crdb' if crdb_p50 < pg_p50 else 'pg'

    # Check throughput (higher is better)
    crdb_tps = (crdb_result.get('throughput') or {}).get('tps')
    pg_tps = (pg_result.get('throughput') or {}).get('tps')
    if crdb_tps and pg_tps:
        return 'crdb' if crdb_tps > pg_tps else 'pg'

    # Check median time (lower is better)
    crdb_median = (crdb_result.get('custom_metrics') or {}).get('median_time_seconds')
    pg_median = (pg_result.get('custom_metrics') or {}).get('median_time_seconds')
    if crdb_median and pg_median:
        return 'crdb' if crdb_median < pg_median else 'pg'

    return None


# Test function
def test_text_summary():
    """Test text summary generation."""
    print("=" * 70)
    print("Text Summary Writer - Test")
    print("=" * 70)

    # Sample results
    sample_results = {
        'benchmark_info': {
            'start_time': '2026-04-14T10:00:00',
            'end_time': '2026-04-14T10:30:00',
            'total_duration_seconds': 1800.5,
        },
        'databases': {
            'cockroachdb': {'version': 'CockroachDB v23.2.0'},
            'azure_postgresql': {'version': 'PostgreSQL 15.5'},
        },
        'test_results': {
            'cockroachdb': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 12.5,
                    'percentiles': {'p50': 1.23, 'p95': 2.45, 'p99': 3.67},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'duration_seconds': 300.0,
                    'throughput': {'tps': 1500.0},
                },
            },
            'azure_postgresql': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 10.0,
                    'percentiles': {'p50': 0.95, 'p95': 1.80, 'p99': 2.50},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'duration_seconds': 300.0,
                    'throughput': {'tps': 1800.0},
                },
            },
        },
        'execution_summary': {
            'cockroachdb_success': 7,
            'azure_postgresql_success': 8,
        },
    }

    # Generate summary
    summary_text = generate_text_summary(sample_results)

    print("\nGenerated Summary:")
    print(summary_text)

    # Write to file
    test_output = '/tmp/test_benchmark_summary.txt'
    write_text_summary(sample_results, test_output)

    print("\n✅ Text summary generation test passed!")
    print("=" * 70)


if __name__ == '__main__':
    test_text_summary()

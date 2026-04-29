"""
HTML Dashboard Generator - Create interactive HTML dashboard with Chart.js.

Generates visual comparison dashboard with tables and charts using Jinja2 templates.
"""

from pathlib import Path
from typing import Dict, Any, List
import json

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    print("Warning: jinja2 not installed. HTML generation will not work.")
    Environment = None

from src.output.test_metadata import get_test_tooltip


def generate_html_dashboard(results: Dict[str, Any], output_path: str, template_dir: str = None) -> None:
    """
    Generate interactive HTML dashboard with Chart.js visualizations.

    Args:
        results: Results dictionary from TestRunner
        output_path: Path to output HTML file
        template_dir: Path to templates directory (auto-detected if None)

    Raises:
        ImportError: If jinja2 not available
        IOError: If template or output file cannot be accessed
    """
    if Environment is None:
        raise ImportError("jinja2 is required for HTML generation. Install with: pip install jinja2")

    print(f"\nGenerating HTML dashboard: {output_path}")

    # Auto-detect template directory
    if template_dir is None:
        template_dir = Path(__file__).parent.parent.parent / 'templates'

    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Load template
    template = env.get_template('dashboard_template.html')

    # Prepare template data
    template_data = _prepare_template_data(results)

    # Render HTML
    html_content = template.render(**template_data)

    # Write to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        file_size = output_file.stat().st_size
        print(f"✅ HTML dashboard generated successfully ({file_size:,} bytes)")
        print(f"   Open in browser: file://{output_file.absolute()}")

    except (IOError, OSError) as e:
        print(f"❌ Failed to write HTML: {e}")
        raise


def _prepare_template_data(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare data for template rendering.

    Args:
        results: Results dictionary from TestRunner

    Returns:
        Dictionary with template data
    """
    # Extract core sections
    benchmark_info = results.get('benchmark_info', {})
    databases = results.get('databases', {})
    test_results_crdb = results.get('test_results', {}).get('cockroachdb', {})
    test_results_pg = results.get('test_results', {}).get('azure_postgresql', {})
    execution_summary = results.get('execution_summary', {})

    # Build comparison table
    comparison_table = _build_comparison_table(test_results_crdb, test_results_pg)

    # Build chart data
    latency_chart_data = _build_latency_chart_data(test_results_crdb, test_results_pg)
    olap_chart_data = _build_olap_chart_data(test_results_crdb, test_results_pg)
    tps_chart_data = _build_tps_chart_data(test_results_crdb, test_results_pg)

    return {
        'benchmark_info': benchmark_info,
        'databases': databases,
        'execution_summary': execution_summary,
        'comparison_table': comparison_table,
        'latency_chart_data': latency_chart_data,
        'olap_chart_data': olap_chart_data,
        'tps_chart_data': tps_chart_data,
    }


def _build_comparison_table(crdb_results: Dict[str, Any], pg_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build comparison table rows.

    Args:
        crdb_results: CockroachDB test results
        pg_results: Azure PostgreSQL test results

    Returns:
        List of table row dictionaries
    """
    rows = []

    test_configs = [
        # Test 1: SELECT 1 - All percentiles
        ('test_01', 'Test 1: SELECT 1', 'p50 Latency', 'percentiles', 'p50', 'ms', True),
        ('test_01', 'Test 1: SELECT 1', 'p95 Latency', 'percentiles', 'p95', 'ms', True),
        ('test_01', 'Test 1: SELECT 1', 'p99 Latency', 'percentiles', 'p99', 'ms', True),
        ('test_01', 'Test 1: SELECT 1', 'p99.99 Latency', 'percentiles', 'p99_99', 'ms', True),

        # Test 2: Point Lookup - All percentiles
        ('test_02', 'Test 2: Point Lookup', 'p50 Latency', 'percentiles', 'p50', 'ms', True),
        ('test_02', 'Test 2: Point Lookup', 'p95 Latency', 'percentiles', 'p95', 'ms', True),
        ('test_02', 'Test 2: Point Lookup', 'p99 Latency', 'percentiles', 'p99', 'ms', True),
        ('test_02', 'Test 2: Point Lookup', 'p99.99 Latency', 'percentiles', 'p99_99', 'ms', True),

        # Test 3: TPC-B
        ('test_03', 'Test 3: TPC-B', 'TPS', 'custom_metrics', 'tps', 'tps', False),

        # Test 4-6: OLAP queries
        ('test_04', 'Test 4: ROLLUP', 'Median Time', 'custom_metrics', 'median_time_seconds', 's', True),
        ('test_05', 'Test 5: Window Funcs', 'Median Time', 'custom_metrics', 'median_time_seconds', 's', True),
        ('test_06', 'Test 6: JOIN', 'Median Time', 'custom_metrics', 'median_time_seconds', 's', True),

        # Test 7-10: Isolation tests
        ('test_07', 'Test 7: Phantom Read (SERIALIZABLE)', 'Status', 'custom_metrics', 'status', '', None),
        ('test_08', 'Test 8: Non-Rep Read (REPEATABLE READ)', 'Status', 'custom_metrics', 'status', '', None),
        ('test_09', 'Test 9: Phantom Read (DEFAULT)', 'Status', 'custom_metrics', 'status', '', None),
        ('test_10', 'Test 10: Non-Rep Read (DEFAULT)', 'Status', 'custom_metrics', 'status', '', None),
    ]

    for test_key, test_name, metric_name, category, metric_key, unit, lower_is_better in test_configs:
        crdb_result = crdb_results.get(test_key, {})
        pg_result = pg_results.get(test_key, {})

        # Generate tooltip for this test
        tooltip_text = get_test_tooltip(test_key, crdb_result)

        # Check for NOT TESTED status
        crdb_status = crdb_result.get('status', 'N/A')
        pg_status = pg_result.get('status', 'N/A')

        # Get metric values first (needed even if one side is NOT TESTED)
        if category == 'percentiles':
            crdb_value = crdb_result.get('percentiles', {}).get(metric_key)
            pg_value = pg_result.get('percentiles', {}).get(metric_key)
        elif category == 'throughput':
            crdb_value = crdb_result.get('throughput', {}).get(metric_key)
            pg_value = pg_result.get('throughput', {}).get(metric_key)
        elif category == 'custom_metrics':
            crdb_value = crdb_result.get('custom_metrics', {}).get(metric_key)
            pg_value = pg_result.get('custom_metrics', {}).get(metric_key)
        else:
            crdb_value = None
            pg_value = None

        # Helper function to format a value
        def format_value(value, unit):
            if value is None:
                return 'N/A'
            if unit == 'ms':
                return f"{value:.2f} ms"
            elif unit == 's':
                return f"{value:.2f} s"
            elif unit == 'tps':
                return f"{value:.0f} TPS"
            else:
                return str(value)

        # Handle NOT TESTED status (show actual values if available)
        if crdb_status == 'NOT TESTED' or pg_status == 'NOT TESTED':
            rows.append({
                'test_name': test_name,
                'metric_name': metric_name,
                'crdb_value': 'NOT TESTED' if crdb_status == 'NOT TESTED' else format_value(crdb_value, unit),
                'pg_value': 'NOT TESTED' if pg_status == 'NOT TESTED' else format_value(pg_value, unit),
                'crdb_class': 'not-tested' if crdb_status == 'NOT TESTED' else '',
                'pg_class': 'not-tested' if pg_status == 'NOT TESTED' else '',
                'winner': '-',
                'delta': '-',
                'delta_class': '',
                'tooltip': tooltip_text,
            })
            continue

        # Format row (both databases tested)
        if crdb_value is not None and pg_value is not None:
            if lower_is_better is not None:
                # Numeric comparison
                if isinstance(crdb_value, (int, float)) and isinstance(pg_value, (int, float)):
                    # Determine winner
                    if lower_is_better:
                        crdb_wins = crdb_value < pg_value
                    else:
                        crdb_wins = crdb_value > pg_value

                    # Calculate delta
                    if crdb_value > 0:
                        delta_pct = ((pg_value - crdb_value) / crdb_value) * 100
                    else:
                        delta_pct = 0

                    rows.append({
                        'test_name': test_name,
                        'metric_name': metric_name,
                        'crdb_value': format_value(crdb_value, unit),
                        'pg_value': format_value(pg_value, unit),
                        'crdb_class': 'winner' if crdb_wins else 'loser',
                        'pg_class': 'loser' if crdb_wins else 'winner',
                        'winner': 'CRDB' if crdb_wins else 'PG',
                        'delta': f"{delta_pct:+.1f}%",
                        'delta_class': 'delta-positive' if delta_pct > 0 else 'delta-negative',
                        'tooltip': tooltip_text,
                    })
                else:
                    # String comparison (isolation tests)
                    # Determine status classes for PASS, FAIL (DEFAULT SETTINGS), etc.
                    crdb_is_pass = crdb_value == 'PASS'
                    pg_is_pass = pg_value == 'PASS'

                    rows.append({
                        'test_name': test_name,
                        'metric_name': metric_name,
                        'crdb_value': str(crdb_value),
                        'pg_value': str(pg_value),
                        'crdb_class': 'status-success' if crdb_is_pass else 'status-failed',
                        'pg_class': 'status-success' if pg_is_pass else 'status-failed',
                        'winner': '-',
                        'delta': '-',
                        'delta_class': '',
                        'tooltip': tooltip_text,
                    })
            else:
                # Non-comparable (isolation tests)
                rows.append({
                    'test_name': test_name,
                    'metric_name': metric_name,
                    'crdb_value': str(crdb_value),
                    'pg_value': str(pg_value),
                    'crdb_class': '',
                    'pg_class': '',
                    'winner': '-',
                    'delta': '-',
                    'delta_class': '',
                    'tooltip': tooltip_text,
                })
        else:
            # Missing data (one or both values are None, but neither marked as NOT TESTED)
            rows.append({
                'test_name': test_name,
                'metric_name': metric_name,
                'crdb_value': format_value(crdb_value, unit),
                'pg_value': format_value(pg_value, unit),
                'crdb_class': '',
                'pg_class': '',
                'winner': '-',
                'delta': '-',
                'delta_class': '',
                'tooltip': tooltip_text,
            })

    return rows


def _build_latency_chart_data(crdb_results: Dict[str, Any], pg_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build latency chart data for Chart.js.

    Args:
        crdb_results: CockroachDB test results
        pg_results: Azure PostgreSQL test results

    Returns:
        Chart data dictionary
    """
    labels = []
    crdb_data = []
    pg_data = []

    # Tests 1-2 have latency metrics (p50, p95, p99, p99.99)
    for test_key, test_label in [
        ('test_01', 'Test 1 p50'), ('test_01', 'Test 1 p95'), ('test_01', 'Test 1 p99'), ('test_01', 'Test 1 p99.99'),
        ('test_02', 'Test 2 p50'), ('test_02', 'Test 2 p95'), ('test_02', 'Test 2 p99'), ('test_02', 'Test 2 p99.99')
    ]:
        percentile_str = test_label.split()[-1]  # Extract p50/p95/p99/p99.99
        percentile_key = percentile_str.replace('.', '_')  # p99.99 -> p99_99

        # Get statuses
        crdb_status = crdb_results.get(test_key, {}).get('status')
        pg_status = pg_results.get(test_key, {}).get('status')

        # Get values (may be None if test wasn't run or failed)
        crdb_value = crdb_results.get(test_key, {}).get('percentiles', {}).get(percentile_key)
        pg_value = pg_results.get(test_key, {}).get('percentiles', {}).get(percentile_key)

        # Include data point if at least one database has valid data
        if crdb_value is not None or pg_value is not None:
            labels.append(test_label)
            crdb_data.append(crdb_value if crdb_value is not None else 0)
            pg_data.append(pg_value if pg_value is not None else 0)

    return {
        'labels': labels,
        'crdb': crdb_data,
        'pg': pg_data,
    }


def _build_olap_chart_data(crdb_results: Dict[str, Any], pg_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build OLAP query time chart data.

    Args:
        crdb_results: CockroachDB test results
        pg_results: Azure PostgreSQL test results

    Returns:
        Chart data dictionary
    """
    labels = []
    crdb_data = []
    pg_data = []

    # Tests 4-6 are OLAP queries
    for test_key, test_label in [('test_04', 'Test 4: ROLLUP'),
                                   ('test_05', 'Test 5: Window'),
                                   ('test_06', 'Test 6: JOIN')]:
        # Get values (may be None if test wasn't run or failed)
        crdb_median = crdb_results.get(test_key, {}).get('custom_metrics', {}).get('median_time_seconds')
        pg_median = pg_results.get(test_key, {}).get('custom_metrics', {}).get('median_time_seconds')

        # Include data point if at least one database has valid data
        if crdb_median is not None or pg_median is not None:
            labels.append(test_label)
            crdb_data.append(crdb_median if crdb_median is not None else 0)
            pg_data.append(pg_median if pg_median is not None else 0)

    return {
        'labels': labels,
        'crdb': crdb_data,
        'pg': pg_data,
    }


def _build_tps_chart_data(crdb_results: Dict[str, Any], pg_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build TPS chart data.

    Args:
        crdb_results: CockroachDB test results
        pg_results: Azure PostgreSQL test results

    Returns:
        Chart data dictionary
    """
    labels = []
    crdb_data = []
    pg_data = []

    # Test 3 has TPS metric (from custom_metrics)
    test_key = 'test_03'
    crdb_tps = crdb_results.get(test_key, {}).get('custom_metrics', {}).get('tps')
    pg_tps = pg_results.get(test_key, {}).get('custom_metrics', {}).get('tps')

    if crdb_tps is not None or pg_tps is not None:
        labels.append('Test 3: TPC-B')
        crdb_data.append(crdb_tps if crdb_tps is not None else 0)
        pg_data.append(pg_tps if pg_tps is not None else 0)

    # Include QPS from tests 1-2 if available
    for test_key, test_label in [('test_01', 'Test 1: SELECT 1'), ('test_02', 'Test 2: Point Lookup')]:
        crdb_qps = crdb_results.get(test_key, {}).get('throughput', {}).get('qps')
        pg_qps = pg_results.get(test_key, {}).get('throughput', {}).get('qps')

        if crdb_qps is not None or pg_qps is not None:
            labels.append(test_label)
            crdb_data.append(crdb_qps if crdb_qps is not None else 0)
            pg_data.append(pg_qps if pg_qps is not None else 0)

    return {
        'labels': labels,
        'crdb': crdb_data,
        'pg': pg_data,
    }


# Test function
def test_html_generator():
    """Test HTML generation with sample data."""
    print("=" * 70)
    print("HTML Generator - Test")
    print("=" * 70)

    # Sample results
    sample_results = {
        'benchmark_info': {
            'start_time': '2026-04-14T10:00:00',
            'end_time': '2026-04-14T10:30:00',
            'total_duration_seconds': 1800.5,
            'test_count': 8,
        },
        'databases': {
            'cockroachdb': {
                'name': 'perftest_crdb',
                'version': 'CockroachDB v23.2.0',
                'type': 'CockroachDB Advanced',
            },
            'azure_postgresql': {
                'name': 'perftest_pg',
                'version': 'PostgreSQL 15.5',
                'type': 'Azure PostgreSQL Flexible',
            },
        },
        'test_results': {
            'cockroachdb': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 12.5,
                    'percentiles': {'p50': 1.23, 'p95': 2.45, 'p99': 3.67},
                    'throughput': {'qps': 8000},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'duration_seconds': 300.0,
                    'throughput': {'tps': 1500.0},
                },
                'test_04': {
                    'status': 'SUCCESS',
                    'custom_metrics': {'median_time_seconds': 5.2},
                },
            },
            'azure_postgresql': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 10.0,
                    'percentiles': {'p50': 0.95, 'p95': 1.80, 'p99': 2.50},
                    'throughput': {'qps': 10000},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'duration_seconds': 300.0,
                    'throughput': {'tps': 1800.0},
                },
                'test_04': {
                    'status': 'SUCCESS',
                    'custom_metrics': {'median_time_seconds': 4.8},
                },
            },
        },
        'execution_summary': {
            'total_duration_seconds': 1800.5,
            'cockroachdb_success': 7,
            'azure_postgresql_success': 8,
        },
    }

    # Generate HTML
    test_output = '/tmp/test_benchmark_dashboard.html'
    try:
        generate_html_dashboard(sample_results, test_output)
        print(f"\n✅ HTML dashboard generation test passed!")
        print(f"   Open {test_output} in your browser to view")
    except Exception as e:
        print(f"\n❌ HTML generation failed: {e}")
        raise

    print("=" * 70)


if __name__ == '__main__':
    test_html_generator()

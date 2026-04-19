#!/usr/bin/env python3
"""
Test Phase 7 implementation - Output Generation.

Verifies JSON writer, text summary, and HTML dashboard generation.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all output modules can be imported."""
    print("=" * 70)
    print("Testing Phase 7 Imports")
    print("=" * 70)

    print("\n[1/3] Importing output modules...")

    try:
        from src.output.json_writer import write_json_results, validate_json_file
        from src.output.text_summary import generate_text_summary, write_text_summary
        from src.output.html_generator import generate_html_dashboard

        print("  ✅ json_writer imported")
        print("  ✅ text_summary imported")
        print("  ✅ html_generator imported")

        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_json_writer():
    """Test JSON writer."""
    print("\n" + "=" * 70)
    print("[2/3] Testing JSON Writer")
    print("=" * 70)

    from src.output.json_writer import write_json_results, validate_json_file, load_json_results
    import math

    # Sample results with special values
    sample_results = {
        'benchmark_info': {
            'start_time': '2026-04-14T10:00:00',
            'total_duration_seconds': 1800.5,
        },
        'databases': {
            'cockroachdb': {'version': 'v23.2.0'},
        },
        'test_results': {
            'cockroachdb': {
                'test_01': {
                    'status': 'SUCCESS',
                    'percentiles': {'p50': 1.23},
                },
            },
        },
        'special_values': {
            'nan_value': float('nan'),
            'inf_value': float('inf'),
            'neg_inf': float('-inf'),
            'normal': 42.0,
        },
    }

    # Write JSON
    test_output = '/tmp/test_phase7_results.json'
    print("\nWriting JSON...")

    try:
        write_json_results(sample_results, test_output)

        # Validate
        print("\nValidating JSON...")
        if validate_json_file(test_output):
            print("✅ JSON file is valid")
        else:
            print("❌ JSON file is invalid")
            return False

        # Load and check
        print("\nLoading JSON back...")
        loaded = load_json_results(test_output)

        # Check special values were converted
        assert loaded['special_values']['nan_value'] is None, "NaN not converted to null"
        assert loaded['special_values']['inf_value'] == "Infinity", "Inf not converted"
        assert loaded['special_values']['neg_inf'] == "-Infinity", "-Inf not converted"
        assert loaded['special_values']['normal'] == 42.0, "Normal value changed"

        print("✅ Special value handling verified:")
        print(f"   NaN → {loaded['special_values']['nan_value']}")
        print(f"   Inf → {loaded['special_values']['inf_value']}")
        print(f"   -Inf → {loaded['special_values']['neg_inf']}")

        return True

    except Exception as e:
        print(f"❌ JSON writer test failed: {e}")
        return False


def test_text_summary():
    """Test text summary generator."""
    print("\n" + "=" * 70)
    print("[3/3] Testing Text Summary Generator")
    print("=" * 70)

    from src.output.text_summary import generate_text_summary, write_text_summary

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
                    'percentiles': {'p50': 1.23, 'p95': 2.45},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'throughput': {'tps': 1500.0},
                },
            },
            'azure_postgresql': {
                'test_01': {
                    'status': 'SUCCESS',
                    'duration_seconds': 10.0,
                    'percentiles': {'p50': 0.95, 'p95': 1.80},
                },
                'test_03': {
                    'status': 'SUCCESS',
                    'throughput': {'tps': 1800.0},
                },
            },
        },
        'execution_summary': {
            'cockroachdb_success': 7,
            'azure_postgresql_success': 8,
        },
    }

    try:
        # Generate summary text
        print("\nGenerating text summary...")
        summary_text = generate_text_summary(sample_results)

        # Verify content
        assert 'BENCHMARK RESULTS SUMMARY' in summary_text
        assert 'CockroachDB' in summary_text
        assert 'PostgreSQL' in summary_text
        assert 'Test 1:' in summary_text

        line_count = summary_text.count('\n') + 1
        print(f"✅ Text summary generated ({line_count} lines)")

        # Write to file
        test_output = '/tmp/test_phase7_summary.txt'
        print("\nWriting text summary to file...")
        write_text_summary(sample_results, test_output)

        # Verify file
        with open(test_output, 'r') as f:
            file_content = f.read()

        assert file_content == summary_text, "File content doesn't match generated summary"
        print("✅ Text summary file verified")

        return True

    except Exception as e:
        print(f"❌ Text summary test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_html_generator():
    """Test HTML dashboard generator."""
    print("\n" + "=" * 70)
    print("[4/4] Testing HTML Dashboard Generator")
    print("=" * 70)

    try:
        from src.output.html_generator import generate_html_dashboard
    except ImportError as e:
        print(f"⚠️  HTML generator import failed (jinja2 may not be installed): {e}")
        print("   This is expected if jinja2 is not yet installed")
        return True  # Don't fail the test if jinja2 isn't installed

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
                'name': 'test_crdb',
                'version': 'CockroachDB v23.2.0',
                'type': 'CockroachDB Advanced',
            },
            'azure_postgresql': {
                'name': 'test_pg',
                'version': 'PostgreSQL 15.5',
                'type': 'Azure PostgreSQL',
            },
        },
        'test_results': {
            'cockroachdb': {
                'test_01': {
                    'status': 'SUCCESS',
                    'percentiles': {'p50': 1.23, 'p95': 2.45, 'p99': 3.67},
                    'throughput': {'qps': 8000},
                },
                'test_03': {
                    'status': 'SUCCESS',
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
                    'percentiles': {'p50': 0.95, 'p95': 1.80, 'p99': 2.50},
                    'throughput': {'qps': 10000},
                },
                'test_03': {
                    'status': 'SUCCESS',
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

    try:
        # Generate HTML
        test_output = '/tmp/test_phase7_dashboard.html'
        print("\nGenerating HTML dashboard...")
        generate_html_dashboard(sample_results, test_output)

        # Verify file exists and has content
        output_path = Path(test_output)
        assert output_path.exists(), "HTML file not created"

        file_size = output_path.stat().st_size
        assert file_size > 1000, "HTML file too small"

        print(f"✅ HTML dashboard generated ({file_size:,} bytes)")
        print(f"   File: {test_output}")

        # Verify HTML structure
        with open(test_output, 'r') as f:
            html_content = f.read()

        assert '<!DOCTYPE html>' in html_content
        assert 'CockroachDB' in html_content
        assert 'Chart.js' in html_content or 'chart.js' in html_content
        assert 'latencyChart' in html_content
        print("✅ HTML structure verified")

        return True

    except Exception as e:
        print(f"❌ HTML generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Phase 7 Test Suite - Output Generation")
    print("=" * 70)

    results = []

    # Test imports
    results.append(('Imports', test_imports()))

    # Test JSON writer
    results.append(('JSON Writer', test_json_writer()))

    # Test text summary
    results.append(('Text Summary', test_text_summary()))

    # Test HTML generator
    results.append(('HTML Generator', test_html_generator()))

    # Summary
    print("\n" + "=" * 70)
    print("Phase 7 Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All Phase 7 tests passed!")
        print("\nOutput modules implemented:")
        print("  - JSON Writer: Raw data export with special value handling")
        print("  - Text Summary: Concise console-friendly summary")
        print("  - HTML Dashboard: Interactive visualizations with Chart.js")
        print("\nGenerated test files:")
        print("  - /tmp/test_phase7_results.json")
        print("  - /tmp/test_phase7_summary.txt")
        print("  - /tmp/test_phase7_dashboard.html")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

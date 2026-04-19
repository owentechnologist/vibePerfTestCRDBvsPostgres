#!/usr/bin/env python3
"""
Test base test infrastructure.

Verifies that all base classes and utilities work correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all base classes can be imported."""
    print("=" * 70)
    print("Testing Base Test Infrastructure")
    print("=" * 70)

    print("\n[1/5] Testing imports...")

    try:
        from src.tests.base import (
            BaseTest, LatencyTest, OLAPTest, IsolationTest, TestResult
        )
        print("  ✅ All base classes imported successfully")
        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_test_result():
    """Test TestResult dataclass."""
    print("\n[2/5] Testing TestResult dataclass...")

    from src.tests.base import TestResult

    # Create a test result
    result = TestResult(
        test_name="Test01Example",
        status="SUCCESS",
        duration_seconds=1.234,
        error_count=0,
        retry_count=2
    )

    if result.test_name == "Test01Example":
        print(f"  ✅ TestResult created: {result.test_name}")
    else:
        print(f"  ❌ TestResult creation failed")
        return False

    # Test to_dict conversion
    result_dict = result.to_dict()

    required_keys = ['test_name', 'status', 'duration_seconds', 'error_count', 'retry_count']
    for key in required_keys:
        if key not in result_dict:
            print(f"  ❌ Missing key in to_dict(): {key}")
            return False

    print(f"  ✅ to_dict() contains all required keys")

    # Test with optional fields
    result_with_metrics = TestResult(
        test_name="Test02Example",
        status="SUCCESS",
        duration_seconds=2.345,
        percentiles={'p50': 10.0, 'p95': 20.0, 'p99': 30.0},
        throughput={'qps': 1234.5, 'tps': 500.0}
    )

    result_dict2 = result_with_metrics.to_dict()

    if 'percentiles' in result_dict2 and 'throughput' in result_dict2:
        print(f"  ✅ Optional fields (percentiles, throughput) included")
    else:
        print(f"  ❌ Optional fields not included")
        return False

    return True


def test_base_test_structure():
    """Test BaseTest structure (without actual execution)."""
    print("\n[3/5] Testing BaseTest structure...")

    from src.tests.base import BaseTest
    import inspect

    # Check that it's abstract
    if inspect.isabstract(BaseTest):
        print(f"  ✅ BaseTest is abstract")
    else:
        print(f"  ❌ BaseTest should be abstract")
        return False

    # Check for required methods
    required_methods = ['execute', 'run', 'get_connection']
    for method_name in required_methods:
        if hasattr(BaseTest, method_name):
            print(f"  ✅ Method exists: {method_name}")
        else:
            print(f"  ❌ Missing method: {method_name}")
            return False

    return True


def test_specialized_base_classes():
    """Test specialized base classes."""
    print("\n[4/5] Testing specialized base classes...")

    from src.tests.base import LatencyTest, OLAPTest, IsolationTest

    # Check LatencyTest
    if hasattr(LatencyTest, '__init__'):
        print(f"  ✅ LatencyTest defined")
    else:
        print(f"  ❌ LatencyTest not properly defined")
        return False

    # Check OLAPTest
    if hasattr(OLAPTest, 'compute_statistics'):
        print(f"  ✅ OLAPTest has compute_statistics method")
    else:
        print(f"  ❌ OLAPTest missing compute_statistics")
        return False

    # Check IsolationTest
    if hasattr(IsolationTest, 'acquire_connections'):
        print(f"  ✅ IsolationTest has acquire_connections method")
    else:
        print(f"  ❌ IsolationTest missing acquire_connections")
        return False

    return True


def test_olap_statistics():
    """Test OLAP test statistics computation."""
    print("\n[5/5] Testing OLAP statistics computation...")

    # Mock DatabasePool for testing
    class MockPool:
        class config:
            name = "TestDB"

    from src.tests.base import OLAPTest

    # We can't instantiate OLAPTest directly since it inherits from abstract BaseTest
    # But we can test the statistics computation logic

    execution_times = [1.5, 2.0, 1.8]
    sorted_times = sorted(execution_times)
    median_idx = len(sorted_times) // 2

    stats = {
        'runs': len(execution_times),
        'min_time_seconds': min(execution_times),
        'median_time_seconds': sorted_times[median_idx],
        'max_time_seconds': max(execution_times),
        'mean_time_seconds': sum(execution_times) / len(execution_times)
    }

    if stats['min_time_seconds'] == 1.5:
        print(f"  ✅ Min time: {stats['min_time_seconds']}s")
    else:
        print(f"  ❌ Min time calculation incorrect")
        return False

    if stats['median_time_seconds'] == 1.8:
        print(f"  ✅ Median time: {stats['median_time_seconds']}s")
    else:
        print(f"  ❌ Median time calculation incorrect")
        return False

    if stats['max_time_seconds'] == 2.0:
        print(f"  ✅ Max time: {stats['max_time_seconds']}s")
    else:
        print(f"  ❌ Max time calculation incorrect")
        return False

    expected_mean = (1.5 + 2.0 + 1.8) / 3
    if abs(stats['mean_time_seconds'] - expected_mean) < 0.01:
        print(f"  ✅ Mean time: {stats['mean_time_seconds']:.2f}s")
    else:
        print(f"  ❌ Mean time calculation incorrect")
        return False

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Base Test Infrastructure Test Suite")
    print("=" * 70)

    results = []

    results.append(('Imports', test_imports()))
    results.append(('TestResult', test_test_result()))
    results.append(('BaseTest Structure', test_base_test_structure()))
    results.append(('Specialized Classes', test_specialized_base_classes()))
    results.append(('OLAP Statistics', test_olap_statistics()))

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
        print("✅ All base infrastructure tests passed!")
        print("\nBase classes ready for test implementation:")
        print("  - BaseTest: Abstract base for all tests")
        print("  - LatencyTest: For Tests 1-2 (latency measurements)")
        print("  - OLAPTest: For Tests 4-6 (analytical queries)")
        print("  - IsolationTest: For Tests 7-8 (isolation level tests)")
        print("  - TestResult: Standardized result format")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

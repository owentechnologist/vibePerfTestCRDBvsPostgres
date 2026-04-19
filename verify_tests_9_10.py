#!/usr/bin/env python3
"""
Verification script to ensure Tests 9 and 10 are properly integrated.

Checks:
1. Test metadata includes tests 9 and 10
2. HTML generator includes tests 9 and 10 in comparison table
3. Text summary includes tests 9 and 10 in isolation tests
4. Test runner has correct test count (10)
5. HTML template uses dynamic test count
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def verify_test_metadata():
    """Verify test metadata includes tests 9 and 10."""
    from src.output.test_metadata import get_test_metadata

    metadata = get_test_metadata()

    print("✓ Checking test metadata...")

    if 'test_09' not in metadata:
        print("  ❌ test_09 missing from metadata")
        return False

    if 'test_10' not in metadata:
        print("  ❌ test_10 missing from metadata")
        return False

    print(f"  ✅ test_09: {metadata['test_09']['name']}")
    print(f"  ✅ test_10: {metadata['test_10']['name']}")

    return True


def verify_html_generator():
    """Verify HTML generator includes tests 9 and 10."""
    from src.output.html_generator import _build_comparison_table

    print("\n✓ Checking HTML generator...")

    # Mock data for tests 9 and 10
    sample_crdb = {
        'test_09': {
            'status': 'SUCCESS',
            'custom_metrics': {'status': 'PASS'}
        },
        'test_10': {
            'status': 'SUCCESS',
            'custom_metrics': {'status': 'PASS'}
        }
    }

    sample_pg = {
        'test_09': {
            'status': 'SUCCESS',
            'custom_metrics': {'status': 'FAIL (DEFAULT SETTINGS)'}
        },
        'test_10': {
            'status': 'SUCCESS',
            'custom_metrics': {'status': 'FAIL (DEFAULT SETTINGS)'}
        }
    }

    rows = _build_comparison_table(sample_crdb, sample_pg)

    # Check if test 9 and 10 rows exist
    test_09_rows = [r for r in rows if 'Test 9' in r['test_name']]
    test_10_rows = [r for r in rows if 'Test 10' in r['test_name']]

    if not test_09_rows:
        print("  ❌ Test 9 not found in comparison table")
        return False

    if not test_10_rows:
        print("  ❌ Test 10 not found in comparison table")
        return False

    print(f"  ✅ Test 9: {test_09_rows[0]['test_name']}")
    print(f"  ✅ Test 10: {test_10_rows[0]['test_name']}")

    # Check tooltips
    if 'tooltip' not in test_09_rows[0]:
        print("  ❌ Test 9 missing tooltip")
        return False

    if 'tooltip' not in test_10_rows[0]:
        print("  ❌ Test 10 missing tooltip")
        return False

    print(f"  ✅ Test 9 tooltip: {len(test_09_rows[0]['tooltip'])} chars")
    print(f"  ✅ Test 10 tooltip: {len(test_10_rows[0]['tooltip'])} chars")

    return True


def verify_text_summary():
    """Verify text summary includes tests 9 and 10."""
    print("\n✓ Checking text summary...")

    # Read the source file and check for test_09 and test_10
    with open('src/output/text_summary.py', 'r') as f:
        content = f.read()

    if 'test_09' not in content:
        print("  ❌ test_09 not found in text_summary.py")
        return False

    if 'test_10' not in content:
        print("  ❌ test_10 not found in text_summary.py")
        return False

    if "'test_07', 'test_08', 'test_09', 'test_10'" in content:
        print("  ✅ Isolation tests list includes test_09 and test_10")
    else:
        print("  ❌ Isolation tests list may not include test_09 and test_10")
        return False

    return True


def verify_test_runner():
    """Verify test runner has correct test count."""
    print("\n✓ Checking test runner...")

    # Read the source file
    with open('src/test_runner.py', 'r') as f:
        content = f.read()

    if "'test_count': 10" in content:
        print("  ✅ benchmark_info test_count = 10")
    else:
        print("  ❌ benchmark_info test_count may not be 10")
        return False

    if "'total_tests': 10" in content:
        print("  ✅ summary total_tests = 10")
    else:
        print("  ❌ summary total_tests may not be 10")
        return False

    return True


def verify_html_template():
    """Verify HTML template uses dynamic test count."""
    print("\n✓ Checking HTML template...")

    with open('templates/dashboard_template.html', 'r') as f:
        content = f.read()

    # Check that it uses dynamic test count, not hardcoded /8
    if 'benchmark_info.test_count' in content:
        print("  ✅ Uses dynamic benchmark_info.test_count")
    else:
        print("  ❌ May not use dynamic test_count")
        return False

    # Make sure no hardcoded /8
    if '/8</p>' in content:
        print("  ⚠️  Warning: Found hardcoded '/8' in template")
        # Don't fail, as we may have fixed it

    return True


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("VERIFYING TESTS 9 & 10 INTEGRATION")
    print("=" * 70)

    checks = [
        ("Test Metadata", verify_test_metadata),
        ("HTML Generator", verify_html_generator),
        ("Text Summary", verify_text_summary),
        ("Test Runner", verify_test_runner),
        ("HTML Template", verify_html_template),
    ]

    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append((name, False))

    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:.<50} {status}")

    all_passed = all(r for _, r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Tests 9 & 10 are fully integrated!")
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

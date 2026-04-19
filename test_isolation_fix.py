#!/usr/bin/env python3
"""
Quick validation script to test the isolation test fixes.

Runs Tests 7 and 8 with the multiple_active_portals_enabled fix.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database import DatabasePool
from src.config import DatabaseConfig
from src.tests.test_07_phantom_read import Test07PhantomRead
from src.tests.test_08_nonrepeatable_read import Test08NonRepeatableRead


async def main():
    print("=" * 70)
    print("ISOLATION TESTS FIX VALIDATION")
    print("=" * 70)

    # Read connection string
    conn_file = Path('crdb_connection.txt')
    if not conn_file.exists():
        print("❌ crdb_connection.txt not found")
        return 1

    connection_string = conn_file.read_text().strip()
    print(f"\n✅ Using connection from crdb_connection.txt")

    # Create database pool
    config = DatabaseConfig(
        connection_string=connection_string,
        database_type='cockroachdb',
        name='CockroachDB',
    )

    pool = DatabasePool(config)
    await pool.create_pool(min_size=2, max_size=5)

    version = await pool.get_version()
    print(f"✅ Connected to: {version}")

    try:
        # Test 7: Phantom Read
        print("\n" + "=" * 70)
        print("TEST 7: PHANTOM READ ISOLATION")
        print("=" * 70)

        test7 = Test07PhantomRead(pool, timeout_seconds=60)
        result7 = await test7.run()

        print(f"\n✅ Test 7 Status: {result7.status}")
        print(f"   Duration: {result7.duration_seconds:.2f}s")
        print(f"   Errors: {result7.error_count}")

        if result7.custom_metrics:
            print(f"   Isolation Status: {result7.custom_metrics.get('status', 'N/A')}")
            print(f"   Behavior: {result7.custom_metrics.get('behavior', 'N/A')}")
            if result7.custom_metrics.get('error_message'):
                print(f"   Error: {result7.custom_metrics['error_type']}")

        # Test 8: Non-Repeatable Read
        print("\n" + "=" * 70)
        print("TEST 8: NON-REPEATABLE READ ISOLATION")
        print("=" * 70)

        test8 = Test08NonRepeatableRead(pool, timeout_seconds=60)
        result8 = await test8.run()

        print(f"\n✅ Test 8 Status: {result8.status}")
        print(f"   Duration: {result8.duration_seconds:.2f}s")
        print(f"   Errors: {result8.error_count}")

        if result8.custom_metrics:
            print(f"   Isolation Status: {result8.custom_metrics.get('status', 'N/A')}")
            print(f"   Behavior: {result8.custom_metrics.get('behavior', 'N/A')}")
            if result8.custom_metrics.get('error_message'):
                print(f"   Error: {result8.custom_metrics['error_type']}")

        # Summary
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        test7_ok = result7.status == 'SUCCESS' and result7.custom_metrics.get('status') in ['PASS', 'ERROR'] and 'FeatureNotSupportedError' not in str(result7.custom_metrics.get('error_type', ''))
        test8_ok = result8.status == 'SUCCESS' and result8.custom_metrics.get('status') in ['PASS', 'ERROR'] and 'FeatureNotSupportedError' not in str(result8.custom_metrics.get('error_type', ''))

        if test7_ok and test8_ok:
            print("\n✅ ALL TESTS PASSED - Fix is working!")
            print("   Both tests completed without FeatureNotSupportedError")
            exit_code = 0
        else:
            print("\n⚠️  TESTS HAD ISSUES")
            if not test7_ok:
                print(f"   Test 7: {result7.custom_metrics.get('error_type', 'Unknown issue')}")
            if not test8_ok:
                print(f"   Test 8: {result8.custom_metrics.get('error_type', 'Unknown issue')}")
            exit_code = 1

    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1

    finally:
        await pool.close_pool()
        print("\n✅ Connection closed")

    print("=" * 70)
    return exit_code


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

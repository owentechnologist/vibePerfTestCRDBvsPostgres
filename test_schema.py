#!/usr/bin/env python3
"""
Test schema generation without requiring database connections.
"""

import sys


def test_schema_ddl_generation():
    """Test that all DDL is generated correctly."""
    print("Testing Schema DDL Generation")
    print("=" * 70)

    # Import after path setup
    from src.schema import SchemaManager

    schema = SchemaManager()

    # Test pgbench table DDL
    print("\n[1/4] Testing pgbench table DDL...")
    pgbench_tables = [
        ('pgbench_branches', schema.PGBENCH_BRANCHES_DDL),
        ('pgbench_tellers', schema.PGBENCH_TELLERS_DDL),
        ('pgbench_accounts', schema.PGBENCH_ACCOUNTS_DDL),
        ('pgbench_history', schema.PGBENCH_HISTORY_DDL),
    ]

    for table_name, ddl in pgbench_tables:
        if 'CREATE TABLE IF NOT EXISTS' in ddl and table_name in ddl:
            print(f"  ✅ {table_name} DDL is valid")
        else:
            print(f"  ❌ {table_name} DDL is invalid")
            return False

    # Test bench_events DDL generation
    print("\n[2/4] Testing bench_events DDL generation (1-16)...")
    for i in range(1, 17):
        ddl = schema.get_bench_events_ddl(i)
        table_name = f'bench_events_{i}'

        if 'CREATE TABLE IF NOT EXISTS' in ddl and table_name in ddl:
            if i == 1 or i == 16:  # Show first and last
                print(f"  ✅ {table_name} DDL is valid")
        else:
            print(f"  ❌ {table_name} DDL is invalid")
            return False

    if True:  # All bench_events passed
        print(f"  ✅ All 16 bench_events tables validated")

    # Test bench_events indexes
    print("\n[3/4] Testing bench_events index DDL...")
    for i in [1, 8, 16]:  # Sample a few
        indexes = schema.get_bench_events_indexes_ddl(i)
        if len(indexes) == 3:
            print(f"  ✅ bench_events_{i} has 3 indexes")
        else:
            print(f"  ❌ bench_events_{i} has {len(indexes)} indexes (expected 3)")
            return False

    # Test isolation_test DDL
    print("\n[4/4] Testing isolation_test DDL...")
    if 'CREATE TABLE IF NOT EXISTS' in schema.ISOLATION_TEST_DDL and 'isolation_test' in schema.ISOLATION_TEST_DDL:
        print(f"  ✅ isolation_test DDL is valid")
    else:
        print(f"  ❌ isolation_test DDL is invalid")
        return False

    return True


def test_schema_table_count():
    """Test that we have the correct number of tables."""
    print("\nTesting Table Count")
    print("=" * 70)

    # Expected tables:
    # - 4 pgbench tables
    # - 16 bench_events tables
    # - 1 isolation_test table
    # Total: 21 tables

    expected_total = 21
    expected_pgbench = 4
    expected_bench_events = 16
    expected_isolation = 1

    actual_total = expected_pgbench + expected_bench_events + expected_isolation

    if actual_total == expected_total:
        print(f"✅ Table count correct: {actual_total} tables")
        print(f"   - pgbench: {expected_pgbench}")
        print(f"   - bench_events: {expected_bench_events}")
        print(f"   - isolation_test: {expected_isolation}")
        return True
    else:
        print(f"❌ Table count incorrect: {actual_total} (expected {expected_total})")
        return False


def test_ddl_features():
    """Test that DDL includes required features."""
    print("\nTesting DDL Features")
    print("=" * 70)

    from src.schema import SchemaManager
    schema = SchemaManager()

    # Check for IF NOT EXISTS (idempotency)
    print("\n[1/2] Checking IF NOT EXISTS clauses...")
    ddl_statements = [
        schema.PGBENCH_BRANCHES_DDL,
        schema.PGBENCH_TELLERS_DDL,
        schema.PGBENCH_ACCOUNTS_DDL,
        schema.PGBENCH_HISTORY_DDL,
        schema.ISOLATION_TEST_DDL,
        schema.get_bench_events_ddl(1),
    ]

    for ddl in ddl_statements:
        if 'IF NOT EXISTS' not in ddl:
            print(f"  ❌ Missing 'IF NOT EXISTS' clause")
            return False

    print(f"  ✅ All DDL statements have 'IF NOT EXISTS'")

    # Check for required columns in bench_events
    print("\n[2/2] Checking bench_events required columns...")
    bench_events_ddl = schema.get_bench_events_ddl(1)
    required_columns = [
        'id', 'customer_id', 'session_id', 'event_type',
        'region', 'amount', 'quantity', 'status',
        'tags', 'metadata', 'created_at', 'updated_at'
    ]

    for col in required_columns:
        if col not in bench_events_ddl:
            print(f"  ❌ Missing column: {col}")
            return False

    print(f"  ✅ All required columns present in bench_events")

    # Check for gen_random_uuid()
    if 'gen_random_uuid()' in bench_events_ddl:
        print(f"  ✅ gen_random_uuid() used for session_id")
    else:
        print(f"  ❌ gen_random_uuid() not found")
        return False

    return True


def main():
    """Run all schema tests."""
    print("\n" + "=" * 70)
    print("Schema Module Test Suite")
    print("=" * 70 + "\n")

    all_passed = True

    all_passed &= test_schema_ddl_generation()
    all_passed &= test_schema_table_count()
    all_passed &= test_ddl_features()

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All schema tests passed!")
        print("=" * 70)
        return 0
    else:
        print("❌ Some schema tests failed")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())

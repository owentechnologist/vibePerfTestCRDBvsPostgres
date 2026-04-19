#!/usr/bin/env python3
"""
Test configuration validation without requiring database connections.
"""

import sys
from src.config import DatabaseConfig

def test_connection_string_validation():
    """Test connection string validation logic."""
    print("Testing Connection String Validation")
    print("=" * 60)

    test_cases = [
        # Valid cases
        ("postgresql://user:pass@localhost:26257/db", True, "Valid CockroachDB local"),
        ("postgresql://user:pass@host.com:5432/db?sslmode=require", True, "Valid with SSL"),
        ("postgres://user:pass@host:5432/mydb", True, "Valid with postgres:// scheme"),

        # Invalid cases
        ("mysql://user:pass@host:3306/db", False, "Wrong scheme (mysql)"),
        ("postgresql://host:5432", False, "Missing database name"),
        ("user:pass@host:5432/db", False, "Missing scheme"),
        ("", False, "Empty string"),
    ]

    passed = 0
    failed = 0

    for conn_str, should_pass, description in test_cases:
        result = DatabaseConfig.is_valid_connection_string(conn_str)
        status = "✅ PASS" if result == should_pass else "❌ FAIL"

        if result == should_pass:
            passed += 1
        else:
            failed += 1

        print(f"{status} - {description}")
        if result != should_pass:
            print(f"       Expected: {should_pass}, Got: {result}")
            print(f"       Connection: {conn_str[:50]}...")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_database_config_creation():
    """Test DatabaseConfig creation and methods."""
    print("\nTesting DatabaseConfig Creation")
    print("=" * 60)

    conn_str = "postgresql://perftest_user:secret@crdb-host.cloud:26257/perftest?sslmode=require"

    try:
        config = DatabaseConfig.from_connection_string(
            conn_str,
            'cockroachdb',
            'Test CockroachDB'
        )

        print(f"✅ Config created: {config.name}")
        print(f"   Host: {config.get_host()}")
        print(f"   Port: {config.get_port()}")
        print(f"   Database: {config.get_database()}")
        print(f"   User: {config.get_user()}")
        print(f"   Type: {config.database_type}")

        # Test invalid config
        try:
            bad_config = DatabaseConfig(
                connection_string="invalid",
                database_type="cockroachdb",
                name="Bad Config"
            )
            print("❌ FAIL - Should have rejected invalid connection string")
            return False
        except ValueError as e:
            print(f"✅ Correctly rejected invalid config: {e}")

        return True

    except Exception as e:
        print(f"❌ FAIL - {e}")
        return False


def test_pool_config():
    """Test pool configuration helper."""
    print("\nTesting Pool Configuration Helper")
    print("=" * 60)

    from src.config import get_default_pool_config

    test_cases = [
        ('test_1', 1, 2),
        ('test_2', 8, 8),
        ('test_3', 16, 16),
        ('test_7', 2, 2),
        ('unknown_test', 1, 10),  # Should return default
    ]

    for test_name, expected_min, expected_max in test_cases:
        config = get_default_pool_config(test_name)
        min_size = config['min_size']
        max_size = config['max_size']

        if min_size == expected_min and max_size == expected_max:
            print(f"✅ {test_name}: {min_size}-{max_size}")
        else:
            print(f"❌ {test_name}: Expected {expected_min}-{expected_max}, Got {min_size}-{max_size}")
            return False

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Configuration Module Test Suite")
    print("=" * 60 + "\n")

    all_passed = True

    all_passed &= test_connection_string_validation()
    all_passed &= test_database_config_creation()
    all_passed &= test_pool_config()

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())

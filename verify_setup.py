#!/usr/bin/env python3
"""
Verify that the environment is set up correctly.

Run this after setup.sh to ensure all dependencies are installed
and modules can be imported.
"""

import sys


def check_python_version():
    """Verify Python version is 3.10+."""
    print("\n" + "=" * 70)
    print("Checking Python Version")
    print("=" * 70)

    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    print(f"Python version: {version_str}")

    if version_info.major < 3 or (version_info.major == 3 and version_info.minor < 10):
        print("❌ Python 3.10 or higher is required")
        return False

    print(f"✅ Python version is compatible")
    return True


def check_dependencies():
    """Verify all required packages are installed."""
    print("\n" + "=" * 70)
    print("Checking Dependencies")
    print("=" * 70)

    packages = [
        ('asyncpg', 'asyncpg'),
        ('numpy', 'numpy'),
        ('rich', 'rich'),
        ('jinja2', 'jinja2'),
        ('psutil', 'psutil'),
        ('yaml', 'pyyaml'),
    ]

    all_ok = True

    for import_name, display_name in packages:
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            print(f"  ✅ {display_name:15} version {version}")
        except ImportError as e:
            print(f"  ❌ {display_name:15} NOT INSTALLED ({e})")
            all_ok = False

    return all_ok


def check_modules():
    """Verify custom modules can be imported."""
    print("\n" + "=" * 70)
    print("Checking Custom Modules")
    print("=" * 70)

    modules = [
        ('src.config', 'Configuration module'),
        ('src.database', 'Database pool module'),
        ('src.schema', 'Schema management module'),
        ('src.data_loader', 'Data loader module'),
    ]

    all_ok = True

    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name:25} {description}")
        except ImportError as e:
            print(f"  ❌ {module_name:25} FAILED: {e}")
            all_ok = False

    return all_ok


def check_classes():
    """Verify key classes can be instantiated."""
    print("\n" + "=" * 70)
    print("Checking Class Instantiation")
    print("=" * 70)

    all_ok = True

    # Test DatabaseConfig
    try:
        from src.config import DatabaseConfig

        config = DatabaseConfig(
            connection_string="postgresql://user:pass@host:5432/db",
            database_type="postgresql",
            name="Test DB"
        )
        print(f"  ✅ DatabaseConfig instantiated")
    except Exception as e:
        print(f"  ❌ DatabaseConfig failed: {e}")
        all_ok = False

    # Test SchemaManager
    try:
        from src.schema import SchemaManager
        schema = SchemaManager()
        ddl = schema.get_bench_events_ddl(1)
        if 'bench_events_1' in ddl:
            print(f"  ✅ SchemaManager instantiated and DDL generation works")
        else:
            print(f"  ❌ SchemaManager DDL generation failed")
            all_ok = False
    except Exception as e:
        print(f"  ❌ SchemaManager failed: {e}")
        all_ok = False

    # Test pool config helper
    try:
        from src.config import get_default_pool_config
        config = get_default_pool_config('test_3')
        if config['min_size'] == 16 and config['max_size'] == 16:
            print(f"  ✅ Pool configuration helper works")
        else:
            print(f"  ❌ Pool configuration returned unexpected values")
            all_ok = False
    except Exception as e:
        print(f"  ❌ Pool configuration failed: {e}")
        all_ok = False

    return all_ok


def check_file_structure():
    """Verify expected files and directories exist."""
    print("\n" + "=" * 70)
    print("Checking File Structure")
    print("=" * 70)

    from pathlib import Path

    expected_files = [
        'requirements.txt',
        'cluster_config.yaml',
        'deploy_crdb.py',
        'setup.sh',
        '.gitignore',
        'DEPLOYMENT.md',
        'src/__init__.py',
        'src/config.py',
        'src/database.py',
        'src/schema.py',
        'src/data_loader.py',
    ]

    all_ok = True

    for file_path in expected_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} NOT FOUND")
            all_ok = False

    return all_ok


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("Environment Verification Suite")
    print("=" * 70)

    results = []

    results.append(('Python Version', check_python_version()))
    results.append(('Dependencies', check_dependencies()))
    results.append(('Custom Modules', check_modules()))
    results.append(('Class Instantiation', check_classes()))
    results.append(('File Structure', check_file_structure()))

    # Summary
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)

    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {check_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All verification checks passed!")
        print("\nYou're ready to:")
        print("  1. Deploy CockroachDB: python deploy_crdb.py --config cluster_config.yaml")
        print("  2. Run benchmark: python benchmark.py --crdb <conn> --pg <conn>")
    else:
        print("❌ Some verification checks failed")
        print("\nPlease resolve the issues above before proceeding.")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

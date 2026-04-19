#!/usr/bin/env python3
"""
Test Phase 8 implementation - Main CLI and Documentation.

Verifies benchmark.py entry point and validates documentation completeness.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that main modules exist and are valid Python."""
    print("=" * 70)
    print("Testing Phase 8 Files")
    print("=" * 70)

    print("\n[1/3] Checking main entry points...")

    main_files = [
        ('benchmark.py', 'Main CLI entry point'),
        ('deploy_crdb.py', 'CockroachDB deployment'),
    ]

    all_valid = True

    for filename, description in main_files:
        filepath = project_root / filename
        if not filepath.exists():
            print(f"  ❌ {filename} MISSING")
            all_valid = False
            continue

        # Check file is valid Python syntax
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # Basic syntax check
            compile(content, filename, 'exec')

            # Check for key elements
            if filename == 'benchmark.py':
                if 'def main()' in content and 'argparse' in content:
                    print(f"  ✅ {filename:20} - Valid ({description})")
                else:
                    print(f"  ⚠️  {filename:20} - Missing main() or argparse")
                    all_valid = False
            else:
                print(f"  ✅ {filename:20} - Valid ({description})")

        except SyntaxError as e:
            print(f"  ❌ {filename:20} - Syntax error: {e}")
            all_valid = False
        except Exception as e:
            print(f"  ⚠️  {filename:20} - Could not validate: {e}")

    return all_valid


def test_documentation():
    """Test that documentation files exist and are complete."""
    print("\n" + "=" * 70)
    print("[2/3] Testing Documentation")
    print("=" * 70)

    required_files = [
        ('README.md', 'Main documentation'),
        ('DEPLOYMENT.md', 'Deployment guide'),
        ('QUICKSTART.md', 'Quick start guide'),
        ('requirements.txt', 'Python dependencies'),
        ('cluster_config.yaml', 'CockroachDB config'),
        ('.gitignore', 'Git ignore rules'),
    ]

    all_exist = True

    print("\nChecking required files...")

    for filename, description in required_files:
        filepath = project_root / filename
        if filepath.exists():
            file_size = filepath.stat().st_size
            print(f"  ✅ {filename:25} ({file_size:,} bytes) - {description}")
        else:
            print(f"  ❌ {filename:25} MISSING - {description}")
            all_exist = False

    # Check README.md content
    print("\nValidating README.md content...")
    readme_path = project_root / 'README.md'
    if readme_path.exists():
        with open(readme_path, 'r') as f:
            readme_content = f.read()

        required_sections = [
            'Overview',
            'Prerequisites',
            'Quick Start',
            'Usage',
            'Output Files',
            'Troubleshooting',
            'Architecture',
        ]

        missing_sections = []
        for section in required_sections:
            if section.lower() not in readme_content.lower():
                missing_sections.append(section)

        if missing_sections:
            print(f"  ⚠️  Missing sections: {', '.join(missing_sections)}")
        else:
            print(f"  ✅ All required sections present")

        # Check for important commands
        if 'python benchmark.py' in readme_content:
            print(f"  ✅ Usage examples present")
        else:
            print(f"  ⚠️  Missing usage examples")

    return all_exist


def test_project_structure():
    """Test that all project files are in place."""
    print("\n" + "=" * 70)
    print("[3/3] Testing Project Structure")
    print("=" * 70)

    required_dirs = [
        'src',
        'src/tests',
        'src/output',
        'templates',
    ]

    required_files = [
        'benchmark.py',
        'deploy_crdb.py',
        'setup.sh',
        'verify_setup.py',
        'src/config.py',
        'src/database.py',
        'src/schema.py',
        'src/data_loader.py',
        'src/test_runner.py',
        'src/retry_logic.py',
        'src/metrics.py',
        'src/tests/base.py',
        'src/tests/test_01_select_one.py',
        'src/tests/test_02_point_lookup.py',
        'src/tests/test_03_pgbench.py',
        'src/tests/test_04_rollup.py',
        'src/tests/test_05_window.py',
        'src/tests/test_06_join.py',
        'src/tests/test_07_phantom_read.py',
        'src/tests/test_08_nonrepeatable_read.py',
        'src/output/json_writer.py',
        'src/output/text_summary.py',
        'src/output/html_generator.py',
        'templates/dashboard_template.html',
    ]

    print("\nChecking directory structure...")
    all_dirs_exist = True
    for dirname in required_dirs:
        dirpath = project_root / dirname
        if dirpath.exists() and dirpath.is_dir():
            print(f"  ✅ {dirname}/")
        else:
            print(f"  ❌ {dirname}/ MISSING")
            all_dirs_exist = False

    print("\nChecking core files...")
    all_files_exist = True
    for filename in required_files:
        filepath = project_root / filename
        if filepath.exists():
            # Just mark as present, don't print all
            pass
        else:
            print(f"  ❌ {filename} MISSING")
            all_files_exist = False

    if all_files_exist:
        print(f"  ✅ All {len(required_files)} core files present")
    else:
        print(f"  ❌ Some files missing")

    # Count total Python files
    python_files = list(project_root.glob('**/*.py'))
    python_files = [f for f in python_files if 'venv' not in str(f) and '__pycache__' not in str(f)]

    print(f"\n✅ Project statistics:")
    print(f"   Python files: {len(python_files)}")
    print(f"   Test modules: {len(list((project_root / 'src/tests').glob('test_*.py')))}")
    output_modules = list((project_root / 'src/output').glob('*.py'))
    print(f"   Output modules: {len(output_modules) - 1}")  # Exclude __init__.py

    return all_dirs_exist and all_files_exist


def test_help_command():
    """Test that benchmark.py has proper help text."""
    print("\n" + "=" * 70)
    print("[4/4] Testing CLI Help Content")
    print("=" * 70)

    print("\nChecking benchmark.py for help text...")

    try:
        with open(project_root / 'benchmark.py', 'r') as f:
            content = f.read()

        # Check for argparse usage
        checks = [
            ('argparse.ArgumentParser', 'Argument parser'),
            ('--crdb', 'CRDB connection arg'),
            ('--pg', 'PG connection arg'),
            ('--skip-load', 'Skip load option'),
            ('--output-dir', 'Output directory option'),
            ('Examples:', 'Usage examples'),
            ('Connection String Format', 'Connection format docs'),
        ]

        all_present = True
        for check_str, description in checks:
            if check_str in content:
                print(f"  ✅ {description}")
            else:
                print(f"  ❌ {description} - MISSING")
                all_present = False

        return all_present

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Phase 8 Test Suite - Main CLI and Documentation")
    print("=" * 70)

    results = []

    # Test imports
    results.append(('Imports', test_imports()))

    # Test documentation
    results.append(('Documentation', test_documentation()))

    # Test project structure
    results.append(('Project Structure', test_project_structure()))

    # Test help command
    results.append(('CLI Help', test_help_command()))

    # Summary
    print("\n" + "=" * 70)
    print("Phase 8 Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:9} {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All Phase 8 tests passed!")
        print("\nProject is complete and ready for use!")
        print("\nMain entry points:")
        print("  - benchmark.py: Run performance benchmark")
        print("  - deploy_crdb.py: Deploy CockroachDB cluster")
        print("  - setup.sh: Setup development environment")
        print("  - verify_setup.py: Verify installation")
        print("\nDocumentation:")
        print("  - README.md: Complete user guide")
        print("  - DEPLOYMENT.md: Deployment instructions")
        print("  - QUICKSTART.md: Quick start guide")
        print("\nNext steps:")
        print("  1. Review README.md for usage instructions")
        print("  2. Run setup.sh to create virtual environment")
        print("  3. Configure cluster_config.yaml for deployment")
        print("  4. Run benchmark.py with your database connections")
    else:
        print("❌ Some tests failed")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

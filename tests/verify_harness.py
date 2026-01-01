#!/usr/bin/env python3
"""
Simple verification script to check test harness is properly structured.
Doesn't require any external dependencies.
"""

import sys
from pathlib import Path

def check_files():
    """Check that all required files exist."""
    plugin_dir = Path(__file__).parent
    
    required_files = [
        'test_harness.py',
        'test_plugin.py',
        'examples.py',
        'setup_tests.py',
        'TEST_HARNESS.md',
        'README_TESTS.md',
    ]
    
    print("Checking test harness files...")
    print("=" * 60)
    
    all_exist = True
    for filename in required_files:
        filepath = plugin_dir / filename
        exists = filepath.exists()
        status = "✓" if exists else "✗"
        print(f"{status} {filename}")
        if not exists:
            all_exist = False
    
    return all_exist

def check_imports():
    """Check that imports are valid (without external deps)."""
    print("\n" + "=" * 60)
    print("Checking syntax...")
    print("=" * 60)
    
    import py_compile
    plugin_dir = Path(__file__).parent
    
    python_files = [
        'test_harness.py',
        'test_plugin.py',
        'examples.py',
        'setup_tests.py',
    ]
    
    all_valid = True
    for filename in python_files:
        filepath = plugin_dir / filename
        try:
            py_compile.compile(str(filepath), doraise=True)
            print(f"✓ {filename}")
        except py_compile.PyCompileError as e:
            print(f"✗ {filename}: {e}")
            all_valid = False
    
    return all_valid

def check_content():
    """Check that key content exists in files."""
    print("\n" + "=" * 60)
    print("Checking key components...")
    print("=" * 60)
    
    plugin_dir = Path(__file__).parent
    checks = [
        ('test_harness.py', 'class TestHarness'),
        ('test_harness.py', 'def fire_event'),
        ('test_plugin.py', 'class Test'),
        ('test_plugin.py', '@pytest.fixture'),
        ('examples.py', 'def example_'),
        ('TEST_HARNESS.md', '## Overview'),
        ('README_TESTS.md', 'Quick Start'),
    ]
    
    all_found = True
    for filename, search_str in checks:
        filepath = plugin_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            if search_str in content:
                print(f"✓ {filename}: contains '{search_str}'")
            else:
                print(f"✗ {filename}: missing '{search_str}'")
                all_found = False
        else:
            print(f"✗ {filename}: file not found")
            all_found = False
    
    return all_found

def main():
    """Run all checks."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "Test Harness Verification" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝\n")
    
    results = {
        'Files': check_files(),
        'Syntax': check_imports(),
        'Content': check_content(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for check_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {check_name}: {status}")
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All checks passed! Test harness is ready to use.\n")
        print("Next steps:")
        print("  1. Run: python3 setup_tests.py")
        print("  2. Activate: source .venv/bin/activate")
        print("  3. Run examples: python examples.py")
        print("  4. Run tests: pytest test_plugin.py -v")
        return 0
    else:
        print("\n✗ Some checks failed. Please review the output above.\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

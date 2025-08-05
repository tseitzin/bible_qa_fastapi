#!/usr/bin/env python3
"""Test runner with different test categories."""
import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and handle output."""
    print(f"\n🔄 {description}")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, cwd=os.getcwd())
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code {e.returncode})")
        return False


def main():
    """Run different test categories."""
    print("🧪 Bible Q&A API Test Runner")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        print("Available test types:")
        print("  unit        - Run only unit tests (fast)")
        print("  integration - Run only integration tests (requires DB)")
        print("  all         - Run all tests")
        print("  coverage    - Run all tests with coverage report")
        test_type = input("\nSelect test type (unit/integration/all/coverage): ").lower()
    
    success = True
    
    if test_type == "unit":
        success &= run_command(
            "python -m pytest tests/ -m 'not integration' -v",
            "Unit Tests Only"
        )
    
    elif test_type == "integration":
        success &= run_command(
            "python -m pytest tests/ -m integration -v",
            "Integration Tests Only"
        )
    
    elif test_type == "all":
        success &= run_command(
            "python -m pytest tests/ -v",
            "All Tests"
        )
    
    elif test_type == "coverage":
        success &= run_command(
            "python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html",
            "All Tests with Coverage"
        )
    
    else:
        print(f"❌ Unknown test type: {test_type}")
        return 1
    
    if success:
        print(f"\n🎉 All {test_type} tests completed successfully!")
        return 0
    else:
        print(f"\n💥 Some {test_type} tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

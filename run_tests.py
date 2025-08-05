#!/usr/bin/env python3
"""Test runner script for the Bible Q&A API."""
import subprocess
import sys
import os


def run_unit_tests():
    """Run only unit tests (fast)."""
    print("🧪 Running Unit Tests (Fast)")
    print("=" * 30)
    
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/", "-v", 
        "-m", "not integration",
        "--tb=short"
    ]
    
    return subprocess.run(cmd).returncode


def run_integration_tests():
    """Run integration tests using the dedicated runner."""
    print("🧪 Running Integration Tests")
    print("=" * 30)
    
    # Use the dedicated integration test runner
    cmd = [sys.executable, "run_integration_tests.py"]
    return subprocess.run(cmd).returncode


def run_all_tests():
    """Run all tests."""
    print("🧪 Running All Tests")
    print("=" * 20)
    
    # First run unit tests
    unit_result = run_unit_tests()
    if unit_result != 0:
        print("❌ Unit tests failed, skipping integration tests")
        return unit_result
    
    print("\n" + "="*50)
    
    # Then run integration tests
    integration_result = run_integration_tests()
    
    if unit_result == 0 and integration_result == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ Tests failed. Unit: {unit_result}, Integration: {integration_result}")
        return 1


def run_coverage():
    """Run all tests with coverage report."""
    print("🧪 Running Tests with Coverage")
    print("=" * 35)
    
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/", "-v",
        "-m", "not integration",  # Only unit tests for coverage
        "--cov=app", 
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov"
    ]
    
    result = subprocess.run(cmd).returncode
    
    if result == 0:
        print("\n📊 Coverage report generated in htmlcov/index.html")
    
    return result


def main():
    """Main function to handle different test modes."""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py [unit|integration|all|coverage]")
        print("  unit        - Run unit tests only (fast)")
        print("  integration - Run integration tests only")
        print("  all         - Run all tests")
        print("  coverage    - Run unit tests with coverage report")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    # Ensure we're in the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print("❌ pytest not found. Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    
    # Run appropriate test mode
    if mode == "unit":
        exit_code = run_unit_tests()
    elif mode == "integration":
        exit_code = run_integration_tests()
    elif mode == "all":
        exit_code = run_all_tests()
    elif mode == "coverage":
        exit_code = run_coverage()
    else:
        print(f"❌ Unknown test mode: {mode}")
        print("Available modes: unit, integration, all, coverage")
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

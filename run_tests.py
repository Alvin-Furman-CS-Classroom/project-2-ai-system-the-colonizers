"""
Test runner script.

Runs all unit tests and integration tests.
"""

import unittest
import sys


def run_all_tests():
    """Discover and run all tests."""
    # Discover unit tests
    unit_loader = unittest.TestLoader()
    unit_suite = unit_loader.discover('unit_tests', pattern='test_*.py')
    
    # Discover integration tests
    integration_loader = unittest.TestLoader()
    integration_suite = integration_loader.discover('integration_tests', pattern='test_*.py')
    
    # Combine test suites
    all_tests = unittest.TestSuite([unit_suite, integration_suite])
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(all_tests)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

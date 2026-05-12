import os
import sys

import pytest

# Add src and project root to sys.path
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))

# Run tests
if __name__ == "__main__":
    # Default: run all tests
    test_paths = ["tests/"]

    # Allow overriding via command line args
    if len(sys.argv) > 1:
        test_paths = sys.argv[1:]

    exit_code = pytest.main(
        [
            *test_paths,
            "-v",
            "--tb=short",
            "--cov=src",
            "--cov=api",
            "--cov=optimization",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
        ]
    )
    sys.exit(exit_code)

import os
import sys

import pytest

# Add src to sys.path
sys.path.insert(0, os.path.abspath("src"))

# Run tests
if __name__ == "__main__":
    exit_code = pytest.main(["tests/integration/test_backend_resilience.py", "-v"])
    sys.exit(exit_code)

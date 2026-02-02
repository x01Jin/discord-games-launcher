"""Test suite for Discord Games Launcher.

Run all tests:
    pytest tests/ -v

Run specific test file:
    pytest tests/test_database.py -v
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

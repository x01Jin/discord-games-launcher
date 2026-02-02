"""Pytest configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.database import Database
from launcher.api import DiscordAPIClient
from launcher.dummy_generator import DummyGenerator
from launcher.process_manager import ProcessManager
from launcher.game_manager import GameManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def database(temp_dir):
    """Create a test database."""
    db_path = temp_dir / "test.db"
    return Database(db_path)


@pytest.fixture
def api_client(database, temp_dir):
    """Create a test API client."""
    cache_dir = temp_dir / "cache"
    return DiscordAPIClient(database, cache_dir)


@pytest.fixture
def dummy_generator(temp_dir):
    """Create a test dummy generator."""
    games_dir = temp_dir / "games"
    return DummyGenerator(games_dir)


@pytest.fixture
def process_manager(database):
    """Create a test process manager."""
    return ProcessManager(database)


@pytest.fixture
def game_manager(database, api_client, dummy_generator, process_manager):
    """Create a test game manager with all components."""
    return GameManager(
        database=database,
        api_client=api_client,
        dummy_generator=dummy_generator,
        process_manager=process_manager
    )

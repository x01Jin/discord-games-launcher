import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.api import DiscordAPIClient
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def database(temp_dir):
    db_path = temp_dir / "test.db"
    return Database(db_path)


@pytest.fixture
def api_client(database, temp_dir):
    cache_dir = temp_dir / "cache"
    return DiscordAPIClient(database, cache_dir)


@pytest.fixture
def mock_template(temp_dir):
    template_path = temp_dir / "DummyGame.exe"
    template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE_FOR_TESTING")
    return template_path


@pytest.fixture
def dummy_generator(temp_dir, mock_template):
    games_dir = temp_dir / "games"
    return DummyGenerator(games_dir, template_exe_path=mock_template)


@pytest.fixture
def process_manager(database, dummy_generator):
    return ProcessManager(database, dummy_generator)


@pytest.fixture
def game_manager(database, api_client, dummy_generator, process_manager):
    return GameManager(
        database=database,
        api_client=api_client,
        dummy_generator=dummy_generator,
        process_manager=process_manager,
    )

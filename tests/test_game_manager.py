"""Test script for Game Manager module.

Tests high-level game management operations including library management,
game search, and process control.

Usage:
    pytest tests/test_game_manager.py -v
    python tests/test_game_manager.py  # Run basic tests
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.database import Database  # noqa: E402
from launcher.api import DiscordAPIClient  # noqa: E402
from launcher.dummy_generator import DummyGenerator  # noqa: E402
from launcher.process_manager import ProcessManager  # noqa: E402
from launcher.game_manager import GameManager  # noqa: E402


def test_game_manager_initialization():
    """Test GameManager initialization with all components."""
    print("Testing GameManager initialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games")
        process_mgr = ProcessManager(db)

        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        assert game_mgr.db == db
        assert game_mgr.api == api
        assert game_mgr.dummy_gen == dummy_gen
        assert game_mgr.process_mgr == process_mgr

        print("  All components initialized")

    print("  PASSED")


def test_sync_games():
    """Test syncing games from API."""
    print("Testing game sync...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games")
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Mock API response
        mock_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["TG"],
                "executables": [
                    {"os": "win32", "name": "test.exe", "is_launcher": False},
                ],
                "icon": "icon123",
                "themes": ["action"],
                "isPublished": True,
            },
            {
                "id": 67890,
                "name": "Another Game",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "another.exe", "is_launcher": False},
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_response.raise_for_status.return_value = None

        with patch("launcher.api.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Sync games
            was_synced, count = game_mgr.sync_games(force=True)

            assert was_synced is True, "Should perform sync"
            assert count == 2, f"Expected 2 games, got {count}"

            # Verify games were cached
            all_games = game_mgr.get_all_games()
            assert len(all_games) == 2

            print(f"  Synced {count} games successfully")

    print("  PASSED")


def test_search_games():
    """Test searching for games in cache."""
    print("Testing game search...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games")
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Add test games to cache
        test_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["TG", "TestG"],
                "executables": [
                    {"os": "win32", "name": "test.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
            {
                "id": 67890,
                "name": "Another Game",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "another.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
            {
                "id": 11111,
                "name": "Test Other",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "test_other.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
        ]

        db.save_games(test_games)

        # Search for "Test" should find Test Game and Test Other
        results = game_mgr.search_games("Test", limit=10)
        assert len(results) == 2, f"Expected 2 results for 'Test', got {len(results)}"

        names = [r.name for r in results]
        assert "Test Game" in names
        assert "Test Other" in names

        print(f"  Found {len(results)} games for 'Test'")

        # Search for exact game should work
        results = game_mgr.search_games("Another", limit=10)
        assert len(results) == 1
        assert results[0].name == "Another Game"

        print(f"  Found exact match: {results[0].name}")

    print("  PASSED")


def test_add_to_library():
    """Test adding game to library with dummy executable creation."""
    print("Testing add to library...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock template
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY")

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Add test game to cache
        test_game = {
            "id": 12345,
            "name": "Test Game",
            "aliases": [],
            "executables": [
                {"os": "win32", "name": "test.exe", "is_launcher": False},
                {"os": "win32", "name": "test_alt.exe", "is_launcher": False},
            ],
            "icon": None,
            "themes": [],
            "isPublished": True,
        }

        db.save_games([test_game])

        # Add to library
        success, message = game_mgr.add_to_library(12345)

        assert success is True, f"Failed to add game: {message}"
        print(f"  {message}")

        # Verify it's in library
        assert game_mgr.is_in_library(12345), "Game should be in library"
        print("  Game is in library")

        # Verify dummy executable was created
        lib_game = db.get_library_game(12345)
        assert lib_game is not None
        assert lib_game.executable_path is not None
        assert Path(lib_game.executable_path).exists()
        print(f"  Dummy created: {lib_game.executable_path}")

        # Verify executables are stored
        assert len(lib_game.executables) == 2
        print(f"  Stored {len(lib_game.executables)} executable candidates")

    print("  PASSED")


def test_add_duplicate_to_library():
    """Test that adding same game twice updates library."""
    print("Testing duplicate library add...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY")

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        test_game = {
            "id": 12345,
            "name": "Test Game",
            "aliases": [],
            "executables": [{"os": "win32", "name": "test.exe", "is_launcher": False}],
            "icon": None,
            "themes": [],
            "isPublished": True,
        }

        db.save_games([test_game])

        # Add first time
        success1, msg1 = game_mgr.add_to_library(12345)
        assert success1 is True

        # Try to add again - should fail (already in library)
        success2, msg2 = game_mgr.add_to_library(12345)
        assert success2 is False, "Should not add game already in library"
        print(f"  Correctly rejected duplicate: {msg2}")

    print("  PASSED")


def test_remove_from_library():
    """Test removing game from library."""
    print("Testing remove from library...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY")

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        test_game = {
            "id": 12345,
            "name": "Test Game",
            "aliases": [],
            "executables": [{"os": "win32", "name": "test.exe", "is_launcher": False}],
            "icon": None,
            "themes": [],
            "isPublished": True,
        }

        db.save_games([test_game])

        # Add to library
        success, _ = game_mgr.add_to_library(12345)
        assert success is True
        assert game_mgr.is_in_library(12345)
        print("  Added to library")

        # Remove from library
        success, message = game_mgr.remove_from_library(12345)

        assert success is True, f"Failed to remove: {message}"
        assert not game_mgr.is_in_library(12345), "Should not be in library"
        print(f"  Removed: {message}")

    print("  PASSED")


def test_get_library():
    """Test retrieving library with status info."""
    print("Testing get library...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY")

        db = Database(tmpdir / "test.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Add test games
        test_games = [
            {
                "id": 12345,
                "name": "Test Game 1",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "test1.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
            {
                "id": 67890,
                "name": "Test Game 2",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "test2.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
        ]

        db.save_games(test_games)

        # Add both to library
        for game_id in [12345, 67890]:
            game_mgr.add_to_library(game_id)

        # Get library
        library = game_mgr.get_library()

        assert len(library) == 2, f"Expected 2 games in library, got {len(library)}"

        # Check each has is_running status
        for game in library:
            assert "is_running" in game, "Each game should have is_running status"
            assert game["is_running"] is False, "Games should not be running initially"

        print(f"  Library has {len(library)} games")
        print("  All games have is_running status")

    print("  PASSED")


def run_all_tests():
    """Run all GameManager tests."""
    print("\n" + "=" * 50)
    print("GAME MANAGER MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_game_manager_initialization,
        test_sync_games,
        test_search_games,
        test_add_to_library,
        test_add_duplicate_to_library,
        test_remove_from_library,
        test_get_library,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed.append((test.__name__, e))
        print()

    print("=" * 50)
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name, error in failed:
            print(f"  - {name}: {error}")
    else:
        print(f"ALL TESTS PASSED: {len(tests)}/{len(tests)}")
    print("=" * 50 + "\n")

    return len(failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

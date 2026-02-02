"""Integration tests for Discord Games Launcher.

These tests verify the full application stack works together.
Tests the complete workflow from API to process management.

Usage:
    pytest tests/test_integration.py -v
    python tests/test_integration.py

Note: These are comprehensive tests that exercise multiple modules.
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


def test_full_workflow():
    """Test the complete user workflow."""
    print("Testing complete user workflow...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock template executable
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE")

        # Initialize all components
        db = Database(tmpdir / "launcher.db")
        api_client = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api_client, dummy_gen, process_mgr)

        print("  All components initialized")

        # Mock Discord API response
        mock_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["TG"],
                "executables": [{"os": "win32", "name": "testgame.exe"}],
                "icon": "abc123",
                "themes": ["action"],
                "isPublished": True,
            },
            {
                "id": 67890,
                "name": "Another Game",
                "aliases": [],
                "executables": [{"os": "win32", "name": "another.exe"}],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_response.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client_class:
            mock_http_client = MagicMock()
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            # Step 1: Sync games from API
            was_synced, count = game_mgr.sync_games(force=True)
            assert was_synced is True
            assert count == 2
            print(f"  Synced {count} games from API")

            # Step 2: Search games
            results = game_mgr.search_games("Test")
            assert len(results) == 1
            assert results[0].name == "Test Game"
            print(f"  Found game: {results[0].name}")

            # Step 3: Add game to library
            success, message = game_mgr.add_to_library(12345)
            assert success is True, f"Failed to add game: {message}"
            assert game_mgr.is_in_library(12345)
            print(f"  Added to library: {message}")

            # Step 4: Verify library
            library = game_mgr.get_library()
            assert len(library) == 1
            assert library[0]["game_id"] == 12345
            assert library[0]["name"] == "Test Game"
            print(f"  Library has {len(library)} game(s)")

            # Step 5: Check dummy was generated
            assert dummy_gen.dummy_exists(12345, "testgame.exe")
            print("  Dummy executable exists")

            # Note: We won't actually start the process in tests
            # as it would create a real running process
            print("  (Skipping actual process start/stop in tests)")

            # Step 6: Remove from library
            success, message = game_mgr.remove_from_library(12345)
            assert success is True, f"Failed to remove: {message}"
            assert not game_mgr.is_in_library(12345)
            assert len(game_mgr.get_library()) == 0
            print(f"  Removed from library: {message}")

            # Step 7: Verify dummy was removed
            assert not dummy_gen.dummy_exists(12345, "testgame.exe")
            print("  Dummy executable removed")

    print("  PASSED")


def test_cache_persistence():
    """Test that cache persists between sessions."""
    print("Testing cache persistence...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "launcher.db"

        # Create mock template executable
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE")

        # First session
        db1 = Database(db_path)
        api1 = DiscordAPIClient(db1, tmpdir / "cache")
        dummy1 = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        proc1 = ProcessManager(db1)
        _ = GameManager(db1, api1, dummy1, proc1)  # noqa: F841

        # Add mock game
        mock_games = [
            {
                "id": 11111,
                "name": "Persistent Game",
                "aliases": [],
                "executables": [{"os": "win32", "name": "persistent.exe"}],
                "icon": None,
                "themes": [],
                "isPublished": True,
            }
        ]
        db1.save_games(mock_games)

        # Add to library
        dummy1.output_dir.mkdir(parents=True, exist_ok=True)
        game_dir = dummy1.output_dir / "11111"
        game_dir.mkdir(parents=True)
        (game_dir / "persistent.exe").write_text("dummy")
        db1.add_to_library(11111, str(game_dir / "persistent.exe"), "persistent.exe")

        print("  First session: Added game to library")

        # Second session (new instances, same database)
        db2 = Database(db_path)
        api2 = DiscordAPIClient(db2, tmpdir / "cache")
        dummy2 = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        proc2 = ProcessManager(db2)
        mgr2 = GameManager(db2, api2, dummy2, proc2)

        # Verify data persisted
        game = db2.get_game(11111)
        assert game is not None
        assert game.name == "Persistent Game"

        assert db2.is_in_library(11111)
        library = mgr2.get_library()
        assert len(library) == 1

        print("  Second session: Data persisted correctly")
        print(f"  Cached games: {db2.get_cache_stats()['cached_games']}")
        print(f"  Library games: {len(library)}")

    print("  PASSED")


def test_multiple_games():
    """Test managing multiple games simultaneously."""
    print("Testing multiple games management...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock template executable
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE")

        db = Database(tmpdir / "launcher.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Add multiple games to cache
        mock_games = [
            {
                "id": i,
                "name": f"Game {i}",
                "aliases": [],
                "executables": [{"os": "win32", "name": f"game{i}.exe"}],
                "icon": None,
                "themes": [],
                "isPublished": True,
            }
            for i in range(1001, 1006)  # 5 games
        ]
        db.save_games(mock_games)
        print(f"  Added {len(mock_games)} games to cache")

        # Add all to library
        for game in mock_games:
            success, _ = game_mgr.add_to_library(game["id"])
            assert success, f"Failed to add game {game['id']}"

        library = game_mgr.get_library()
        assert len(library) == 5
        print(f"  All {len(library)} games in library")

        # Verify all dummies exist
        for game in mock_games:
            assert dummy_gen.dummy_exists(game["id"], game["executables"][0]["name"])
        print("  All dummy executables generated")

        # Remove multiple games
        for game in mock_games[:3]:  # Remove first 3
            success, _ = game_mgr.remove_from_library(game["id"])
            assert success

        library = game_mgr.get_library()
        assert len(library) == 2
        print(f"  Removed 3 games, {len(library)} remain")

    print("  PASSED")


def test_error_recovery():
    """Test error handling and recovery."""
    print("Testing error handling and recovery...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock template executable
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE")

        db = Database(tmpdir / "launcher.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Test: Add non-existent game
        success, message = game_mgr.add_to_library(99999)
        assert not success
        assert "not found" in message.lower() or "failed" in message.lower()
        print(f"  Correctly handled non-existent game: {message}")

        # Add a game to cache
        db.save_games(
            [
                {
                    "id": 77777,
                    "name": "No Windows Exe Game",
                    "aliases": [],
                    "executables": [{"os": "darwin", "name": "game.app"}],
                    "icon": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )

        # Test: Add game with no Windows executable
        success, message = game_mgr.add_to_library(77777)
        assert not success
        assert "windows" in message.lower() or "executable" in message.lower()
        print(f"  Correctly handled game without Windows exe: {message}")

        # Add valid game
        db.save_games(
            [
                {
                    "id": 88888,
                    "name": "Valid Game",
                    "aliases": [],
                    "executables": [{"os": "win32", "name": "valid.exe"}],
                    "icon": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )

        # Create dummy manually
        game_dir = dummy_gen.output_dir / "88888"
        game_dir.mkdir(parents=True)
        (game_dir / "valid.exe").write_text("dummy")
        db.add_to_library(88888, str(game_dir / "valid.exe"), "valid.exe")

        # Test: Start game with missing executable
        (game_dir / "valid.exe").unlink()  # Delete the file
        success, message = game_mgr.start_game(88888)
        assert not success
        assert "not found" in message.lower()
        print(f"  Correctly handled missing executable: {message}")

    print("  PASSED")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 50)
    print("INTEGRATION TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_full_workflow,
        test_cache_persistence,
        test_multiple_games,
        test_error_recovery,
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

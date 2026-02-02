"""Integration tests for Discord Games Launcher.

Tests the complete application stack working together.
Tests realistic workflows that exercise all components together.

Usage:
    pytest tests/test_integration.py -v
    python tests/test_integration.py

Note: These tests verify that components work together correctly,
not just in isolation.
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
    """Test the complete user workflow from sync to library management."""
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

        # Mock Discord API with realistic data
        mock_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["TG"],
                "executables": [
                    {"os": "win32", "name": "testgame.exe", "is_launcher": False},
                    {"os": "win32", "name": "launcher.exe", "is_launcher": True},
                ],
                "icon": "abc123",
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
            mock_http_client = MagicMock()
            mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
            mock_http_client.__exit__ = MagicMock(return_value=None)
            mock_http_client.get.return_value = mock_response
            mock_client_class.return_value = mock_http_client

            # Step 1: Sync games from API
            was_synced, count = game_mgr.sync_games(force=True)
            assert was_synced is True, "Should perform sync"
            assert count == 2, f"Expected 2 games, got {count}"
            print(f"  ✓ Synced {count} games from API")

            # Step 2: Verify cache was populated
            all_games = game_mgr.get_all_games()
            assert len(all_games) == 2, "Cache should have 2 games"
            print(f"  ✓ Cache populated with {len(all_games)} games")

            # Step 3: Search for specific game
            results = game_mgr.search_games("Test")
            assert len(results) == 1, f"Expected 1 result, got {len(results)}"
            assert results[0].name == "Test Game"
            print(f"  ✓ Search found: {results[0].name}")

            # Step 4: Add game to library
            success, message = game_mgr.add_to_library(12345)
            assert success is True, f"Failed to add game: {message}"
            assert game_mgr.is_in_library(12345), "Game should be in library"
            print(f"  ✓ Added to library: {message}")

            # Step 5: Verify library entry has executable candidates
            lib_game = db.get_library_game(12345)
            assert lib_game is not None, "Library game should exist"
            assert len(lib_game.executables) == 2, "Should store both executables"
            print(
                f"  ✓ Library entry has {len(lib_game.executables)} executable candidates"
            )

            # Step 6: Verify dummy executable was created
            assert dummy_gen.dummy_exists(12345, "testgame.exe"), "Dummy should exist"
            dummy_path = lib_game.executable_path
            assert Path(dummy_path).exists(), f"Dummy at {dummy_path} should exist"
            print(f"  ✓ Dummy created: {Path(dummy_path).name}")

            # Step 7: Verify all library operations work
            library = game_mgr.get_library()
            assert len(library) == 1, "Library should have 1 game"
            assert library[0]["game_id"] == 12345
            assert library[0]["name"] == "Test Game"
            assert "is_running" in library[0], "Each game should have is_running status"
            print(f"  ✓ Library retrieval works: {len(library)} game(s)")

            # Step 8: Add another game
            success, message = game_mgr.add_to_library(67890)
            assert success is True, f"Failed to add second game: {message}"
            library = game_mgr.get_library()
            assert len(library) == 2, "Library should have 2 games now"
            print(f"  ✓ Added second game: {len(library)} in library")

            # Step 9: Remove game from library
            success, message = game_mgr.remove_from_library(12345)
            assert success is True, f"Failed to remove: {message}"
            assert not game_mgr.is_in_library(12345), "Game should not be in library"
            library = game_mgr.get_library()
            assert len(library) == 1, "Library should have 1 game left"
            print(f"  ✓ Removed from library: {len(library)} remaining")

            # Step 10: Verify dummy was cleaned up
            assert not dummy_gen.dummy_exists(12345, "testgame.exe"), (
                "Dummy should be removed"
            )
            print("  ✓ Dummy executable cleaned up")

            # Step 11: Check stats
            stats = game_mgr.get_cache_stats()
            assert stats["cached_games"] == 2, "Cache should still have 2 games"
            assert stats["library_games"] == 1, "Library should have 1 game"
            print(
                f"  ✓ Stats valid: cache={stats['cached_games']}, library={stats['library_games']}"
            )

    print("  PASSED")


def test_cache_persistence():
    """Test that cache persists across database sessions."""
    print("Testing cache persistence across sessions...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "launcher.db"

        # Create mock template executable
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE")

        # First session - save games
        db1 = Database(db_path)
        api1 = DiscordAPIClient(db1, tmpdir / "cache")
        dummy1 = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        proc1 = ProcessManager(db1)
        gmgr1 = GameManager(db1, api1, dummy1, proc1)

        # Add test game in first session
        test_game = {
            "id": 11111,
            "name": "Persistent Game",
            "aliases": [],
            "executables": [
                {"os": "win32", "name": "persistent.exe", "is_launcher": False}
            ],
            "icon": None,
            "themes": [],
            "isPublished": True,
        }
        db1.save_games([test_game])

        # Add to library
        db1.add_to_library(
            11111,
            str(tmpdir / "games" / "11111" / "persistent.exe"),
            "persistent.exe",
            "persistent.exe",
            test_game["executables"],
        )

        print("  ✓ First session: Added game to library")

        # Second session (new instances, same database)
        db2 = Database(db_path)
        api2 = DiscordAPIClient(db2, tmpdir / "cache")
        dummy2 = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        proc2 = ProcessManager(db2)
        mgr2 = GameManager(db2, api2, dummy2, proc2)

        # Verify data persisted
        game = db2.get_game(11111)
        assert game is not None, "Game should be cached"
        assert game.name == "Persistent Game", (
            f"Expected 'Persistent Game', got {game.name}"
        )

        assert db2.is_in_library(11111), "Game should still be in library"
        library = mgr2.get_library()
        assert len(library) == 1, f"Expected 1 game in library, got {len(library)}"

        print("  ✓ Second session: Data persisted correctly")
        print(
            f"    Cached: {db2.get_cache_stats()['cached_games']}, Library: {len(library)}"
        )

    print("  PASSED")


def test_smart_executable_selection():
    """Test that best executable is selected when adding to library."""
    print("Testing smart executable selection...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"MOCK_DUMMY")

        db = Database(tmpdir / "launcher.db")
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
        process_mgr = ProcessManager(db)
        game_mgr = GameManager(db, api, dummy_gen, process_mgr)

        # Add game with multiple executables
        test_game = {
            "id": 99999,
            "name": "Multi Executable Game",
            "aliases": [],
            "executables": [
                # Launcher (should be down-scored)
                {"os": "win32", "name": "launcher.exe", "is_launcher": True},
                # Good candidate (should be selected)
                {"os": "win32", "name": "game.exe", "is_launcher": False},
                # Path with separator (down-scored)
                {"os": "win32", "name": "_retail_/wow.exe", "is_launcher": False},
                # Non-Windows (filtered out)
                {"os": "darwin", "name": "game.app", "is_launcher": False},
            ],
            "icon": None,
            "themes": [],
            "isPublished": True,
        }

        db.save_games([test_game])

        # Add to library - should intelligently select best executable
        success, message = game_mgr.add_to_library(99999)
        assert success is True, f"Failed: {message}"

        # Verify best executable was used
        lib_game = db.get_library_game(99999)
        assert lib_game is not None
        assert lib_game.process_name == "game.exe", (
            f"Expected 'game.exe', got {lib_game.process_name}"
        )

        # Verify all Windows executables are stored for fallback
        assert len(lib_game.executables) == 3, (
            f"Should store 3 Windows executables, got {len(lib_game.executables)}"
        )

        print(f"  ✓ Selected best: {lib_game.process_name}")
        print(f"  ✓ Stored {len(lib_game.executables)} candidates for retry")

    print("  PASSED")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 50)
    print("INTEGRATION TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_full_workflow,
        test_cache_persistence,
        test_smart_executable_selection,
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
    sys.exit(0 if success else 1)

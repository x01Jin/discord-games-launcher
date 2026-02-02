"""Test script for Database module.

Usage:
    pytest tests/test_database.py -v
    python tests/test_database.py  # Run basic tests
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.database import Database  # noqa: E402


def test_database_initialization():
    """Test database initialization and schema creation."""
    print("Testing database initialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Check database file was created
        assert db_path.exists(), "Database file not created"
        print("  Database file created successfully")

        # Check stats work
        stats = db.get_cache_stats()
        assert "cached_games" in stats
        assert "library_games" in stats
        assert "running_processes" in stats
        print(f"  Initial stats: {stats}")

    print("  PASSED")


def test_games_cache():
    """Test game caching operations."""
    print("Testing games cache operations...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Test saving games
        test_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["Test", "TG"],
                "executables": [{"os": "win32", "name": "test.exe"}],
                "icon": "abc123",
                "themes": ["action"],
                "isPublished": True,
            },
            {
                "id": 67890,
                "name": "Another Game",
                "aliases": [],
                "executables": [{"os": "win32", "name": "another.exe"}],
                "icon": "def456",
                "themes": ["rpg"],
                "isPublished": True,
            },
        ]

        db.save_games(test_games)
        print(f"  Saved {len(test_games)} games")

        # Test retrieving all games
        games = db.get_all_games()
        assert len(games) == 2, f"Expected 2 games, got {len(games)}"
        print(f"  Retrieved {len(games)} games")

        # Test retrieving single game
        game = db.get_game(12345)
        assert game is not None, "Game not found"
        assert game.name == "Test Game", f"Wrong game name: {game.name}"
        assert game.id == 12345, f"Wrong game ID: {game.id}"
        print(f"  Retrieved single game: {game.name}")

        # Test search
        results = db.search_games("Test")
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        assert results[0].name == "Test Game"
        print(f"  Search works: found '{results[0].name}'")

        # Test cache stats
        stats = db.get_cache_stats()
        assert stats["cached_games"] == 2
        print(f"  Stats: {stats}")

    print("  PASSED")


def test_library_operations():
    """Test library add/remove operations with executable candidates."""
    print("Testing library operations...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Add games to cache first
        test_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": [],
                "executables": [
                    {"os": "win32", "name": "test.exe", "is_launcher": False},
                    {"os": "win32", "name": "test_launcher.exe", "is_launcher": True},
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            }
        ]
        db.save_games(test_games)

        # Test adding to library with executable candidates
        executables = [
            {"os": "win32", "name": "test.exe", "is_launcher": False},
            {"os": "win32", "name": "test_launcher.exe", "is_launcher": True},
        ]
        db.add_to_library(
            12345, "/path/to/test.exe", "test.exe", "test.exe", executables
        )
        assert db.is_in_library(12345), "Game should be in library"
        print("  Added game to library with executable candidates")

        # Test retrieving library game with executables
        lib_game = db.get_library_game(12345)
        assert lib_game is not None, "Library game should exist"
        assert lib_game.game_id == 12345
        assert lib_game.executables is not None and len(lib_game.executables) == 2, (
            "Should store all executables"
        )
        print(f"  Library game has {len(lib_game.executables)} executable candidates")

        # Test retrieving library list
        library = db.get_library()
        assert len(library) == 1, f"Expected 1 library game, got {len(library)}"
        assert library[0]["name"] == "Test Game"
        print(f"  Library list has {len(library)} game(s)")

        # Test duplicate add (should update executables)
        new_executables = [
            {"os": "win32", "name": "test.exe", "is_launcher": False},
        ]
        db.add_to_library(
            12345, "/new/path/test.exe", "test.exe", "test.exe", new_executables
        )
        lib_game = db.get_library_game(12345)
        assert lib_game is not None and len(lib_game.executables) == 1, (
            "Should update with new executables list"
        )
        print("  Duplicate add updated executables correctly")

        # Test removing from library
        db.remove_from_library(12345)
        assert not db.is_in_library(12345), "Game should not be in library"
        library = db.get_library()
        assert len(library) == 0, "Library should be empty"
        print("  Removed game from library")

    print("  PASSED")


def test_process_tracking():
    """Test process tracking."""
    print("Testing process tracking...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Add game to library
        db.save_games(
            [
                {
                    "id": 12345,
                    "name": "Test Game",
                    "aliases": [],
                    "executables": [
                        {"os": "win32", "name": "test.exe", "is_launcher": False}
                    ],
                    "icon": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )

        # Add to library with all required parameters
        executables = [{"os": "win32", "name": "test.exe", "is_launcher": False}]
        db.add_to_library(
            12345, "/path/to/test.exe", "test.exe", "test.exe", executables
        )

        # Test setting process running
        db.set_process_running(12345, 1234)
        assert db.is_process_running(12345), "Process should be running"
        print("  Set process as running")

        # Test getting running processes
        processes = db.get_running_processes()
        assert 12345 in processes, "Game should be in running processes"
        assert processes[12345] == 1234, "PID should match"
        print(f"  Running processes: {processes}")

        # Test stopping process
        db.set_process_stopped(12345)
        assert not db.is_process_running(12345), "Process should not be running"
        processes = db.get_running_processes()
        assert len(processes) == 0, "No processes should be running"
        print("  Process stopped")

    print("  PASSED")


def test_executable_history_tracking():
    """Test tracking of executable attempts and success/failure history."""
    print("Testing executable history tracking...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Add game to cache
        db.save_games(
            [
                {
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
            ]
        )

        # Add to library
        executables = [
            {"os": "win32", "name": "test.exe", "is_launcher": False},
            {"os": "win32", "name": "test_alt.exe", "is_launcher": False},
        ]
        db.add_to_library(12345, "/path/test.exe", "test.exe", "test.exe", executables)

        # Record successful attempt
        db.record_executable_attempt(12345, "test.exe", success=True)

        # Record failed attempts
        db.record_executable_attempt(12345, "test_alt.exe", success=False)
        db.record_executable_attempt(12345, "test_alt.exe", success=False)

        # Get best executable (should be test.exe - it has success)
        best = db.get_preferred_executable(12345)
        assert best is not None, "Should find best executable"
        exe, score = best
        assert exe["name"] == "test.exe", "Best should be test.exe with success"
        print(f"  Best executable: {exe['name']} (score: {score})")

        # Verify success count (score = success_count * 20 - failure_count)
        # test.exe: 1 success, 0 failures = 20
        # test_alt.exe: 0 success, 2 failures = -2
        # So test.exe should have higher score
        assert score == 20, f"Expected score 20, got {score}"
        print("  Correct scoring: test.exe=20, test_alt.exe=-2")

        print("  PASSED")


def test_cache_sync():
    """Test cache sync tracking."""
    print("Testing cache sync tracking...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Initially should need sync
        assert db.needs_sync(), "Should need initial sync"
        print("  Initial sync needed")

        # Set last sync
        now = datetime.now()
        db.set_last_sync(now)

        # Should not need sync immediately
        assert not db.needs_sync(), "Should not need sync immediately"
        print("  Sync not needed immediately after sync")

        # Check last sync retrieval
        last_sync = db.get_last_sync()
        assert last_sync is not None, "Last sync should be set"
        print(f"  Last sync: {last_sync}")

    print("  PASSED")


def run_all_tests():
    """Run all database tests."""
    print("\n" + "=" * 50)
    print("DATABASE MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_database_initialization,
        test_games_cache,
        test_library_operations,
        test_process_tracking,
        test_executable_history_tracking,
        test_cache_sync,
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

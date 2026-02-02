"""Test script for Discord API Client module.

Tests the DiscordAPIClient including caching, icon handling, and executable scoring.

Usage:
    pytest tests/test_api.py -v
    python tests/test_api.py  # Run basic tests

Note: Some tests require internet connection to Discord API.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.api import DiscordAPIClient, DiscordAPIError  # noqa: E402
from launcher.database import Database  # noqa: E402


def test_api_initialization():
    """Test API client initialization."""
    print("Testing API client initialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"

        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)

        assert client.db == db
        assert client.cache_dir == cache_dir
        assert client.icons_dir == cache_dir / "icons"
        assert client.icons_dir.exists()
        print("  API client initialized successfully")

    print("  PASSED")


def test_best_win32_executables_scoring():
    """Test smart executable scoring system."""
    print("Testing executable smart scoring system...")

    test_executables = [
        # Launcher (should be downscored - is_launcher=True)
        {"os": "win32", "name": "launcher.exe", "is_launcher": True},
        # Good candidate - short name, not a launcher
        {"os": "win32", "name": "game.exe", "is_launcher": False},
        # Path with separator (should be downscored)
        {"os": "win32", "name": "_retail_/wow.exe", "is_launcher": False},
        # Started with underscore (less preferred)
        {"os": "win32", "name": "_game.exe", "is_launcher": False},
        # Non-Windows (should be filtered out)
        {"os": "darwin", "name": "game.app", "is_launcher": False},
        {"os": "linux", "name": "game", "is_launcher": False},
    ]

    result = DiscordAPIClient.get_best_win32_executables(test_executables)

    # Should only return Windows executables
    assert all(exe.get("os") == "win32" for exe in result), "Should only return win32"
    print(f"  Filtered to {len(result)} Windows executables")

    # Best should be 'game.exe' (non-launcher, short, no path, no underscore)
    assert result[0]["name"] == "game.exe", (
        f"Expected 'game.exe' first, got '{result[0]['name']}'"
    )
    print(f"  Best: {result[0]['name']} (score: {result[0]['_score']})")

    # Launcher should be last
    launcher = next((e for e in result if e["name"] == "launcher.exe"), None)
    assert launcher is not None, "Launcher should still be in list"
    assert launcher == result[-1], "Launcher should be scored lowest"
    print(f"  Launcher last: {launcher['name']} (score: {launcher['_score']})")

    print("  PASSED")


def test_executable_scoring_weights():
    """Test that scoring weights are applied correctly."""
    print("Testing executable scoring weights...")

    # Same executables, only differs in properties
    executables = [
        {
            "os": "win32",
            "name": "perfect.exe",
            "is_launcher": False,
        },  # 1000 - 100 + 50 + 20 = 970
        {
            "os": "win32",
            "name": "launcher.exe",
            "is_launcher": True,
        },  # 0 - 130 + 50 + 20 = -60
        {
            "os": "win32",
            "name": "_underscore.exe",
            "is_launcher": False,
        },  # 1000 - 150 + 50 + 0 = 900
    ]

    result = DiscordAPIClient.get_best_win32_executables(executables)

    # Verify scoring order
    assert result[0]["name"] == "perfect.exe"
    assert result[1]["name"] == "_underscore.exe"
    assert result[2]["name"] == "launcher.exe"

    # Verify scores are descending
    assert result[0]["_score"] > result[1]["_score"]
    assert result[1]["_score"] > result[2]["_score"]

    print(f"  Scores (descending): {[e['_score'] for e in result]}")
    print("  PASSED")


def test_process_name_normalization():
    """Test process name normalization for Discord detection."""
    print("Testing process name normalization...")

    test_cases = [
        ("game.exe", "game.exe"),  # Already normalized
        ("_retail_/wow-64.exe", "wow-64.exe"),  # Extract filename from path
        ("bin/game.exe", "game.exe"),  # Extract from subdirectory
        ("path/to/executable.exe", "executable.exe"),  # Deep path
    ]

    for input_name, expected in test_cases:
        result = DiscordAPIClient.normalize_process_name(input_name)
        assert result == expected, f"Expected {expected}, got {result}"
        print(f"  '{input_name}' -> '{result}'")

    print("  PASSED")


def test_icon_url_generation():
    """Test icon URL generation."""
    print("Testing icon URL generation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"

        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)

        game_id = 12345
        icon_hash = "abc123def456"

        url = client.get_icon_url(game_id, icon_hash)
        expected = (
            f"https://cdn.discordapp.com/app-icons/{game_id}/{icon_hash}.png?size=128"
        )
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"  Generated URL: {url}")

        # Test with custom size
        url = client.get_icon_url(game_id, icon_hash, size=256)
        assert "size=256" in url
        print("  Custom size works")

    print("  PASSED")


def test_sync_cache_logic():
    """Test cache sync logic with database persistence."""
    print("Testing cache sync logic...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"

        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)

        # Mock response data with varied executables
        mock_games = [
            {
                "id": 12345,
                "name": "Test Game",
                "aliases": ["TestG"],
                "executables": [
                    {"os": "win32", "name": "test.exe", "is_launcher": False},
                    {"os": "win32", "name": "test_launcher.exe", "is_launcher": True},
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
                    {"os": "win32", "name": "another.exe", "is_launcher": False}
                ],
                "icon": None,
                "themes": [],
                "isPublished": True,
            },
        ]

        # Mock the httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_response.raise_for_status.return_value = None

        with patch("launcher.api.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # First sync should perform sync
            result = client.sync_cache(force=True)
            assert result is True, "Should return True when sync performed"
            print("  First sync performed successfully")

            # Check games were saved to database
            games = db.get_all_games()
            assert len(games) == 2, f"Expected 2 games, got {len(games)}"

            # Verify both games are in the cache (order not guaranteed)
            game_names = {g.name for g in games}
            assert "Test Game" in game_names
            assert "Another Game" in game_names
            print(f"  Saved {len(games)} games to cache: {game_names}")

            # Verify games have correct data
            test_game = db.get_game(12345)
            assert test_game is not None
            assert len(test_game.executables) == 2
            assert test_game.aliases == ["TestG"]
            print(f"  Game has {len(test_game.executables)} executables")

            # Second sync without force should skip (cache is fresh)
            result = client.sync_cache(force=False)
            assert result is False, "Should return False when cache is fresh"
            print("  Correctly skipped sync for fresh cache")

    print("  PASSED")


def test_api_error_handling():
    """Test API error handling and retries."""
    print("Testing API error handling...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"

        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)

        # Test timeout error
        with patch("launcher.api.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get.side_effect = Exception("Connection timeout")
            mock_client_class.return_value = mock_client

            try:
                client.sync_cache(force=True)
                assert False, "Should have raised DiscordAPIError"
            except DiscordAPIError as e:
                print(f"  Correctly raised error for timeout: {e}")

    print("  PASSED")


def run_all_tests():
    """Run all API tests."""
    print("\n" + "=" * 50)
    print("API CLIENT MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_api_initialization,
        test_process_name_normalization,
        test_icon_url_generation,
        test_sync_cache_logic,
        test_api_error_handling,
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

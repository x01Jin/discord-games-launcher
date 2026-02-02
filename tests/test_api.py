"""Test script for Discord API Client module.

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


def test_win32_executable_filter():
    """Test filtering for Windows executables."""
    print("Testing Windows executable filter...")
    
    test_executables = [
        {'os': 'win32', 'name': 'game.exe'},
        {'os': 'darwin', 'name': 'game.app'},
        {'os': 'linux', 'name': 'game'},
        {'os': 'win32', 'name': 'launcher.exe'},
    ]
    
    result = DiscordAPIClient.get_win32_executable(test_executables)
    assert result is not None, "Should find Windows executable"
    assert result['name'] == 'game.exe', "Should return first Windows exe"
    print(f"  Found Windows exe: {result['name']}")
    
    # Test with no Windows executables
    no_win = [
        {'os': 'darwin', 'name': 'game.app'},
        {'os': 'linux', 'name': 'game'},
    ]
    result = DiscordAPIClient.get_win32_executable(no_win)
    assert result is None, "Should return None when no Windows exe"
    print("  Correctly returned None for no Windows executables")
    
    print("  PASSED")


def test_process_name_normalization():
    """Test process name normalization."""
    print("Testing process name normalization...")
    
    test_cases = [
        ('game.exe', 'game.exe'),
        ('_retail_/wow-64.exe', 'wow-64.exe'),
        ('bin/game.exe', 'game.exe'),
        ('path/to/executable.exe', 'executable.exe'),
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
        expected = f"https://cdn.discordapp.com/app-icons/{game_id}/{icon_hash}.png?size=128"
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"  Generated URL: {url}")
        
        # Test with custom size
        url = client.get_icon_url(game_id, icon_hash, size=256)
        assert "size=256" in url
        print("  Custom size works")
    
    print("  PASSED")


def test_sync_cache_logic():
    """Test cache sync logic (mocked)."""
    print("Testing cache sync logic...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"
        
        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)
        
        # Mock response data
        mock_games = [
            {
                'id': 12345,
                'name': 'Test Game',
                'aliases': [],
                'executables': [{'os': 'win32', 'name': 'test.exe'}],
                'icon': 'icon123',
                'themes': [],
                'isPublished': True
            }
        ]
        
        # Mock the httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_response.raise_for_status.return_value = None
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            # Test sync
            result = client.sync_cache(force=True)
            assert result is True, "Should return True when sync performed"
            print("  Sync performed successfully")
            
            # Check games were saved
            games = db.get_all_games()
            assert len(games) == 1, f"Expected 1 game, got {len(games)}"
            assert games[0].name == 'Test Game'
            print(f"  Saved game: {games[0].name}")
            
            # Test no sync when cache is fresh
            result = client.sync_cache(force=False)
            assert result is False, "Should return False when cache is fresh"
            print("  Correctly skipped sync for fresh cache")
    
    print("  PASSED")


def test_api_error_handling():
    """Test API error handling."""
    print("Testing API error handling...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cache_dir = Path(tmpdir) / "cache"
        
        db = Database(db_path)
        client = DiscordAPIClient(db, cache_dir)
        
        # Mock timeout error
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Connection error")
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get.side_effect = Exception("Connection error")
            mock_client_class.return_value = mock_client
            
            try:
                client.sync_cache(force=True)
                assert False, "Should have raised DiscordAPIError"
            except DiscordAPIError as e:
                print(f"  Correctly raised DiscordAPIError: {e}")
    
    print("  PASSED")


def run_all_tests():
    """Run all API tests."""
    print("\n" + "="*50)
    print("API CLIENT MODULE TESTS")
    print("="*50 + "\n")
    
    tests = [
        test_api_initialization,
        test_win32_executable_filter,
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
    
    print("="*50)
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name, error in failed:
            print(f"  - {name}: {error}")
    else:
        print(f"ALL TESTS PASSED: {len(tests)}/{len(tests)}")
    print("="*50 + "\n")
    
    return len(failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

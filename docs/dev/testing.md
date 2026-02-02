# Testing Documentation

## Overview

The Discord Games Launcher includes a comprehensive test suite using pytest.

**Location:** `tests/`
**Framework:** pytest>=8.3.0
**Additional:** pytest-qt>=4.4.0, pytest-asyncio>=0.23.0

## Test Structure

```structure
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── README.md               # Test documentation (this file)
├── test_database.py        # Database operation tests
├── test_api.py             # API client tests
├── test_dummy_generator.py # Dummy executable tests
└── test_integration.py     # End-to-end integration tests
```

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_database.py -v
pytest tests/test_api.py -v
pytest tests/test_dummy_generator.py -v
pytest tests/test_integration.py -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=launcher --cov=ui --cov-report=html
```

### Run Directly with Python

```bash
python tests/test_database.py
python tests/test_api.py
python tests/test_dummy_generator.py
```

## Environment Variables

### SKIP_PYINSTALLER_TESTS

Set to skip slow PyInstaller-based tests:

```bash
# Windows
set SKIP_PYINSTALLER_TESTS=True
pytest tests/test_dummy_generator.py -v

# Linux/macOS
export SKIP_PYINSTALLER_TESTS=True
pytest tests/test_dummy_generator.py -v
```

## Test Files

### test_database.py

**Coverage:** Database operations, caching, library management

**Key Tests:**

- Database initialization and schema creation
- Game caching (save, retrieve, search)
- Library operations (add, remove, query)
- Process tracking (PID storage, retrieval)
- Cache sync tracking (last_sync, needs_sync)

**Example:**

```python
def test_database_initialization(temp_db):
    """Test database creates tables on init."""
    stats = temp_db.get_cache_stats()
    assert stats["cached_games"] == 0
    assert stats["library_games"] == 0

def test_save_and_retrieve_game(temp_db):
    """Test saving and retrieving a game."""
    game = {
        "id": 123,
        "name": "Test Game",
        "aliases": ["Test", "TG"],
        "executables": [{"os": "win32", "name": "test.exe"}],
        "icon": "abc123",
        "themes": ["action"],
        "isPublished": True
    }
    temp_db.save_games([game])
    
    retrieved = temp_db.get_game(123)
    assert retrieved.name == "Test Game"
    assert retrieved.aliases == ["Test", "TG"]
```

### test_api.py

**Coverage:** Discord API client, HTTP operations, error handling

**Key Tests:**

- API client initialization
- Windows executable filtering
- Process name normalization
- Icon URL generation
- Cache sync logic (with mocked responses)
- Error handling (timeouts, HTTP errors)

**Example:**

```python
def test_get_win32_executable():
    """Test filtering Windows executables."""
    executables = [
        {"name": "game.exe", "os": "win32", "is_launcher": False},
        {"name": "game.app", "os": "darwin", "is_launcher": False}
    ]
    win_exe = DiscordAPIClient.get_win32_executable(executables)
    assert win_exe["name"] == "game.exe"

def test_normalize_process_name():
    """Test process name normalization."""
    assert DiscordAPIClient.normalize_process_name("path/game.exe") == "game.exe"
    assert DiscordAPIClient.normalize_process_name("game.exe") == "game.exe"

def test_icon_url_generation(api_client):
    """Test icon URL generation."""
    url = api_client.get_icon_url(12345, "icon_hash", size=128)
    assert "cdn.discordapp.com" in url
    assert "12345" in url
    assert "icon_hash" in url
    assert "size=128" in url
```

### test_dummy_generator.py

**Coverage:** Dummy executable generation, PyInstaller integration

**Key Tests:**

- Generator initialization
- Script template creation
- Path calculations
- Dummy removal
- Template formatting

**Note:** Tests requiring PyInstaller are skipped if `SKIP_PYINSTALLER_TESTS=True`.

**Example:**

```python
def test_generator_initialization(temp_generator):
    """Test generator creates output directory."""
    assert temp_generator.output_dir.exists()

def test_dummy_path_calculation(temp_generator):
    """Test dummy path calculation."""
    path = temp_generator.get_dummy_path(123, "game.exe")
    assert path.name == "game.exe"
    assert str(123) in str(path.parent)

def test_script_template_creation(temp_generator):
    """Test script template generation."""
    script = temp_generator._create_dummy_script(
        game_id=123,
        game_name="Test Game",
        process_name="test.exe"
    )
    assert script.exists()
    content = script.read_text()
    assert "Test Game" in content
    assert "test.exe" in content
```

### test_integration.py

**Coverage:** End-to-end integration testing

**Key Tests:**

- Full application stack initialization
- Game add → start → stop → remove flow
- Multiple games running simultaneously
- Error scenarios

**Example:**

```python
def test_full_game_lifecycle(integration_setup):
    """Test complete game lifecycle."""
    db, api, dummy_gen, process_mgr, game_mgr = integration_setup
    
    # 1. Sync games (mock API)
    # 2. Add game to library
    # 3. Start game
    # 4. Verify running
    # 5. Stop game
    # 6. Remove from library
```

## Fixtures (conftest.py)

### temp_db

Creates a temporary database for testing:

```python
@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path)
```

### temp_generator

Creates a temporary dummy generator:

```python
@pytest.fixture
def temp_generator(tmp_path):
    """Create a temporary dummy generator."""
    output_dir = tmp_path / "games"
    return DummyGenerator(output_dir)
```

### api_client

Creates an API client with mocked database:

```python
@pytest.fixture
def api_client(tmp_path):
    """Create an API client for testing."""
    db = Database(tmp_path / "test.db")
    cache_dir = tmp_path / "cache"
    return DiscordAPIClient(db, cache_dir)
```

## Test Data Helpers

### create_sample_game()

Creates sample game dictionaries for testing:

```python
def create_sample_game(game_id: int) -> Dict[str, Any]:
    """Create a sample game dictionary."""
    return {
        "id": game_id,
        "name": f"Test Game {game_id}",
        "aliases": [f"TG{game_id}"],
        "executables": [{"os": "win32", "name": f"game{game_id}.exe"}],
        "icon": f"icon_{game_id}",
        "themes": ["action"],
        "isPublished": True
    }
```

## Mocking

### Mocking API Responses

```python
import json
from unittest.mock import patch, MagicMock

def test_api_sync_with_mock(temp_db, tmp_path):
    """Test API sync with mocked response."""
    mock_games = [
        {"id": 1, "name": "Game 1", ...},
        {"id": 2, "name": "Game 2", ...}
    ]
    
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        api_client = DiscordAPIClient(temp_db, tmp_path / "cache")
        api_client.sync_cache(force=True)
        
        stats = temp_db.get_cache_stats()
        assert stats["cached_games"] == 2
```

## Best Practices

### 1. Use Temporary Paths

Always use `tmp_path` fixture for file operations:

```python
def test_something(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
```

### 2. Clean Up Resources

Use fixtures for automatic cleanup:

```python
@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    # Cleanup happens automatically when tmp_path is removed
```

### 3. Test Error Cases

Always test failure scenarios:

```python
def test_database_error_handling(temp_db):
    """Test handling of database errors."""
    # Test with invalid data
    with pytest.raises(Exception):
        temp_db.save_games(None)
```

### 4. Skip Slow Tests

Use environment variables for optional slow tests:

```python
import os

@pytest.mark.skipif(
    os.environ.get("SKIP_PYINSTALLER_TESTS") == "True",
    reason="PyInstaller tests skipped"
)
def test_generate_dummy_executable(temp_generator):
    """Test actual dummy generation (slow)."""
    result = temp_generator.generate_dummy(123, "Test", "test.exe")
    assert result[0].exists()
```

## Continuous Integration

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.13
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests (fast)
        run: |
          set SKIP_PYINSTALLER_TESTS=True
          pytest tests/ -v --cov=launcher
      
      - name: Run full tests
        run: pytest tests/ -v
```

## Debugging Tests

### Verbose Output

```bash
pytest tests/test_database.py -v -s
```

### Stop on First Failure

```bash
pytest tests/ -x
```

### Debug a Specific Test

```bash
pytest tests/test_database.py::test_save_and_retrieve_game -v --pdb
```

### Show Local Variables on Failure

```bash
pytest tests/ --showlocals
```

## Coverage Goals

**Target Coverage:**

- launcher/ modules: 80%+
- ui/ modules: 60%+
- Overall: 75%+

**Exclusions:**

- PyInstaller build artifacts
- Auto-generated UI code
- Debug print statements

Generate coverage report:

```bash
pytest tests/ --cov=launcher --cov=ui --cov-report=html
# Open htmlcov/index.html in browser
```

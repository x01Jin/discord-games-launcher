# Testing Documentation

## Overview

The Discord Games Launcher includes a comprehensive test suite using pytest.

**Location:** `tests/`
**Framework:** pytest>=9.1.1
**Additional:** pytest-asyncio>=1.4.0

## Test Structure

```structure
tests/
├── conftest.py              # Shared fixtures and configuration
├── README.md               # Test documentation (this file)
├── test_api.py             # Discord API client tests
├── test_bridge_ids.py      # Snowflake ID bridge serialization tests
├── test_database.py        # Database operation tests
├── test_dummy_generator.py # Dummy executable tests
├── test_game_manager.py    # Game manager tests
├── test_integration.py     # End-to-end integration tests
├── test_migration.py       # Schema migration tests
├── test_repair.py          # Library repair tests
└── test_startup_cleanup.py # Startup cleanup tests
```

## Running Tests

### Run All Tests

```bash
pytest tests/ -q
```

On Windows with the project virtual environment:

```cmd
.venv\Scripts\python.exe -m pytest tests/ -q
```

### Run Specific Test File

```bash
pytest tests/test_database.py -q
pytest tests/test_api.py -q
pytest tests/test_dummy_generator.py -q
pytest tests/test_integration.py -q
```

### Run with Coverage

Coverage targets `launcher/` only (the React frontend in `frontend/src/` has no Python coverage):

```bash
pytest tests/ -q --cov=launcher --cov-report=html
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
pytest tests/test_dummy_generator.py -q

# Linux/macOS
export SKIP_PYINSTALLER_TESTS=True
pytest tests/test_dummy_generator.py -q
```

## Test Files

### test_database.py

**Coverage:** Database initialization, game caching, library operations, process tracking, executable history, cache sync tracking.

### test_api.py

**Coverage:** Discord API client initialization, executable scoring, process name normalization, icon URL generation, cache sync logic, error handling.

### test_bridge_ids.py

**Coverage:** Snowflake-scale game IDs crossing the JS bridge serialized as strings.

### test_dummy_generator.py

**Coverage:** Copy-based dummy executable generation from the pre-built template.

**Note:** Tests requiring PyInstaller are skipped if `SKIP_PYINSTALLER_TESTS=True`.

### test_game_manager.py

**Coverage:** High-level library management, game search and sync, process control.

### test_integration.py

**Coverage:** Complete application stack working together in realistic workflows.

### test_migration.py

**Coverage:** Non-destructive schema migration without data loss.

### test_repair.py

**Coverage:** Executable candidate refresh, library repair composition, generator ownership.

### test_startup_cleanup.py

**Coverage:** Startup reconciliation of stale runtime records, orphaned directories, missing executables, and orphaned icons.

## Fixtures (conftest.py)

### temp_dir

Creates a temporary directory for test files:

```python
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

### database

Creates a test database in the temporary directory:

```python
@pytest.fixture
def database(temp_dir):
    """Create a test database."""
    db_path = temp_dir / "test.db"
    return Database(db_path)
```

### api_client

Creates a test API client backed by the test database:

```python
@pytest.fixture
def api_client(database, temp_dir):
    """Create a test API client."""
    cache_dir = temp_dir / "cache"
    return DiscordAPIClient(database, cache_dir)
```

### mock_template

Creates a mock DummyGame.exe template file for testing:

```python
@pytest.fixture
def mock_template(temp_dir):
    """Create a mock DummyGame.exe template for testing."""
    template_path = temp_dir / "DummyGame.exe"
    template_path.write_bytes(b"MOCK_DUMMY_GAME_EXE_FOR_TESTING")
    return template_path
```

### dummy_generator

Creates a test dummy generator with the mock template:

```python
@pytest.fixture
def dummy_generator(temp_dir, mock_template):
    """Create a test dummy generator with mock template."""
    games_dir = temp_dir / "games"
    return DummyGenerator(games_dir, template_exe_path=mock_template)
```

### process_manager

Creates a test process manager:

```python
@pytest.fixture
def process_manager(database, dummy_generator):
    """Create a test process manager."""
    return ProcessManager(database, dummy_generator)
```

### game_manager

Creates a test game manager with all components:

```python
@pytest.fixture
def game_manager(database, api_client, dummy_generator, process_manager):
    """Create a test game manager with all components."""
    return GameManager(
        database=database,
        api_client=api_client,
        dummy_generator=dummy_generator,
        process_manager=process_manager,
    )
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
        "icon_hash": f"icon_{game_id}",
        "themes": ["action"],
        "isPublished": True
    }
```

## Mocking

### Mocking API Responses

```python
import json
from unittest.mock import patch, MagicMock

def test_api_sync_with_mock(database, temp_dir):
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

        api_client = DiscordAPIClient(database, temp_dir / "cache")
        api_client.sync_cache(force=True)

        stats = database.get_cache_stats()
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
def database(temp_dir):
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    yield db
    # Cleanup happens automatically when temp_dir is removed
```

### 3. Test Error Cases

Always test failure scenarios:

```python
def test_database_error_handling(database):
    """Test handling of database errors."""
    # Test with invalid data
    with pytest.raises(Exception):
        database.save_games(None)
```

### 4. Skip Slow Tests

Use environment variables for optional slow tests:

```python
import os

@pytest.mark.skipif(
    os.environ.get("SKIP_PYINSTALLER_TESTS") == "True",
    reason="PyInstaller tests skipped"
)
def test_generate_dummy_executable(dummy_generator):
    """Test actual dummy generation (slow)."""
    result = dummy_generator.generate_dummy(123, "Test", "test.exe")
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
          python-version: "3.14"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests (fast)
        run: |
          set SKIP_PYINSTALLER_TESTS=True
          pytest tests/ -q --cov=launcher

      - name: Run full tests
        run: pytest tests/ -q
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
pytest tests/test_database.py::test_games_cache -v --pdb
```

### Show Local Variables on Failure

```bash
pytest tests/ --showlocals
```

## Coverage Goals

**Target Coverage:**

- launcher/ modules: 80%+
- Overall: 75%+

**Exclusions:**

- PyInstaller build artifacts
- Debug print statements

Generate coverage report:

```bash
pytest tests/ -q --cov=launcher --cov-report=html
# Open htmlcov/index.html in browser
```

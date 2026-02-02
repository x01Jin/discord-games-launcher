# Test Suite for Discord Games Launcher

This directory contains comprehensive tests for the Discord Games Launcher.

## Running Tests

### Run all tests

```bash
pytest tests/ -v
```

### Run specific test file

```bash
pytest tests/test_database.py -v
pytest tests/test_api.py -v
pytest tests/test_dummy_generator.py -v
```

### Run tests directly with Python

```bash
python tests/test_database.py
python tests/test_api.py
python tests/test_dummy_generator.py
```

## Test Files

- **test_database.py** - Tests for SQLite database operations, caching, library management, and process tracking
- **test_api.py** - Tests for Discord API client, including mocked API calls
- **test_dummy_generator.py** - Tests for dummy executable generation (PyInstaller integration)
- **test_integration.py** - End-to-end integration tests (creates full stack)

## Environment Variables

- `SKIP_PYINSTALLER_TESTS=True` - Skip tests that require PyInstaller (slow)

## Test Coverage

### Database Tests

- Database initialization and schema creation
- Game caching (save, retrieve, search)
- Library operations (add, remove, query)
- Process tracking (PID storage and retrieval)
- Cache sync tracking

### API Tests

- API client initialization
- Windows executable filtering
- Process name normalization
- Icon URL generation
- Cache sync logic (mocked)
- Error handling

### Dummy Generator Tests

- Generator initialization
- Script template creation
- Path calculations
- Dummy removal
- Template formatting

## Notes

- Tests use temporary directories that are automatically cleaned up
- API tests mock HTTP requests to avoid network dependencies
- Some tests require PyInstaller to be installed

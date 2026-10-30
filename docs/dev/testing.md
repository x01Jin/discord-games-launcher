# Testing

The suite runs on pytest (with pytest-asyncio) and lives in `tests/`. Most files
need no network access: HTTP is mocked and the CDP round trip uses a local socket
pair.

## Running

```cmd
.venv\Scripts\python.exe -m pytest tests/ -q
```

```bash
pytest tests/ -q                                # any environment with pytest
pytest tests/test_database.py -q                # one file
pytest tests/test_database.py -v -s             # with output
pytest tests/test_database.py::test_games_cache -v --pdb
pytest tests/ -x                                # stop on first failure
pytest tests/ --showlocals
```

`SKIP_PYINSTALLER_TESTS=True` skips the slow tests that call PyInstaller.

Coverage targets `launcher/` (the React frontend has no Python coverage) and
needs `pytest-cov`:

```bash
pytest tests/ -q --cov=launcher --cov-report=html
```

## Files

```structure
tests/
├── conftest.py                  # fixtures
├── README.md                    # short index of the files
├── test_api.py                  # catalogue client, scoring, normalization, icons
├── test_api_versions.py         # version cascade, sanitizing, drift warning
├── test_bridge_ids.py           # string IDs across the bridge
├── test_bridge_quests.py        # quest methods, error wrapping, events
├── test_database.py             # schema, caching, library, process tracking
├── test_database_queries.py     # paging, bulk lookup, stats memo
├── test_discord_native.py       # discovery, CDP session, payload parsing
├── test_discord_setup.py        # launch-argument rewriting, shortcuts, Run key
├── test_dummy_generator.py      # copy-based dummy generation
├── test_game_manager.py         # library management, sync, process control
├── test_integration.py          # full stack in realistic workflows
├── test_migration.py            # in-place schema migration
├── test_notifications.py        # toast script, finished-quest announcement
├── test_prefs.py                # settings file, clamping, corrupt file
├── test_quests.py               # states, runs, queue, stall, test mode, live progress
├── test_repair.py               # candidate refresh, repair, generator ownership
├── test_startup_cleanup.py      # stale rows, orphans, missing files, icons
└── test_updates.py              # version comparison and GitHub release check
```

## Fixtures

`conftest.py` provides:

| Fixture | What it builds |
| --- | --- |
| `temp_dir` | `tempfile.TemporaryDirectory()`, cleaned up by the context manager |
| `database` | `Database(temp_dir / "test.db")` |
| `api_client` | `DiscordAPIClient(database, temp_dir / "cache")` |
| `mock_template` | A `DummyGame.exe` holding the bytes `MOCK_DUMMY_GAME_EXE_FOR_TESTING` |
| `dummy_generator` | `DummyGenerator(games_dir, template_exe_path=mock_template)` |
| `process_manager` | `ProcessManager(database, dummy_generator)` |
| `game_manager` | `GameManager` wired with all of the above |

`conftest.py` also inserts the repository root into `sys.path`, so tests import
`launcher` without an install step.

## Patterns

Sample game rows come from small helpers such as `create_sample_game(game_id)`,
which returns an id, a name, one Windows executable, an icon hash, and a theme.
HTTP is patched at `launcher.api.httpx.Client`:

```python
with patch("launcher.api.httpx.Client") as mock_client_class:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client
```

Use `tmp_path` for anything that writes, and keep slow or platform-specific
tests behind `@pytest.mark.skipif(os.environ.get("SKIP_PYINSTALLER_TESTS") == "True", ...)`.
There is no CI configuration in the repository; the commands above are the
whole procedure.

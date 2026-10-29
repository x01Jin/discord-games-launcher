# Tests

pytest suite for the launcher. Most files need no network access.

## Running

```cmd
.venv\Scripts\python.exe -m pytest tests/ -q
```

```bash
pytest tests/test_database.py -q
pytest tests/test_quests.py -k heartbeat -v
```

`SKIP_PYINSTALLER_TESTS=True` skips the slow tests that call PyInstaller.

## Files

| File | Covers |
| --- | --- |
| `conftest.py` | Shared fixtures: `temp_dir`, `database`, `api_client`, `mock_template`, `dummy_generator`, `process_manager`, `game_manager` |
| `test_api.py` | Catalogue client, executable scoring, name normalization, icon URLs |
| `test_api_versions.py` | API version cascade, payload sanitizing, skipped-record counts, drift warning |
| `test_bridge_ids.py` | Snowflake game IDs as strings across the bridge |
| `test_bridge_quests.py` | Quest methods on the bridge, error wrapping, event push |
| `test_database.py` | Schema, caching, library operations, process tracking, history |
| `test_database_queries.py` | Catalogue paging and filtering, bulk lookup, stats memo |
| `test_discord_native.py` | Install discovery, target selection, websocket framing, `Runtime.evaluate` round trip, payload parsing |
| `test_discord_setup.py` | Launch-argument rewriting, shortcut and Run key round trips, idempotence |
| `test_dummy_generator.py` | Copy-based dummy generation from the template |
| `test_game_manager.py` | Library management, search, sync, process control |
| `test_integration.py` | Full stack in realistic workflows |
| `test_migration.py` | In-place schema migration without data loss |
| `test_notifications.py` | Toast script escaping, finished-quest announcement, failed runner |
| `test_prefs.py` | Settings file round trip, clamping, unknown keys, corrupt file |
| `test_quests.py` | Quest states, executable resolution, heartbeat and video runs, queue, prefs |
| `test_repair.py` | Candidate refresh, repair composition, generator ownership |
| `test_startup_cleanup.py` | Stale runtime rows, orphaned directories, missing executables, orphaned icons |
| `test_updates.py` | Version comparison and GitHub release lookup |

Fixtures and helpers are described in [docs/dev/testing.md](../docs/dev/testing.md).

Tests write into temporary directories that pytest removes; API tests mock HTTP,
so a normal run needs no Discord account or network.

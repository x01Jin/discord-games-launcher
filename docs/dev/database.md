# Database

SQLite stores the catalogue cache, the user library, and process tracking.
`Database` in `launcher/database.py` owns the queries; schema creation and
migration live in `launcher/database_schema.py` (`SchemaMixin`), and the row
dataclasses in `launcher/models.py`.

## Models

`Game` mirrors a `games_cache` row:

```python
@dataclass
class Game:
    id: int
    name: str
    aliases: list[str]
    executables: list[dict[str, Any]]
    icon_hash: str | None
    themes: list[str]
    is_published: bool
    cached_at: datetime
```

`LibraryGame` mirrors a `user_library` row: `game_id`, `executable_path`,
`process_name`, `normalized_process_name`, `executables`, `added_at`.

Both name columns store the filename only (`wow-64.exe`); the full API path
(`_retail_/wow-64.exe`) is used only when copying the dummy file, so the on-disk
layout mirrors it.

## Schema

```sql
CREATE TABLE games_cache (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT,               -- JSON array
    executables TEXT,           -- JSON array
    icon_hash TEXT,
    themes TEXT,                -- JSON array
    is_published INTEGER DEFAULT 1,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_library (
    game_id INTEGER PRIMARY KEY,
    executable_path TEXT,
    process_name TEXT NOT NULL,
    normalized_process_name TEXT,
    executables TEXT,           -- JSON array of Windows executables
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games_cache(id)
);

CREATE TABLE executable_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    executable_name TEXT NOT NULL,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_success_at TIMESTAMP,
    UNIQUE(game_id, executable_name),
    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
);

CREATE TABLE running_processes (
    game_id INTEGER PRIMARY KEY,
    pid INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
);

CREATE TABLE cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Indexes: `idx_games_name` on `games_cache(name)` and `idx_games_cached_at` on
`games_cache(cached_at)`.

`cache_metadata` holds `last_sync` (ISO timestamp), `schema_version`, and
`last_working_api_version`. Opening an older database adds missing columns with
`ALTER TABLE` and keeps the rows; only an unrecognized newer schema falls back to
recreating the database.

## Methods

| Method | Purpose |
| --- | --- |
| `get_last_sync()` / `set_last_sync(timestamp)` | Sync timestamp, timezone-aware (UTC); older rows are read as UTC |
| `needs_sync(max_age_days=7)` | True when the cache is older than the limit |
| `get_metadata_value(key)` / `set_metadata_value(key, value)` | Free-form `cache_metadata` rows |
| `save_games(games)` | UPSERT into `games_cache`; returns the number of records skipped |
| `get_game(game_id)` | One `Game` or None |
| `get_all_games(limit=None)` | All cached games, ordered by name |
| `get_games_page(limit=200, offset=0, win32_only=True)` | One catalogue page, filtered and paginated in SQL |
| `get_games(game_ids)` | Bulk lookup by id, chunked under SQLite's parameter cap |
| `ensure_game_row(game_id, name, icon_hash, executables)` | Insert-only cache row for an application the sync has not delivered |
| `search_games(query, limit=100, win32_only=True)` | `name LIKE '%query%'` |
| `add_to_library(game_id, executable_path, process_name, normalized_process_name, executables)` | UPSERT the library row with every candidate |
| `remove_from_library(game_id)` | Delete the library row, its runtime row, and its history |
| `get_library()` | Library rows joined with `games_cache` |
| `get_library_ids()` / `get_cached_game_ids()` | ID sets for reconciliation |
| `is_in_library(game_id)` / `get_library_game(game_id)` | Membership and one `LibraryGame` |
| `get_preferred_executable(game_id)` | Best candidate by history score (`success * 20 - failures`) |
| `record_executable_attempt(game_id, executable_name, success)` | Update `executable_history` |
| `set_process_running(game_id, pid)` / `set_process_stopped(game_id)` | Runtime rows |
| `get_running_processes()` / `is_process_running(game_id)` | Runtime reads, as `{game_id: pid}` |
| `clear_cache()` | Drop cached games and sync metadata |
| `get_cache_stats()` | Counts, memoised for three seconds |

`get_games_page()` evaluates "has a Windows executable" with SQLite's JSON1
extension over `executables`, so page boundaries do not depend on how many
unplayable games sit in a fetch window. `get_games()` lets the quest service
resolve every quest application in one query.

`get_cache_stats()` returns:

```python
{
    "cached_games": int,       # games in cache
    "games_no_win_exes": int,  # cached games without a Windows executable
    "library_games": int,      # games in user library
    "running_processes": int,  # active dummy processes
    "executable_history": int  # recorded detection attempts
}
```

The three-second memo is cleared by every write that can change a count:
`save_games`, `clear_cache`, `ensure_game_row`, `add_to_library`,
`remove_from_library`, `set_process_running`, and `set_process_stopped`. Without
it the JSON scan over the whole cache ran for the footer and for every catalogue
page.

## Connections and JSON

Each operation opens a short-lived connection through a context manager that
commits on success and always closes (`sqlite3.Row` row factory). Arrays are
stored as JSON text and decoded with `json.loads(row[...] or "[]")`.

## Data directory

`platformdirs` picks the folder, and `DCGL_DATA_DIR` overrides it:

```python
app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
```

On Windows the database is
`%LOCALAPPDATA%\discord-games-launcher\launcher.db`.

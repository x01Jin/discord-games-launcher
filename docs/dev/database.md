# Database Documentation

## Overview

The Discord Games Launcher uses SQLite for local data persistence. The database handles caching of Discord API data, user library management, and process tracking.

**Module:** `launcher/database.py`
**Class:** `Database` (line 39)

## Data Models

### Game

**Line:** 15

Represents a Discord-supported game from the API.

```python
@dataclass
class Game:
    id: int
    name: str
    aliases: List[str]
    executables: List[Dict[str, Any]]
    icon_hash: Optional[str]
    themes: List[str]
    is_published: bool
    cached_at: datetime
```

**Fields:**

- `id` - Discord application ID
- `name` - Display name
- `aliases` - Alternative names (JSON array in DB)
- `executables` - Platform-specific executables (JSON array in DB)
- `icon_hash` - Icon hash for CDN lookup
- `themes` - Game categories/tags (JSON array in DB)
- `is_published` - Publication status
- `cached_at` - Cache timestamp

### LibraryGame

**Line:** 29

Represents a game in the user's library.

```python
@dataclass
class LibraryGame:
    game_id: int
    executable_path: Optional[str]
    process_name: str
    added_at: datetime
```

**Fields:**

- `game_id` - Reference to games_cache.id
- `executable_path` - Path to generated dummy executable
- `process_name` - Process name for Discord detection
- `added_at` - When added to library

## Database Schema

### games_cache

Stores cached Discord API game data.

```sql
CREATE TABLE games_cache (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT,              -- JSON array
    executables TEXT,          -- JSON array
    icon_hash TEXT,
    themes TEXT,               -- JSON array
    is_published INTEGER DEFAULT 1,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**

```sql
CREATE INDEX idx_games_name ON games_cache(name);
CREATE INDEX idx_games_cached_at ON games_cache(cached_at);
```

### user_library

Stores user's game library.

```sql
CREATE TABLE user_library (
    game_id INTEGER PRIMARY KEY,
    executable_path TEXT,
    process_name TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games_cache(id)
);
```

### running_processes

Tracks active dummy processes.

```sql
CREATE TABLE running_processes (
    game_id INTEGER PRIMARY KEY,
    pid INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
);
```

### cache_metadata

Stores cache synchronization metadata.

```sql
CREATE TABLE cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Used for:**

- `last_sync` - ISO format timestamp of last API sync

## Database Class

### Initialization

```python
db = Database(db_path: Path)
```

**Parameters:**

- `db_path` - Path to SQLite database file

**Auto-creates:**

- Parent directories if needed
- All tables and indexes on first run

### Connection Management

**Line:** 47

Uses context manager for safe connections:

```python
@contextmanager
def _connect(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

### Cache Operations

#### get_last_sync()

**Line:** 113

```python
def get_last_sync(self) -> Optional[datetime]
```

Returns timestamp of last API sync, or None if never synced.

#### set_last_sync()

**Line:** 123

```python
def set_last_sync(self, timestamp: datetime) -> None
```

Updates the last sync timestamp in metadata.

#### needs_sync()

**Line:** 135

```python
def needs_sync(self, max_age_days: int = 7) -> bool
```

Checks if cache needs refreshing based on age.

**Parameters:**

- `max_age_days` - Maximum age before refresh needed (default: 7)

**Returns:** `True` if sync needed, `False` if cache is fresh

### Game Operations

#### save_games()

**Line:** 142

```python
def save_games(self, games: List[Dict[str, Any]]) -> None
```

Saves or updates games from API to cache.

**Uses UPSERT:**

```sql
INSERT INTO games_cache (...) VALUES (...)
ON CONFLICT(id) DO UPDATE SET ...
```

#### get_game()

**Line:** 169

```python
def get_game(self, game_id: int) -> Optional[Game]
```

Retrieves a single game by ID.

#### get_all_games()

**Line:** 179

```python
def get_all_games(self, limit: Optional[int] = None) -> List[Game]
```

Returns all cached games ordered by name.

#### search_games()

**Line:** 188

```python
def search_games(self, query: str, limit: int = 100) -> List[Game]
```

Searches games by name using SQL LIKE.

**Example:**

```python
games = db.search_games("overwatch", limit=10)
# Returns games where name LIKE '%overwatch%'
```

### Library Operations

#### add_to_library()

**Line:** 214

```python
def add_to_library(
    self, game_id: int, executable_path: str, process_name: str
) -> None
```

Adds a game to user's library.

**Uses UPSERT** to handle re-adding existing games.

#### remove_from_library()

**Line:** 228

```python
def remove_from_library(self, game_id: int) -> None
```

Removes game from library and cleans up running processes.

**Automatically:**

- Stops any running process for this game
- Removes from library table

#### get_library()

**Line:** 236

```python
def get_library(self) -> List[Dict[str, Any]]
```

Returns all library games with full game info (joined with games_cache).

**Returns:**

```python
[
    {
        "game_id": int,
        "name": str,
        "aliases": List[str],
        "icon_hash": Optional[str],
        "executable_path": str,
        "process_name": str,
        "added_at": str,
        "executables": List[Dict]
    }
]
```

#### is_in_library()

**Line:** 262

```python
def is_in_library(self, game_id: int) -> bool
```

Quick check if game is in library.

#### get_library_game()

**Line:** 270

```python
def get_library_game(self, game_id: int) -> Optional[LibraryGame]
```

Returns library entry for a specific game.

### Process Tracking

#### set_process_running()

**Line:** 285

```python
def set_process_running(self, game_id: int, pid: int) -> None
```

Records that a process is running for a game.

#### set_process_stopped()

**Line:** 297

```python
def set_process_stopped(self, game_id: int) -> None
```

Removes process tracking when stopped.

#### get_running_processes()

**Line:** 302

```python
def get_running_processes(self) -> Dict[int, int]
```

Returns all running processes as `{game_id: pid}`.

#### is_process_running()

**Line:** 308

```python
def is_process_running(self, game_id: int) -> bool
```

Checks if a process is marked as running.

### Utility Methods

#### clear_cache()

**Line:** 316

```python
def clear_cache(self) -> None
```

Clears all cached games and sync metadata. **Use with caution.**

#### get_cache_stats()

**Line:** 322

```python
def get_cache_stats(self) -> Dict[str, int]
```

Returns cache statistics:

```python
{
    "cached_games": int,      # Total games in cache
    "library_games": int,     # Games in user library
    "running_processes": int  # Active dummy processes
}
```

## JSON Handling

Arrays are stored as JSON strings in the database:

```python
# Saving (launcher/database.py:161)
json.dumps(game.get("aliases", []))
json.dumps(game.get("executables", []))
json.dumps(game.get("themes", []))

# Loading (launcher/database.py:206)
json.loads(row["aliases"] or "[]")
json.loads(row["executables"] or "[]")
json.loads(row["themes"] or "[]")
```

## Data Directory

Default location using `platformdirs`:

```python
from platformdirs import user_data_dir
app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
```

**Platform paths:**

- Windows: `%LOCALAPPDATA%\discord-games-launcher\launcher.db`
- Linux: `~/.local/share/discord-games-launcher/launcher.db`
- macOS: `~/Library/Application Support/discord-games-launcher/launcher.db`

## Testing

See `tests/test_database.py` for comprehensive tests:

- Database initialization
- CRUD operations
- Library management
- Process tracking
- Cache sync logic
- Search functionality

**Example test:**

```python
def test_add_to_library(temp_db):
    game = create_sample_game(1)
    temp_db.save_games([game])
    temp_db.add_to_library(1, "/path/to/exe", "game.exe")
    
    assert temp_db.is_in_library(1)
    lib = temp_db.get_library()
    assert len(lib) == 1
    assert lib[0]["game_id"] == 1
```

## Usage Examples

### Basic Operations

```python
from pathlib import Path
from launcher.database import Database

# Initialize
db = Database(Path("launcher.db"))

# Cache games from API
games = [...]  # From Discord API
db.save_games(games)

# Search
tf2_games = db.search_games("Team Fortress", limit=10)

# Library management
db.add_to_library(440, "/games/440/hl2.exe", "hl2.exe")
db.remove_from_library(440)

# Process tracking
db.set_process_running(440, 12345)
if db.is_process_running(440):
    db.set_process_stopped(440)

# Stats
stats = db.get_cache_stats()
print(f"Cached: {stats['cached_games']}, Library: {stats['library_games']}")
```

### Cache Management

```python
from datetime import datetime

# Check if refresh needed
if db.needs_sync(max_age_days=7):
    # Fetch from API and update
    games = fetch_from_discord_api()
    db.save_games(games)
    db.set_last_sync(datetime.now())
```

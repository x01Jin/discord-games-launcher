# API Documentation

## Discord API Client

**Module:** `launcher/api.py`
**Class:** `DiscordAPIClient` (line 25)

The API client handles all communication with Discord's applications API for fetching detectable games.

## Endpoints

### Discord API

```python
DISCORD_API_URL = "https://discord.com/api/v10/applications/detectable"
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"
```

The `applications/detectable` endpoint returns a list of all games/applications that Discord can detect as "Playing" status.

## Class: DiscordAPIClient

### Initialization

```python
client = DiscordAPIClient(
    database: Database,
    cache_dir: Path,
    timeout: float = 30.0
)
```

**Parameters:**

- `database` - Database instance for caching
- `cache_dir` - Directory for icon cache
- `timeout` - HTTP request timeout in seconds (default: 30)

### Methods

#### sync_cache()

**Line:** 35

Synchronizes the local cache with Discord API.

```python
def sync_cache(self, force: bool = False) -> bool
```

**Parameters:**

- `force` - Force sync even if cache is fresh

**Returns:** `True` if sync was performed, `False` if cache is up to date

**Example:**

```python
try:
    was_synced = client.sync_cache(force=False)
    if was_synced:
        print("Cache updated")
    else:
        print("Cache is current")
except DiscordAPIError as e:
    print(f"Sync failed: {e}")
```

#### _fetch_all_games()

**Line:** 55

Internal method to fetch all games from Discord API.

```python
def _fetch_all_games(self) -> List[Dict[str, Any]]
```

**Returns:** List of game dictionaries from Discord API

**Raises:** `DiscordAPIError` on HTTP errors

**Rate Limiting:** The Discord API endpoint does not require authentication and has reasonable rate limits for this use case.

#### get_icon_url()

**Line:** 85

Generates Discord CDN URL for a game icon.

```python
def get_icon_url(self, game_id: int, icon_hash: str, size: int = 128) -> str
```

**Parameters:**

- `game_id` - Discord application ID
- `icon_hash` - Icon hash from API
- `size` - Icon size in pixels (default: 128)

**Returns:** URL string for the icon

**Example:**

```python
url = client.get_icon_url(356869127241072640, "a0c9d2c4...", size=256)
# Returns: https://cdn.discordapp.com/app-icons/356869127241072640/a0c9d2c4....png?size=256
```

#### download_icon()

**Line:** 89

Downloads and caches a game icon locally.

```python
def download_icon(
    self, game_id: int, icon_hash: str, size: int = 128
) -> Optional[Path]
```

**Parameters:**

- `game_id` - Discord application ID
- `icon_hash` - Icon hash from API
- `size` - Icon size (default: 128)

**Returns:** Path to cached icon file, or `None` if download failed

**Caching:** Icons are stored in `cache_dir/icons/{game_id}_{icon_hash}_{size}.png`

**Example:**

```python
icon_path = client.download_icon(356869127241072640, "a0c9d2c4...")
if icon_path:
    print(f"Icon cached at: {icon_path}")
```

#### get_best_win32_executables()

**Line:** 146 (static method)

Get all Windows executables sorted by smart scoring for intelligent selection.

```python
@staticmethod
def get_best_win32_executables(
    executables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]
```

**Parameters:**

- `executables` - List of executable configurations from API

**Returns:** Sorted list of Windows executable configs (best first)

**Executable Config Structure:**

```python
{
    "is_launcher": bool,           # CRITICAL: Discord ignores launchers!
    "name": str,                   # Process name like "minecraft.exe"
    "os": str,                     # "win32", "darwin", or "linux"
    "arguments": List[str]         # Optional
}
```

**Scoring System:**

- Non-launcher: +1000 (CRITICAL - Discord ignores launchers!)
- Shorter name: -10 per character (simpler is better)
- No path separators: +50 (avoid "_retail_/bg3.exe")
- No underscore prefix: +20 (avoid "_wow.exe")

**Example:**

```python
executables = [
    {"name": "_launcher.exe", "os": "win32", "is_launcher": True},
    {"name": "_retail_/wow-64.exe", "os": "win32", "is_launcher": False},
    {"name": "wow.exe", "os": "win32", "is_launcher": False},
]
sorted_exes = DiscordAPIClient.get_best_win32_executables(executables)
# Returns sorted list with "wow.exe" first (highest score)
```

**Why This Matters:**

Discord's detection is strict. A launcher executable may fail completely, while a shorter, non-prefixed path is much more reliable for detection.

#### normalize_process_name()

**Line:** 181 (static method)

Normalizes process names that may contain path separators. Returns only the filename for Discord detection.

```python
@staticmethod
def normalize_process_name(name: str) -> str
```

**Parameters:**

- `name` - Raw process name from API (may include paths)

**Returns:** Normalized executable filename for Discord detection

**Examples:**

```python
# Handles cases like:
DiscordAPIClient.normalize_process_name("_retail_/wow-64.exe")
# Returns: "wow-64.exe"

DiscordAPIClient.normalize_process_name("devil may cry 5/devilmaycry5.exe")
# Returns: "devilmaycry5.exe"

DiscordAPIClient.normalize_process_name("minecraft.exe")
# Returns: "minecraft.exe"
```

**Note:** The full path is preserved in the filesystem for proper Discord detection (e.g., creating `_retail_/wow-64.exe`), but the normalized name is used for Discord's process lookup.

## Exceptions

### DiscordAPIError

**Line:** 19

Raised when Discord API requests fail.

```python
class DiscordAPIError(Exception):
    """Raised when Discord API request fails."""
```

**Common Causes:**

- Network connectivity issues
- Discord API rate limiting
- Invalid responses
- Timeout exceeded

**Handling:**

```python
from launcher.api import DiscordAPIClient, DiscordAPIError

try:
    client = DiscordAPIClient(database, cache_dir)
    client.sync_cache()
except DiscordAPIError as e:
    # Handle API errors specifically
    print(f"API Error: {e}")
except Exception as e:
    # Handle other errors
    print(f"Unexpected error: {e}")
```

## Response Format

### Game Object

Discord API returns game objects with this structure:

```json
{
  "id": "356869127241072640",
  "name": "Minecraft",
  "aliases": ["Minecraft"],
  "executables": [
    {
      "is_launcher": false,
      "name": "minecraft.exe",
      "os": "win32"
    }
  ],
  "icon": "a0c9d2c4e6f8g0h2i4j6k8l0m2n4o6p8q0r2s4t6u8v0w2x4",
  "themes": ["action", "fps", "multiplayer"],
  "isPublished": true
}
```

**Fields:**

- `id` - Discord application ID (string, though treated as int internally)
- `name` - Display name of the game
- `aliases` - Alternative names for the game
- `executables` - List of executable configurations per platform
- `icon` - Icon hash for CDN lookup
- `themes` - Game categories/tags
- `isPublished` - Whether the game is published

## Async Support

The client includes async versions of fetch methods:

```python
async def _fetch_all_games_async(self) -> List[Dict[str, Any]]
async def download_icon_async(self, game_id: int, icon_hash: str, size: int = 128) -> Optional[Path]
```

**Note:** These are currently not used in the main application but are available for future async implementations.

## Testing

See `tests/test_api.py` for comprehensive tests including:

- Mocked API responses
- Windows executable filtering
- Process name normalization
- Icon URL generation
- Error handling scenarios

## Usage Example

```python
from pathlib import Path
from launcher.api import DiscordAPIClient, DiscordAPIError
from launcher.database import Database

# Setup
db = Database(Path("launcher.db"))
cache_dir = Path("./cache")

# Create client
client = DiscordAPIClient(db, cache_dir, timeout=30.0)

try:
    # Sync cache
    was_synced = client.sync_cache(force=False)
    
    # Get game info
    game = db.get_game(356869127241072640)
    if game and game.icon_hash:
        # Download icon
        icon_path = client.download_icon(game.id, game.icon_hash, size=128)
        
    # Get all Windows executables sorted by score
    if game:
        exes = client.get_best_win32_executables(game.executables)
        if exes:
            best_exe = exes[0]  # Highest score
            normalized = client.normalize_process_name(best_exe['name'])
            print(f"Best executable: {best_exe['name']}")
            print(f"Normalized name: {normalized}")
            
except DiscordAPIError as e:
    print(f"API error: {e}")
```

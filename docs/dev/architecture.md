# System Architecture

## Overview

Discord Games Launcher follows a layered architecture with clear separation of concerns:

```flow
UI Layer (PyQt6)
├── MainWindow
├── BrowserTab
└── LibraryTab
       │
       ▼
Game Manager (Coordinator)
       │
   ┌───┴───┐
   ▼       ▼
API Client    Database    Process Manager
(Discord API) (SQLite)    (psutil)
   │           │           │
   ▼           ▼           ▼
HTTP (httpx)  Local Cache Dummy Generator
Discord API   User Library (PyInstaller)
```

## Components

### 1. UI Layer

**Location:** `ui/`

The user interface is built with PyQt6 and features a dark theme.

**Files:**

- `main_window.py:34` - Main application window with tabs
- `browser_tab.py:108` - Game browser and search interface
- `library_tab.py:228` - Library management and game control

**Key Responsibilities:**

- Display game database and user library
- Handle user interactions (search, add, start, stop)
- Apply consistent dark theme styling
- Periodic status updates (every 5 seconds)

### 2. Game Manager

**Location:** `launcher/game_manager.py:21`

Central coordinator that provides a high-level interface for all game operations.

**Key Methods:**

- `sync_games()` - Sync with Discord API (line 36)
- `search_games()` - Search cached games (line 52)
- `add_to_library()` - Add game and generate dummy (line 64)
- `remove_from_library()` - Remove game and cleanup (line 108)
- `start_game()` - Launch dummy process (line 157)
- `stop_game()` - Terminate process (line 193)

### 3. API Client

**Location:** `launcher/api.py:25`

Handles all communication with Discord's applications API.

**Key Features:**

- Fetches 3000+ games from `discord.com/api/v10/applications/detectable`
- Caches game data locally (refreshed every 7 days by default)
- Downloads game icons from Discord CDN
- Filters Windows executables from multi-platform entries

**Endpoints:**

```python
DISCORD_API_URL = "https://discord.com/api/v10/applications/detectable"
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"
```

### 4. Database

**Location:** `launcher/database.py:39`

SQLite database for local caching and user data persistence.

**Tables:**

- `games_cache` - Cached Discord API game data
- `user_library` - User's game library
- `running_processes` - Active dummy process tracking
- `cache_metadata` - Sync timestamps and metadata

**Schema Details:** See [Database Documentation](./database.md)

### 5. Dummy Generator

**Location:** `launcher/dummy_generator.py:21`

Generates executable files that mimic real game processes using PyInstaller.

**Process:**

1. Creates temporary Python script from template
2. Compiles with PyInstaller to single executable
3. Names executable to match game's process name (e.g., `overwatch.exe`)
4. Discord detects running process and shows "Playing" status

**Output Location:**

```path
%LOCALAPPDATA%\discord-games-launcher\games\{game_id}\{process_name}
```

### 6. Process Manager

**Location:** `launcher/process_manager.py:20`

Manages lifecycle of dummy game processes.

**Key Features:**

- Starts processes without console window (Windows)
- Tracks PIDs in database for persistence
- Monitors process health and cleans up stale records
- Graceful termination with fallback to force kill

## Data Flow

### Adding a Game to Library

```flow
User clicks "Add to Library"
         │
         ▼
┌─────────────────────┐
│   GameManager       │
│ add_to_library()    │
└─────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│Database│ │API Client│
│get_game│ │get_win32 │
│        │ │executable│
└────────┘ └──────────┘
         │
         ▼
┌─────────────────────┐
│  DummyGenerator     │
│  generate_dummy()   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   PyInstaller       │
│ (creates .exe)      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│     Database        │
│  add_to_library()   │
└─────────────────────┘
```

### Starting a Game

```flow
User clicks "Start"
         │
         ▼
┌─────────────────────┐
│   GameManager       │
│    start_game()     │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  ProcessManager     │
│  start_process()    │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  subprocess.Popen   │
│ (CREATE_NO_WINDOW)  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│     Database        │
│ set_process_running │
└─────────────────────┘
```

## Configuration

### Data Directories

Uses `platformdirs` for cross-platform paths:

```python
from platformdirs import user_data_dir
app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))

# Results in:
# Windows: %LOCALAPPDATA%\discord-games-launcher\
# Linux: ~/.local/share/discord-games-launcher/
# macOS: ~/Library/Application Support/discord-games-launcher/
```

**Subdirectories:**

- `launcher.db` - SQLite database
- `cache/icons/` - Downloaded game icons
- `games/{game_id}/` - Generated dummy executables

### Cache TTL

Default cache refresh interval: **7 days**

```python
# launcher/database.py:135
def needs_sync(self, max_age_days: int = 7) -> bool:
    last_sync = self.get_last_sync()
    if not last_sync:
        return True
    return datetime.now() - last_sync > timedelta(days=max_age_days)
```

## Threading and Concurrency

- **UI Thread:** All PyQt6 UI operations run on the main thread
- **Timers:** Periodic updates via `QTimer` (5-second intervals)
- **HTTP:** Synchronous httpx client (async available but unused)
- **Process Management:** Subprocess calls are non-blocking

## Error Handling

Each module defines custom exceptions:

```python
# launcher/api.py:19
class DiscordAPIError(Exception):
    """Raised when Discord API request fails."""

# launcher/game_manager.py:15
class GameManagerError(Exception):
    """Raised when game manager operation fails."""

# launcher/dummy_generator.py:15
class DummyGenerationError(Exception):
    """Raised when dummy executable generation fails."""

# launcher/process_manager.py:14
class ProcessError(Exception):
    """Raised when process operation fails."""
```

## Dependencies

See `requirements.txt` for full list:

- **PyQt6>=6.9.0** - GUI framework
- **httpx[http2]>=0.27.0** - HTTP client
- **platformdirs>=4.5.1** - App directories
- **pyinstaller>=6.14.1** - Dummy executable generation
- **psutil>=6.0.0** - Process management

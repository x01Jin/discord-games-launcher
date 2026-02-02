# System Architecture

## Overview

Discord Games Launcher follows a layered architecture with clear separation of concerns:

```flow
UI Layer (PyQt6)
├── MainWindow
├── BrowserTab (QTreeWidget)
└── LibraryTab (QListWidget with custom widgets)
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
Discord API   User Library (PyInstaller + background process)
```

## Components

### 1. UI Layer

**Location:** `ui/`

The user interface is built with PyQt6 and features a modern dark theme with proper list widgets for better organization.

**Files:**

- `main_window.py` - Main application window with tabbed interface
- `browser_tab.py` - Game browser using QTreeWidget with columns (Name, Executables, Status)
- `library_tab.py` - Library management using QListWidget with PyQt6 widget-based items

**Key Responsibilities:**

- Display game database in tree view with sorting/filtering
- Display user library in clean list view with status indicators using QLabel widgets
- Handle user interactions (search, add, start, stop, remove)
- Apply consistent dark theme styling
- Support context menus for quick actions
- Periodic status updates (every 5 seconds)

**UI Improvements:**

- **Browser Tab:** QTreeWidget with 3 columns (Game name + aliases, Executables, Status)
- **Library Tab:** QListWidget with PyQt6 custom widgets showing game name, process name, and running status
- **Context Menus:** Right-click for quick actions (Start/Stop/Remove)
- **Double-click:** Toggle start/stop in library
- **Multi-select:** Add multiple games at once from browser

### 2. Game Manager

**Location:** `launcher/game_manager.py`

Central coordinator providing high-level interface for all game operations.

**Key Methods:**

- `sync_games()` - Sync with Discord API
- `search_games()` - Search cached games
- `add_to_library()` - Add game and generate dummy background process
- `remove_from_library()` - Remove game, stop process, and cleanup all files
- `start_game()` - Launch dummy background process
- `stop_game()` - Terminate process and all children
- `stop_all_games()` - Stop all running processes

### 3. API Client

**Location:** `launcher/api.py`

Handles communication with Discord's applications API with improved executable field handling.

**Key Features:**

- Fetches 3000+ games from `discord.com/api/v10/applications/detectable`
- Caches game data locally (7-day refresh)
- Downloads game icons from Discord CDN
- Filters Windows executables with flexible field detection (handles missing 'name' field)
- Normalizes process names (handles paths like `_retail_/wow.exe`)
- Extracts executable names from `arguments` array when `name` field is missing

### 4. Database

**Location:** `launcher/database.py`

SQLite database for local caching and user data persistence.

**Tables:**

- `games_cache` - Cached Discord API game data
- `user_library` - User's game library
- `running_processes` - Active process tracking
- `cache_metadata` - Sync timestamps

### 5. Dummy Generator

**Location:** `launcher/dummy_generator.py`

Generates executable files using PyInstaller that can run as either GUI or background processes.

**Process:**

1. Creates temporary Python script from template (GUI or background mode)
2. Compiles with PyInstaller to single executable
3. Names executable to match game's process name
4. Generated executables run in background or with visible GUI window
5. Process stays alive with minimal CPU usage (sleeps 60 seconds at a time)
6. GUI mode includes PyQt6 bundle for visible window

**Key Features:**

- GUI mode for better Discord game detection
- Visible window with status panel (runtime, Discord status, troubleshooting tips)
- System tray integration for minimization
- Minimal CPU usage with sleep loop
- Proper cleanup of all build artifacts and directories
- PID file tracking for process management
- Fallback to background process if PyQt6 unavailable

**Template Locations:**

- `templates/gui_dummy_template.py` - GUI window with status panel (default)
- `templates/dummy_template.py` - Silent background process (fallback)

### 6. Process Manager

**Location:** `launcher/process_manager.py`

Manages lifecycle of dummy game processes with proper child process handling and duplicate prevention.

**Key Features:**

- Starts processes as background tasks (no console window needed)
- Tracks PIDs in database with verification
- **Duplicate prevention:** Verifies existing processes before starting new ones
- **Process verification:** Checks executable path to ensure correct game association
- **Recursive termination:** Kills child processes before parent
- Stale process detection and cleanup
- Graceful termination with fallback to force kill

**Process Termination:**

```python
# 1. Get all child processes recursively
children = parent.children(recursive=True)

# 2. Terminate children first
for child in children:
    child.terminate()

# 3. Wait for children
psutil.wait_procs(children, timeout=3)

# 4. Force kill remaining children
for child in alive:
    child.kill()

# 5. Terminate parent
parent.terminate()
```

**Duplicate Prevention:**

```python
# Before starting, verify existing process
if self.is_running(game_id):
    pid = self._local_pid_cache[game_id]
    if self._verify_game_process(game_id, pid):
        return pid  # Return existing valid process
    # Clean up stale entry
    self.db.set_process_stopped(game_id)
    del self._local_pid_cache[game_id]
```

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
│        │ │(handles   │
│        │ │missing    │
│        │ │name field)│
└────────┘ └──────────┘
         │
         ▼
┌─────────────────────┐
│  DummyGenerator     │
│  generate_dummy()   │
│                     │
│ - Creates temp      │
│   Python script     │
│ - Runs PyInstaller  │
│ - Logs all output   │
│   to file in        │
│   logs/ directory   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   PyInstaller       │
│ (creates .exe with  │
│  background process)│
│                     │
│ Output logged to:   │
│ games/logs/         │
│ pyinstaller_*.log   │
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
│  (duplicate check)  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  subprocess.Popen   │
│ (no console window) │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Dummy Executable  │
│ (background process │
│  - no GUI window)   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│     Database        │
│ set_process_running │
└─────────────────────┘
```

### Stopping a Game (Proper Cleanup)

```flow
User clicks "Stop" or "Remove"
         │
         ▼
┌─────────────────────┐
│   GameManager       │
│ stop_game() or      │
│ remove_from_library │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  ProcessManager     │
│  stop_process()     │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   _kill_process()   │
│                     │
│ 1. Get children     │
│ 2. Terminate kids   │
│ 3. Wait (3s)        │
│ 4. Force kill kids  │
│ 5. Terminate parent │
│ 6. Wait (3s)        │
│ 7. Force kill parent│
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  DummyGenerator     │
│  remove_dummy()     │
│                     │
│ - Remove .exe       │
│ - Remove .pid file  │
│ - Remove dist/      │
│ - Remove build/     │
│ - Remove .spec      │
│ - Remove game dir/  │
└─────────────────────┘
```

## Configuration

### Data Directories

Uses `platformdirs` for cross-platform paths:

```python
from platformdirs import user_data_dir
app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))

# Windows: %LOCALAPPDATA%\discord-games-launcher\
# Linux: ~/.local/share/discord-games-launcher/
# macOS: ~/Library/Application Support/discord-games-launcher/
```

**Subdirectories:**

- `launcher.db` - SQLite database
- `cache/icons/` - Downloaded game icons
- `games/{game_id}/` - Generated dummy executables and related files
- `games/logs/` - PyInstaller compilation logs (timestamped)

### Cache TTL

Default cache refresh interval: **7 days**

```python
def needs_sync(self, max_age_days: int = 7) -> bool:
    last_sync = self.get_last_sync()
    if not last_sync:
        return True
    return datetime.now() - last_sync > timedelta(days=max_age_days)
```

## Threading and Concurrency

- **UI Thread:** All PyQt6 UI operations on main thread
- **Timers:** Periodic updates via `QTimer` (5-second intervals)
- **HTTP:** Synchronous httpx client
- **Process Management:** Subprocess calls are non-blocking
- **PyInstaller:** Runs in background via `QThreadPool` with max 2 concurrent workers
- **Compilation Queue:** Real-time progress updates via worker signals to keep UI responsive
- **Worker Classes:** `GameAdditionWorker` for individual games, `BatchGameAdditionWorker` for multiple games

## Error Handling

Each module defines custom exceptions:

```python
class DiscordAPIError(Exception):
    """Raised when Discord API request fails."""

class GameManagerError(Exception):
    """Raised when game manager operation fails."""

class DummyGenerationError(Exception):
    """Raised when dummy executable generation fails."""

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

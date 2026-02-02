# System Architecture

## Overview

Discord Games Launcher follows a layered architecture with clear separation of concerns:

```flow
UI Layer (PyQt6)
├── MainWindow
├── BrowserTab (QTreeWidget)
└── LibraryTab (QListWidget)
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
Discord API   User Library (Copy-based template)
```

## Components

### 1. UI Layer

**Location:** `ui/`

The user interface is built with PyQt6 and features a modern dark theme.

**Files:**

- `main_window.py` - Main application window with tabbed interface
- `browser_tab.py` - Game browser using QTreeWidget with columns (Name, Executables, Status)
- `library_tab.py` - Library management using QListWidget with status indicators

**Key Responsibilities:**

- Display game database in tree view with sorting/filtering
- Display user library with status indicators
- Handle user interactions (search, add, start, stop, remove)
- Apply consistent dark theme styling
- Support context menus for quick actions
- Periodic status updates (every 5 seconds)

**UI Features:**

- **Browser Tab:** QTreeWidget with 3 columns (Game name + aliases, Executables, Status)
- **Library Tab:** QListWidget showing game name, process name, and running status
- **Context Menus:** Right-click for quick actions (Start/Stop/Remove)
- **Double-click:** Toggle start/stop in library
- **Multi-select:** Add multiple games at once from browser
- **Instant Addition:** Games are added instantly (no compilation queue)

### 2. Game Manager

**Location:** `launcher/game_manager.py`

Central coordinator providing high-level interface for all game operations.

**Key Methods:**

- `sync_games()` - Sync with Discord API
- `search_games()` - Search cached games
- `add_to_library()` - Add game by copying dummy template (instant)
- `remove_from_library()` - Remove game, stop process, cleanup files
- `start_game()` - Launch dummy process with game name argument
- `stop_game()` - Terminate process and all children
- `stop_all_games()` - Stop all running processes

### 3. API Client

**Location:** `launcher/api.py`

Handles communication with Discord's applications API.

**Key Features:**

- Fetches 3000+ games from `discord.com/api/v10/applications/detectable`
- Caches game data locally (7-day refresh)
- Downloads game icons from Discord CDN
- Filters Windows executables
- Normalizes process names (handles paths like `_retail_/wow.exe`)

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

Manages dummy executables by copying a pre-built template. This approach is inspired by the reference project's simple and efficient design.

**How It Works:**

1. A pre-built `DummyGame.exe` template exists in `templates/dist/`
2. When a game is added, the template is **copied** and **renamed** to match the target process name
3. When launched, the game name is passed as a **command-line argument**

**Path-Based Detection:**

Discord's detection database stores executable names that may include relative folder paths (e.g., `devil may cry 5/devilmaycry5.exe`, `_retail_/wow.exe`). The Dummy Generator preserves this folder structure to ensure proper detection:

- For `devil may cry 5/devilmaycry5.exe`:
  - Creates folder: `games/<game_id>/devil may cry 5/`
  - Creates exe: `devilmaycry5.exe` inside that folder
- Discord matches the running process by checking if its full path ends with the expected pattern

**Key Features:**

- **Instant game addition** - Just a file copy, no compilation needed
- **Single template** - One DummyGame.exe serves all games
- **Simple architecture** - No PyInstaller at runtime
- **Flexible naming** - Handles subdirectory paths like `_retail_/wow.exe`

**Template Location:**

- `templates/dummy_game.py` - Source code for the dummy game window
- `templates/dist/DummyGame.exe` - Pre-built template (built once with PyInstaller)
- `templates/build_dummy.py` - Build script to create the template

**Building the Template:**

```bash
python templates/build_dummy.py
```

This creates `templates/dist/DummyGame.exe` which is then copied for each game.

### 6. Process Manager

**Location:** `launcher/process_manager.py`

Manages lifecycle of dummy game processes.

**Key Features:**

- Starts processes with game name as argument
- Tracks PIDs in database with verification
- **Duplicate prevention:** Verifies existing processes before starting new ones
- **Process verification:** Checks executable path to ensure correct game association
- **Recursive termination:** Kills child processes before parent
- Stale process detection and cleanup

**Thread Management:**

The Process Manager uses PyQt6's QThread with a worker object pattern for game detection:

```python
# Worker object pattern - proper cleanup sequence
thread = QThread()
worker = DetectionWorker(...)
worker.moveToThread(thread)

# Signal connections for safe cleanup:
thread.started.connect(worker.run)      # Start worker when thread starts
worker.finished.connect(thread.quit)    # Request thread quit when worker done
thread.finished.connect(worker.deleteLater)  # Delete worker after thread stops
thread.finished.connect(thread.deleteLater)  # Delete thread after it stops
```

**Critical:** Worker and thread deletion must be handled via `deleteLater()` connected to `thread.finished`, not `worker.finished`. This ensures the thread has actually stopped before Qt cleans up objects, preventing "QThread: Destroyed while thread is still running" crashes.

**Process Launch:**

```python
# Start process with game name as argument
process = subprocess.Popen(
    [str(exe_path), game_name],  # Pass game name as argument
    cwd=str(working_dir),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)
```

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
    ┌────┴─────────────┐
    ▼                  ▼
┌────────┐    ┌──────────────────┐
│Database│    │  API Client      │
│get_game│    │get_best_win32_exe│
│        │    │normalize_name    │
└────────┘    └──────────────────┘
         │
         ▼
┌─────────────────────┐
│   DummyGenerator    │
│ensure_dummy_for_game│
│   (copies template) │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│      Database       │
│  add_to_library()   │
│(with all exe opts)  │
└─────────────────────┘
```

### Starting a Game

```flow
User clicks "Start"
         │
         ▼
┌─────────────────────┐
│   GameManager       │
│   start_game()      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  ProcessManager     │
│  start_process()    │
│  (passes game name  │
│   as argument)      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Dummy Process     │
│ (DummyGame Window)  │
│ Shows: "Minecraft"  │
└─────────────────────┘
         │
         ▼
Discord detects process name
Shows "Playing Minecraft"
```

## Directory Structure

```structure
discord-games-launcher/
├── launcher/           # Core business logic
│   ├── api.py         # Discord API client
│   ├── database.py    # SQLite operations
│   ├── dummy_generator.py  # Copy-based dummy management
│   ├── game_manager.py     # High-level coordinator
│   └── process_manager.py  # Process lifecycle
│
├── ui/                 # PyQt6 user interface
│   ├── main_window.py # Main window
│   ├── browser_tab.py # Game browser
│   └── library_tab.py # Library management
│
├── templates/          # Dummy executable template
│   ├── dummy_game.py      # Template source code
│   ├── build_dummy.py     # Build script
│   └── dist/              # Built template
│       └── DummyGame.exe
│
├── tests/              # Test suite
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_dummy_generator.py
│   └── test_integration.py
│
├── docs/               # Documentation
├── main.py            # Entry point
└── requirements.txt   # Dependencies
```

## Key Design Decisions

### Copy-Based Dummy Generation

Instead of compiling a new executable for each game using PyInstaller at runtime, we:

1. Pre-build a single `DummyGame.exe` template
2. Copy and rename it for each game
3. Pass the game name as a command-line argument at launch

**Benefits:**

- **Instant game addition** - Copying is much faster than compilation
- **Smaller disk footprint** - All games use the same template (just renamed copies)
- **Simpler code** - No need for PyInstaller at runtime
- **More reliable** - No compilation errors or dependency issues

### Game Name as Argument

The game name is passed to the dummy process at launch time, not embedded in the executable. This means:

- The same executable can display any game name
- The window title matches the game name
- The user sees what game is "running"

### Process Tracking

We track running processes in the database and verify them on each check:

- Prevents duplicate processes
- Detects when processes exit unexpectedly
- Cleans up stale records automatically

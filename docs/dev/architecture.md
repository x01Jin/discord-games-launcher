# System Architecture

## Overview

Discord Games Launcher is a Python backend with a React frontend,
glued by a pywebview bridge:

```flow
React Frontend (frontend/src)
├── Catalogue module (browse, search, add)
├── Library module (manage, repair)
└── Shared shell (header, tabs, footer, toasts)
        │  window.pywebview.api (string-ID JSON contract)
        ▼
Bridge (launcher/bridge.py)
        │
        ▼
Game Manager (Coordinator)
        │
    ┌───┴───┐
    ▼       ▼
API Client    Database    Process Manager
(Discord API) (SQLite)    (PID cache + psutil verification)
     │           │           │
     ▼           ▼           ▼
HTTP (httpx)  Local Cache Dummy Generator
Discord API   User Library (single shared instance)
```

## Components

### 1. Frontend

**Location:** `frontend/src/` (built to `frontend-dist/`, served by pywebview)

React + Vite + Tailwind. Catalogue and library features live in
self-contained modules (components, hooks, services); shared shell,
API client, store, and hooks live in `shared/`. See [UI](./ui.md).

### 2. Bridge

**Location:** `launcher/bridge.py`

The only frontend-facing surface. Exposes catalogue, library, process,
stats, sync, and repair methods over `window.pywebview.api`, and emits
a `library_changed` event on state changes. Game IDs cross as strings;
inputs are strictly validated. See [Bridge](./bridge.md).

### 3. Game Manager

**Location:** `launcher/game_manager.py`

Central coordinator providing the high-level interface for all game
operations.

**Key Methods:**

- `sync_games()` - Sync with Discord API, then refresh library candidates
- `search_games()` - Search cached games
- `add_to_library()` - Add game by copying dummy template (instant)
- `remove_from_library()` - Remove game, stop process, cleanup files
- `start_game()` - Validate and launch the best stored executable at once (no detection step, no waiting)
- `stop_game()` / `stop_all_games()` - Terminate processes
- `startup_cleanup()` - Boot/on-demand reconciliation of files vs database
- `refresh_library_candidates()` - Refresh stored executables from cache
- `repair_library()` - Full cleanup plus candidate refresh

(Batch adds are handled by `Bridge.add_many()` in `launcher/bridge.py`, which loops over `GameManager.add_to_library()`.)

Library repair and data-freshness mechanics are documented in
[Library Maintenance](./library-maintenance.md).

### 4. API Client

**Location:** `launcher/api.py`

Handles communication with Discord's applications API.

**Key Features:**

- Fetches 20,000+ games from `discord.com/api/v10/applications/detectable`
- Caches game data locally (7-day refresh)
- Downloads game icons from Discord CDN
- Filters Windows executables
- Normalizes process names (handles paths like `_retail_/wow.exe`)

### 5. Database

**Location:** `launcher/database.py`

SQLite database for local caching and user data persistence.

**Tables:**

- `games_cache` - Cached Discord API game data
- `user_library` - User's game library (executable candidates included)
- `executable_history` - Detection attempt success/failure per executable
- `running_processes` - Active process tracking
- `cache_metadata` - Sync timestamps and schema version

Opening an older database migrates it in place (new columns are added,
rows preserved); only an unrecognized newer schema falls back to
recreate. See [Database](./database.md).

### 6. Dummy Generator

**Location:** `launcher/dummy_generator.py`

Manages dummy executables by copying a pre-built template. Exactly one
instance exists per process: it is constructed in `main.py` and shared
by the game manager and the process manager (constructor injection).

**How It Works:**

1. A pre-built `DummyGame.exe` template exists in `templates/dist/`
2. When a game is added, the template is **copied** and **renamed** to match the target process name
3. When launched, the game name is passed as a **command-line argument**

**Path-Based Detection:**

Discord's detection database stores executable names that may include relative folder paths (e.g., `devil may cry 5/devilmaycry5.exe`, `_retail_/wow.exe`). The Dummy Generator preserves this folder structure to ensure proper detection:

- For `devil may cry 5/devilmaycry5.exe`:
  - Creates folder: `games/<game_id>/devil may cry 5/`
  - Creates exe: `devilmaycry5.exe` inside that folder
- The on-disk layout mirrors the API names so the copied dummy keeps the expected relative path

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

### 7. Process Manager

**Location:** `launcher/process_manager.py`

Manages lifecycle of dummy game processes.

**Key Features:**

- Starts processes with game name as argument
- Tracks PIDs in database with verification
- **Duplicate prevention:** Verifies existing processes before starting new ones
- **Process verification:** Matches the executable path by exact path
  segment, so game `22` never verifies against `.../222/...`
- **Recursive termination:** Kills child processes before parent
- Stale process detection and cleanup

**Direct Start:**

Starting a game launches the best stored executable candidate at once
and returns: no detection step, no waiting, no background threads.
Discord picks up the running process on its own scan cycle. The single
start outcome is recorded in `executable_history` for the stats count.

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
User double-clicks a library game
         │
         ▼
Bridge.start_game() (validates ID, rejects games already running)
         │
         ▼
┌─────────────────────┐
│   GameManager       │
│   start_game()      │
│ (validates: in      │
│  library, stopped,  │
│  has executables;   │
│  returns at once)   │
└─────────────────────┘
         │
         ▼
Game starts at once: the best stored executable is launched,
the outcome is recorded, and the UI updates via a single
`library_changed` event. No waiting, no retries.
┌─────────────────────┐
│   Dummy Process     │
│ (DummyGame Window)  │
│ Shows: game name,   │
│ "Game Started!",    │
│ live runtime        │
└─────────────────────┘
         │
         ▼
Discord detects process name
Shows "Playing [Game]"
```

## Directory Structure

```structure
discord-games-launcher/
├── launcher/           # Core business logic
│   ├── api.py         # Discord API client
│   ├── bridge.py      # pywebview frontend contract
│   ├── database.py    # SQLite operations (+ migration)
│   ├── dummy_generator.py  # Copy-based dummy management
│   ├── game_manager.py     # High-level coordinator (+ repair)
│   ├── logger.py           # Centralized logging
│   └── process_manager.py  # Process lifecycle + detection
│
├── frontend/           # React UI (Vite + Tailwind)
│   └── src/
│       ├── modules/   # catalogue, library
│       └── shared/    # api-client, components, hooks, store
├── frontend-dist/      # Built frontend served by pywebview
│
├── templates/          # Dummy executable template
│   ├── dummy_game.py      # Template source code
│   ├── build_dummy.py     # Build script
│   └── dist/              # Built template
│       └── DummyGame.exe
│
├── tests/              # Test suite
│   ├── test_api.py
│   ├── test_bridge_ids.py
│   ├── test_database.py
│   ├── test_dummy_generator.py
│   ├── test_game_manager.py
│   ├── test_integration.py
│   ├── test_migration.py
│   ├── test_repair.py
│   └── test_startup_cleanup.py
│
├── docs/               # Documentation
├── main.py            # Entry point (pywebview window)
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

### String Game IDs on the Wire

Discord IDs are snowflake-scale integers that JavaScript numbers cannot
represent exactly, so the bridge serializes every game ID as a string
and validates every inbound ID strictly. See [Bridge](./bridge.md).

### Process Tracking

We track running processes in the database and verify them on each check:

- Prevents duplicate processes
- Detects when processes exit unexpectedly
- Cleans up stale records automatically
- Path verification matches exact segments, immune to PID recycling

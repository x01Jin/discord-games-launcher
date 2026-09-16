# Logging Documentation

## Overview

The Discord Games Launcher uses a centralized logger (`launcher/logger.py`) shared by all backend components. Logs help diagnose detection failures, sync problems, and crashes.

**Module:** `launcher/logger.py`
**Class:** `GameLauncherLogger`

## Log Files

Log files live in the application data directory:

```structure
%LOCALAPPDATA%\discord-games-launcher\
└── logs\
    └── dcgl_YYYY-MM-DD.log
```

A new file is started each day (for example `dcgl_2026-09-15.log`). Each file rotates at **10 MB**, keeping **5 backups** (50 MB maximum).

## Log Levels

Two outputs with different levels:

| Output  | Level | Destination                |
| ------- | ----- | -------------------------- |
| File    | DEBUG | `logs/dcgl_YYYY-MM-DD.log` |
| Console | INFO  | stdout                     |

**Format:** `%(asctime)s - %(levelname)s - %(message)s` with timestamps as `YYYY-MM-DD HH:MM:SS`.

## Usage

Components receive the logger at construction:

```python
from launcher.logger import GameLauncherLogger

logger = GameLauncherLogger()
logger.app_start()

database = Database(db_path, logger=logger)
dummy_generator = DummyGenerator(games_dir)
process_manager = ProcessManager(database, dummy_generator, logger=logger)
```

On fatal errors the entry point records the traceback via `logger.critical`, and always runs process cleanup plus `logger.app_exit()` on shutdown.

## Helper Methods

Beyond the standard `debug` / `info` / `warning` / `error` / `critical` methods, the logger provides structured helpers:

### Application Lifecycle

- `app_start()` - Startup banner
- `app_exit()` - Shutdown banner
- `database_recreate()` - Warning when the schema check fails and the database is rebuilt

### Process Management

- `process_start(game_name, exe_path, pid)` - Dummy process launched
- `process_stop(game_name, pid, reason)` - Process stopped (`reason` defaults to `"user_stop"`)
- `process_kill(game_name, pid)` - Process force-killed

### Library and Database

- `game_add_library(game_name, game_id, exe_count)` - Game added to the library
- `game_remove_library(game_name, game_id)` - Game removed from the library
- `game_start_request(game_name, game_id)` - Start requested
- `database_operation(operation, table, details)` - Debug-level database operation record
- `record_executable_attempt(game_name, exe_name, success)` - Detection attempt recorded to executable history

## Collecting Logs for Bug Reports

Attach the current day's log file from `%LOCALAPPDATA%\discord-games-launcher\logs\` along with:

1. The exact error message or screenshot
2. Steps to reproduce
3. `python --version` output
4. Windows and Discord app versions

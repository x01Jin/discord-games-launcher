# Logging

`launcher/logger.py` provides `GameLauncherLogger`, one logger shared by every
backend component. It writes the file for the day in the application data
directory:

```structure
%LOCALAPPDATA%\discord-games-launcher\
└── logs\
    └── dcgl_YYYY-MM-DD.log
```

A new file starts each day. Each file rotates at **10 MB**, keeping **5 backups**
(50 MB maximum).

## Levels

| Output | Level | Destination |
| --- | --- | --- |
| File | DEBUG | `logs/dcgl_YYYY-MM-DD.log` |
| Console | INFO | stdout |

Format: `%(asctime)s - %(levelname)s - %(message)s`, timestamps as
`YYYY-MM-DD HH:MM:SS`.

## Usage

Components receive the logger at construction:

```python
from launcher.logger import GameLauncherLogger

logger = GameLauncherLogger()
logger.app_start()

database = Database(db_path, logger=logger)
process_manager = ProcessManager(database, dummy_generator, logger=logger)
```

On a fatal error the entry point records the traceback with `logger.critical`,
then always runs process cleanup and `logger.app_exit()` on shutdown.

## Helper methods

Beyond `debug` / `info` / `warning` / `error` / `critical`:

- Lifecycle: `app_start()`, `app_exit()`, `database_recreate()` (the schema check
  failed and the database is rebuilt).
- Processes: `process_start(game_name, exe_path, pid)`,
  `process_stop(game_name, pid, reason="user_stop")`, `process_kill(game_name, pid)`.
- Library: `game_add_library(game_name, game_id, exe_count)`,
  `game_remove_library(game_name, game_id)`, `game_start_request(game_name, game_id)`.
- Database: `database_operation(operation, table, details="")` at debug level, and
  `record_executable_attempt(game_name, exe_name, success)`.

## Bug reports

Attach today's log from `%LOCALAPPDATA%\discord-games-launcher\logs\`, the exact
error message, the steps that led to it, and the Windows and Discord versions.

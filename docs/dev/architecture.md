# System architecture

Discord Games Launcher is a Python backend with a React frontend, joined by a
pywebview bridge.

```flow
React frontend (frontend/src)
└── window.pywebview.api (string-ID JSON contract)
    └── Bridge (launcher/bridge.py)
        ├── Game manager (launcher/game_manager.py)
        │   ├── API client (launcher/api.py) -> discord.com applications API
        │   ├── Database (launcher/database.py) -> launcher.db
        │   └── Process manager (launcher/process_manager.py)
        │       └── Dummy generator (launcher/dummy_generator.py)
        └── Quest service (launcher/quests/)
            └── Discord client (launcher/discord_native/)
                └── CDP over loopback -> QuestStore in the renderer
```

## Components

**Frontend** (`frontend/src/`, built to `frontend-dist/`, served by pywebview).
React, Vite, and Tailwind. Quests, running, catalogue, and library live in
self-contained modules (components, hooks, services); the shell, API client,
store, and shared hooks live in `shared/`. See [UI](./ui.md).

**Bridge** (`launcher/bridge.py`). The only frontend-facing surface: catalogue,
library, process, stats, sync, repair, and quest methods over
`window.pywebview.api`, plus the `library_changed` event. Game IDs cross as
strings and inputs are strictly validated. See [Bridge](./bridge.md).

**Game manager** (`launcher/game_manager.py`). High-level operations:
`sync_games()`, `search_games()`, `add_to_library()`, `remove_from_library()`,
`start_game()`, `stop_game()` / `stop_all_games()`, and SQL-side catalogue paging
through `get_games_page()` / `count_playable_games()`. Repair, startup cleanup,
and candidate refresh arrive through `MaintenanceMixin`
(`launcher/library_maintenance.py`, see [Library maintenance](./library-maintenance.md)).
Batch adds are handled by `Bridge.add_many()`, which loops over
`add_to_library()`.

**API client** (`launcher/api.py`). Fetches 20,000+ games from
`discord.com/api/{version}/applications/detectable` (v10 stable, latest-first
cascade with the last working version remembered, see [API](./api.md)), caches
the data for 7 days, downloads icons from the Discord CDN, filters Windows
executables, and normalizes process names such as `_retail_/wow.exe`.

**Database** (`launcher/database.py`, schema in `launcher/database_schema.py`).
SQLite tables `games_cache`, `user_library`, `executable_history`,
`running_processes`, and `cache_metadata`. An older database migrates in place
(new columns added, rows preserved); only an unrecognized newer schema falls
back to recreate. See [Database](./database.md).

**Dummy generator** (`launcher/dummy_generator.py`). Copies a prebuilt
`DummyGame.exe` and renames it to the target process name. Exactly one instance
exists per process: `main.py` constructs it and hands it to the game manager and
the process manager.

A prebuilt `templates/dist/DummyGame.exe` is copied and renamed per game, and the
game name is passed as a command-line argument at launch. Discord's detection
database stores executable names that may include relative folder paths
(`devil may cry 5/devilmaycry5.exe`, `_retail_/wow.exe`), so the copy mirrors
that structure: `games/<game_id>/devil may cry 5/devilmaycry5.exe`. Nothing is
compiled at runtime. `templates/build_dummy.py` builds the template (see
[Build](./build.md)).

**Discord client access** (`launcher/discord_native/`: `client.py`, `cdp.py`,
`discovery.py`, `renderer/`). Reads the running desktop client instead of
calling Discord's REST API. Discovery covers the stable, PTB, and Canary
channels under `%APPDATA%` and `%LOCALAPPDATA%`. Access is the Chrome DevTools
Protocol endpoint Electron opens for `--remote-debugging-port`; `CdpConnection`
is a small RFC 6455 client rather than a dependency (loopback socket, text
frames, ping/pong, `Runtime.evaluate`). The expression finds the renderer's
`QuestStore` through `webpackChunkdiscord_app` and returns a compact JSON
payload.

Nothing is injected into Discord and no token, cookie, or credential is read.
The only control action is `connect()`, which restarts the client once with the
switch on loopback when it was started without it. Because the switch only takes
effect at launch, `launcher/discord_setup.py` adds it to the entries Windows
starts Discord from (the `HKCU` Run value and every Discord shortcut), through
`--process-start-args` because Squirrel starts the client via `Update.exe`.
`enable()` is idempotent, `disable()` restores the original command lines, and a
marker file lets `DiscordNative.status()` repair a shortcut that a Discord update
rewrote. See [Quests](./quests.md).

**Quest service** (`launcher/quests/`: `service.py`, `model.py`, `play.py`,
`watch.py`, `queue.py`, `monitor.py`). Turns the client's quest payload into the
list the UI shows: keeps play on desktop, watch video, and watch on mobile (drops
console and activity quests); labels each quest with the executable Discord
expects; computes state, progress, time left, reward, and the "in library"
badge. Play quests post `/quests/{id}/heartbeat` through the client's own HTTP
layer every 20 s, video quests post `/quests/{id}/video-progress`, and neither
touches the process manager or the dummy executables. One queue runs in two
lanes (one play run, one video), pumped by a monitor thread, with the configured
pause between finished runs. The payload is cached for 20 s and mutations
invalidate it.

**Process manager** (`launcher/process_manager.py`). Starts, verifies, and ends
dummy processes: PIDs tracked in the database with verification, duplicate
prevention, recursive termination (children before parent), stale record
cleanup, and exact path-segment matching so game `22` never verifies against
`.../222/...`.

## Starting a game

Bridge `start_game()` validates the ID and rejects a game that is already
running, then the game manager checks that the game is in the library, stopped,
and has executables. It launches the best stored candidate at once and returns:
no detection step, no waiting, no background threads. Discord picks the process
up on its own scan cycle. The outcome is recorded in `executable_history` for
the stats count, and the UI updates from one `library_changed` event.

```python
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = 7
process = subprocess.Popen(
    [str(exe_path), game_name],
    cwd=str(working_dir),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
    startupinfo=startupinfo,
)
```

Stopping collects `parent.children(recursive=True)`, terminates the children,
waits up to 3 s, kills whatever is left, then terminates the parent.

Adding a game stays on the same path: `get_game()` from the database,
`get_best_win32_executables()` and `normalize_process_name()` from the API client,
`ensure_dummy_for_game()` copies the template, and `add_to_library()` stores every
executable candidate.

## Key design decisions

**Copy-based dummy generation.** One prebuilt template, copied and renamed per
game, instead of compiling with PyInstaller at runtime. Adding a game is a file
copy, the disk footprint is one template plus small copies, and there is no
compilation to fail.

**Game name as an argument.** The name is passed at launch, not embedded, so the
same executable displays any game name in its window title.

**String game IDs on the wire.** Discord IDs are snowflake-scale integers that
JavaScript numbers cannot represent exactly, so the bridge serializes every game
ID as a string and validates every inbound ID. See [Bridge](./bridge.md).

**Process tracking in the database.** Each check verifies the tracked process,
which prevents duplicates, catches a process that exited on its own, and clears
stale records. Path verification matches exact segments, so it survives PID
recycling.

## Directory structure

```structure
launcher/
├── api.py, bridge.py, database.py, database_schema.py, models.py
├── discord_native/     # client.py, cdp.py, discovery.py, renderer/
├── discord_setup.py    # launch entries
├── discord_window.py   # focus and claim-in-client helpers
├── dummy_generator.py, game_manager.py, library_maintenance.py
├── logger.py, notifications.py, prefs.py, process_manager.py
├── quests/             # service.py, model.py, play.py, watch.py, queue.py, monitor.py
└── rpc_activity.py
frontend/src/           # App.tsx, modules/, shared/
frontend-dist/          # built frontend
templates/              # dummy_game.py, build_dummy.py, dist/DummyGame.exe
tests/                  # see Testing
main.py                 # pywebview window and startup
```

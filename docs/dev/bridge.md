# Bridge

## Overview

Module: `launcher/bridge.py`

The bridge is the only contract between the React frontend and the
Python backend. The frontend calls it as `window.pywebview.api`, and
the backend pushes async updates as `dcgl` CustomEvents. Method
results are plain JSON dicts; failures are returned as error payloads,
never raised.

The injected object is not complete when the page first paints: pywebview
creates `window.pywebview` before it fills in the method table. The frontend
accessor (`shared/api-client/bridge.ts`) waits for the specific method, so a
query fired on first paint does not call `undefined` and record a failure that
fixes itself on the next poll.

## Methods

### Catalogue and library

| Method                         | Input          | Returns                                                                             |
| ------------------------------ | -------------- | ----------------------------------------------------------------------------------- |
| `list_games(limit, offset)`    | ints           | `{games, total}` - Windows-executable games only, filtered and paged in SQL          |
| `search_games(query, limit)`   | string, int    | `{games}` - Windows-executable matches only                                          |
| `add_to_library(game_id)`      | string ID      | `{ok, message}`                                                                     |
| `add_many(game_ids)`           | string ID list | `{added, failed, message}`                                                          |
| `get_library()`                | -              | `{games}` with running flags                                                        |
| `remove_from_library(game_id)` | string ID      | `{ok, message}`                                                                     |
| `repair_library()`             | -              | `{ok, message, summary}`                                                            |
| `start_game(game_id)`          | string ID      | `{ok, message}`; starts immediately, emits `library_changed`                        |
| `stop_game(game_id)`           | string ID      | `{ok, message}`                                                                     |
| `stop_all_games()`             | -              | `{stopped}`                                                                         |
| `get_running()`                | -              | `{running}` - string ID list                                                        |
| `get_stats()`                  | -              | `{cached_games, library_games, running_processes, executable_history, games_no_win_exes}` |
| `sync_catalogue()`             | -              | `{synced, count, skipped, message}`                                                 |

`list_games` caps `limit` at 500 and reports `total` as the number of
Windows-playable games, so "showing X of Y" matches what can actually be
added. `get_stats` is memoised for three seconds in the database layer; the
footer-style reads behind it are a handful of aggregates plus one JSON scan
over the whole cache.

### Quests

Read from the running Discord client, never from the REST API. Details in
[Quests](./quests.md).

| Method                 | Input      | Returns                                                                                           |
| ---------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| `discord_status()`     | -          | `{installed, running, connected, channel, version, debug_port, silent, silent_wanted, silent_port, hint, error}` |
| `get_quests(force?)`   | bool (opt) | `{connected, quests, status, error, account, suspended_until, total_quests}`                       |
| `connect_discord()`    | -          | `{ok, message}` - starts Discord with the endpoint, or restarts it once if it is already running    |
| `start_discord()`      | -          | `{ok, message}` - launches Discord with the endpoint when it is closed; never restarts a running one  |
| `open_quest_in_discord(quest_id)` | string | `{ok, message}` - opens `discord://-/quest-home` so a quest can be accepted or watched    |
| `start_quest(quest_id)`| string ID  | `{ok, message}` - adds the quest's game to the library if needed, then starts it, emits `library_changed` |
| `stop_quest(quest_id)` | string ID  | `{ok, message}`, emits `library_changed`                                                            |
| `silent_mode_status()` | -          | `{port, enabled, wanted, patched, total, launchers}` - which Windows launch entries carry the endpoint |
| `enable_silent_mode()` | -          | `{ok, message, updated, failed}` - writes the switch into the Run key and every Discord shortcut    |
| `disable_silent_mode()`| -          | `{ok, message, restored, failed}` - puts the original arguments back and clears the marker           |

`get_quests` never raises. A missing client, a missing DevTools endpoint, or a
read that times out all come back as `{connected: false, error}` so the view
can show the reason.

Each quest carries `kind` (`play`, `watch`, `watch_mobile`), `enrolled`, and an
`action` (`run`, `stop`, `enroll`, `open`, `mobile`, `done`, `unsupported`).
`start_quest` refuses watch quests and unaccepted play quests by name, so the
UI and the backend cannot disagree about what is runnable.

`silent_mode_status()` never raises either: a machine where the shortcuts cannot
be read comes back as `{enabled: false, launchers: [], error}`, and the panel
falls back to the restart wording instead of showing an empty list. The three
silent-mode methods invalidate the quest service, so a Connect right after
enabling does not read a status cached before the switch existed.

`list_games` / `search_games` / `get_library` / `get_quests` include an `error`
field when the backend call itself fails; the frontend renders it with a retry
action instead of an empty view.

## ID contract

Discord game IDs are snowflake-scale integers that JavaScript numbers
cannot represent exactly (`2^53 - 1` limit). To keep IDs lossless:

- Outbound: every game ID crossing to the frontend is a string
  (`id`, `game_id`, `running` entries, event payloads).
- Inbound: every ID is strictly parsed - bools, floats, and
  non-numeric strings are rejected with "Invalid game id", and values
  outside the SQLite 64-bit range are rejected. Digit strings are
  accepted deterministically.
- Frontend code keeps the string form everywhere (selection state,
  React keys, mutation arguments) and never coerces through `Number`.

Quest IDs follow the same rule and are validated as non-empty strings, since
the service compares them against the list the client returned.

## Events

The backend dispatches a `window` CustomEvent named `dcgl` with a
`library_changed` detail whenever library, running, quest, or stats state
changes. The frontend subscribes once (`useDcglEvents`) and invalidates the
library, catalogue, stats, and quest queries. Mutation results (start, stop,
add, remove, repair, quest start) arrive as the direct return value and surface
as a single toast.

Polling is limited to two backstops: stats every 20 s, because a dummy process
can exit on its own and no event reports it, and the quest list every 20 s
while the client is connected.

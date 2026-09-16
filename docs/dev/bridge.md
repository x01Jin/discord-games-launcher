# Bridge Documentation

## Overview

**Module:** `launcher/bridge.py`

The bridge is the only contract between the React frontend and the
Python backend. The frontend calls it as `window.pywebview.api`, and
the backend pushes async updates as `dcgl` CustomEvents. Method
results are plain JSON dicts; failures are returned as error payloads,
never raised.

## Methods

| Method                         | Input          | Returns                                                                                                                                          |
| ------------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `list_games(limit, offset)`    | ints           | `{games, total}` — Windows-executable games only                                                                                                 |
| `search_games(query, limit)`   | string, int    | `{games}` — Windows-executable matches only                                                                                                      |
| `add_to_library(game_id)`      | string ID      | `{ok, message}`                                                                                                                                  |
| `add_many(game_ids)`           | string ID list | `{added, failed, message}` — already-in-library skips and invalid IDs folded into the message/`failed` count                                     |
| `get_library()`                | —              | `{games}` with running flags                                                                                                                     |
| `remove_from_library(game_id)` | string ID      | `{ok, message}`                                                                                                                                  |
| `repair_library()`             | —              | `{ok, message, summary}`                                                                                                                         |
| `start_game(game_id)`          | string ID      | `{ok, message}`; starts immediately, emits `library_changed`                                                                                     |
| `stop_game(game_id)`           | string ID      | `{ok, message}`                                                                                                                                  |
| `stop_all_games()`             | —              | `{stopped}`                                                                                                                                      |
| `get_running()`                | —              | `{running}` — string ID list                                                                                                                     |
| `get_stats()`                  | —              | `{cached_games, library_games, running_processes, executable_history, games_no_win_exes}` (error fallback returns only the first three as zeros) |
| `sync_catalogue()`             | —              | `{synced, count, message}`                                                                                                                       |

`list_games` / `search_games` / `get_library` include an `error` field
when the backend call itself fails; the frontend renders it with a
retry action instead of an empty view.

## ID Contract

Discord game IDs are snowflake-scale integers that JavaScript numbers
cannot represent exactly (`2^53 - 1` limit). To keep IDs lossless:

- **Outbound:** every game ID crossing to the frontend is a string
  (`id`, `game_id`, `running` entries, event payloads).
- **Inbound:** every ID is strictly parsed — bools, floats, and
  non-numeric strings are rejected with "Invalid game id", and values
  outside the SQLite 64-bit range are rejected. Digit strings are
  accepted deterministically.
- Frontend code keeps the string form everywhere (selection state,
  React keys, mutation arguments) and never coerces through `Number`.

## Events

The backend dispatches a `window` CustomEvent named `dcgl` with a
`library_changed` detail whenever library, running, or stats state
changes. The frontend subscribes once (`useDcglEvents`) and
invalidates the matching queries; no polling is needed beyond the
footer's 5-second stats refresh. Mutation results (start, stop,
add, remove, repair) arrive as the direct return value and surface as
a single toast.

# Bridge

`launcher/bridge.py` is the only contract between the React frontend and the
Python backend. The frontend calls it as `window.pywebview.api`; the backend
pushes updates as `dcgl` CustomEvents. Method results are plain JSON dicts, and
failures come back as error payloads rather than exceptions.

pywebview creates `window.pywebview` before it fills in the method table, so the
frontend accessor (`shared/api-client/bridge.ts`) waits for the specific method.
A query fired on first paint then does not call `undefined` and record a failure
that fixes itself on the next poll.

## App

| Method | Input | Returns |
| --- | --- | --- |
| `get_app_info()` | - | `{version, repo_url, release_url}` |
| `check_for_update(force?)` | bool (opt) | `{version, latest, update_available, repo_url, release_url, error}`; cached for one hour |
| `open_project_page(target?)` | `"repo"` or `"latest"` | `{ok, message}`; opens the repository or the latest release in the default browser |

The version comes from `launcher/__init__.py`. `check_for_update` asks GitHub's
latest release endpoint and compares the tag against that version. A failed
check returns the current version with `error` set and `update_available: false`.

## Catalogue and library

| Method | Input | Returns |
| --- | --- | --- |
| `list_games(limit, offset)` | ints | `{games, total}`, Windows-executable games only, filtered and paged in SQL |
| `search_games(query, limit)` | string, int | `{games}` |
| `add_to_library(game_id)` | string ID | `{ok, message}` |
| `add_many(game_ids)` | string ID list | `{added, failed, message}` |
| `get_library()` | - | `{games}` with running flags |
| `remove_from_library(game_id)` | string ID | `{ok, message}` |
| `remove_many(game_ids)` | string ID list | `{removed, failed, message}`; stops and deletes each game, counting misses |
| `repair_library()` | - | `{ok, message, summary}` |
| `start_game(game_id)` | string ID | `{ok, message}`; starts at once, emits `library_changed` |
| `stop_game(game_id)` | string ID | `{ok, message}` |
| `stop_all_games()` | - | `{stopped}` |
| `get_running()` | - | `{running}`, a string ID list |
| `get_stats()` | - | `{cached_games, library_games, running_processes, executable_history, games_no_win_exes}` |
| `sync_catalogue()` | - | `{synced, count, skipped, message}` |

`list_games` caps `limit` at 500 and reports `total` as the number of
Windows-playable games, so "showing X of Y" matches what can be added.
`get_stats` is memoised for three seconds in the database layer.

## Quests

Read from the running Discord client, never from the REST API. Details in
[Quests](./quests.md).

| Method | Input | Returns |
| --- | --- | --- |
| `discord_status()` | - | `{installed, running, connected, channel, version, debug_port, silent, silent_wanted, silent_port, hint, error}` |
| `get_quests(force?)` | bool (opt) | `{connected, quests, status, error, account, suspended_until, total_quests}` |
| `connect_discord()` | - | `{ok, message}`; patches the launch entries, then restarts Discord with the endpoint (starts it when closed) |
| `start_discord()` | - | `{ok, message}`; patches the launch entries, then starts Discord with the endpoint; never restarts a running one |
| `open_quest_in_discord(quest_id)` | string | `{ok, message}` |
| `start_quest(quest_id)` | string ID | `{ok, message}`; accepts the quest when needed, then starts a heartbeat run, or queues it behind an active play run |
| `stop_quest(quest_id)` | string ID | `{ok, message}`; ends the play run or the video wait, with no library effect |
| `accept_quest(quest_id)` | string ID | `{ok, message}`; enrolls through the running client |
| `claim_quest_reward(quest_id)` | string ID | `{ok, message, needs_user_action, claimed_in_client}`; a refusal opens Discord's quest page, presses that quest's Claim button when it finds it, and brings the window forward |
| `start_quest_queue(quest_ids?)` | string ID list (opt) | `{ok, message}`; queues unfinished play and video quests, accepting them first |
| `clear_quest_queue()` | - | `{ok, cleared}`; empties both lanes and stops waiting on a video |
| `skip_quest_watch()` | - | `{ok, message}`; stops waiting for the video and starts the next queued one |
| `reorder_quest_queue(quest_ids?)` | string ID list | `{ok, message}`; puts the pending ids in that order |
| `remove_from_quest_queue(quest_id)` | string ID | `{ok, message}` |
| `get_quest_prefs()` | - | `{ok, prefs}`, where prefs is `{play_session_tail_min, run_mode, test_mode}` |
| `set_quest_prefs(values)` | object | `{ok, prefs, message}`; merges known keys and clamps the tail to 0..30 |
| `silent_mode_status()` | - | `{port, enabled, wanted, patched, total, launchers}` |
| `enable_silent_mode()` | - | `{ok, message, updated, failed}`; writes the switch into the Run key and every Discord shortcut |
| `disable_silent_mode()` | - | `{ok, message, restored, failed, restarted}`; restores the original arguments, clears the marker, and restarts a running Discord without the endpoint |

`get_quests` never raises. A missing client, a missing DevTools endpoint, or a
timed-out read all come back as `{connected: false, error}` so the view can show
the reason. A successful read also carries `orbs` (integer or null), `prefs`,
and `queue` (`{ids, active, watching}`), so one query covers the header, the
options panel, and the queue bar.

Each quest carries `kind` (`play`, `watch`, `watch_mobile`), `enrolled`,
`claimed`, `claimable`, `queued`, an `action` (`run`, `stop`, `open`, `claim`,
`done`, `unsupported`), and a reward object with the orb counts and labels.

`start_discord` and `connect_discord` write the launch patch before they touch
Discord, so "Patch and run" and "Patch and restart" are one call each. The
client's own `start()` and `restart()` never patch: they pass the switch on that
launch only.

`start_quest` refuses a watch quest by name and accepts an unaccepted play quest
before starting it, so the UI and the backend cannot disagree about what is
runnable. A second play quest started while one runs is queued, not run in
parallel. `start_quest_queue` applies the same rule: play rows in `run` and video
rows in `open` are accepted, the rest are skipped, and the message names both
counts. Play and video quests run in separate lanes, so a video does not delay a
play run. `stop_quest` on the id in `queue.watching` ends the watch.

`silent_mode_status()` never raises either: a machine where the shortcuts cannot
be read comes back as `{enabled: false, launchers: [], error}`, and the panel
falls back to the restart wording. The three silent-mode methods invalidate the
quest service, so a Connect right after enabling does not read a status cached
before the switch existed.

`list_games`, `search_games`, `get_library`, and `get_quests` include an `error`
field when the backend call fails; the frontend renders it with a retry action
instead of an empty view.

## ID contract

Discord game IDs are snowflake-scale integers that JavaScript numbers cannot
represent exactly (the `2^53 - 1` limit), so:

- Outbound: every game ID crossing to the frontend is a string (`id`,
  `game_id`, `running` entries, event payloads).
- Inbound: every ID is strictly parsed. Bools, floats, and non-numeric strings
  are rejected with "Invalid game id", and values outside the SQLite 64-bit
  range are rejected.
- Frontend code keeps the string form everywhere (selection state, React keys,
  mutation arguments) and never coerces through `Number`.

Quest IDs follow the same rule and are validated as non-empty strings, since the
service compares them against the list the client returned.

## Events

The backend dispatches a `window` CustomEvent named `dcgl` with a
`library_changed` detail whenever library, running, quest, or stats state
changes, and a `quests_changed` detail when a quest run starts or finishes
(`QuestService.on_change`). The frontend subscribes once (`useDcglEvents`) and
invalidates the library, catalogue, stats, and quest queries. Mutation results
arrive as the direct return value and surface as a single toast.

A third detail, `quest_progress`, carries `{quest_id, credited, target, kind}`
at most once a second while a run is in flight (`QuestService.on_progress`,
filled by the monitor from the last credited beat). `useDcglEvents` patches that
one row in the quest cache instead of refetching, which is what makes the bar
move while the run is credited rather than once per list read.

Polling is limited to two backstops: stats every 20 s, because a dummy process
can exit on its own and no event reports it, and the quest list every 60 s while
the client is connected, for changes no event describes (a quest appearing, the
client refreshing its own list).

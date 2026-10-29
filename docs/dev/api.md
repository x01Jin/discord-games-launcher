# API

`DiscordAPIClient` in `launcher/api.py` talks to Discord's applications API for
the detectable game list and downloads game icons.

```python
DISCORD_API_BASE = "https://discord.com/api"
STABLE_API_VERSION = "v10"
API_VERSION_CANDIDATES = ("v10",)
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"
```

`applications/detectable` returns every application Discord can show as
"Playing". The client fetches 20,000+ records, keeps the Windows-executable
ones, and caches the set in SQLite for seven days.

## Version policy

v10 is the latest stable REST version. Candidates are ordered latest first:
prepend a newer version when Discord ships one and syncs start trying it
automatically, cascading down to the stable default. The last working version is
remembered (`last_working_api_version` in `cache_metadata`) and tried first next
time; other candidates are probed with a 10-second timeout so a dead version
fails fast.

`sync_cache()` returns `(was_synced, game_count, skipped_records)`. Malformed
records are skipped and counted, so one bad record cannot kill a 20,000-game
sync. Payloads missing `executables` across most records trigger a drift warning
in the logs, because the endpoint is undocumented and upstream shape changes are
the main risk.

## Using the client

```python
client = DiscordAPIClient(database, cache_dir, timeout=30.0, logger=None)
```

- `database` holds the cache.
- `cache_dir` holds downloaded icons under `icons/`.
- `timeout` bounds one HTTP request (default 30 s).

| Method | Behavior |
| --- | --- |
| `sync_cache(force=False)` | `(was_synced, game_count, skipped_records)`; `force` syncs even when the cache is fresh |
| `get_icon_url(game_id, icon_hash, size=128)` | CDN URL for one icon |
| `download_icon(game_id, icon_hash, size=128)` | Saves `icons/{game_id}_{icon_hash}_{size}.png`, returns the path or None |
| `get_best_win32_executables(executables)` | Static; Windows executables sorted best first |
| `normalize_process_name(name)` | Static; strips any directory path |

The frontend loads icons straight from the CDN (default size 64, see
`frontend/src/shared/api-client/icons.ts`) and caches nothing locally. The
backend icon cache (default size 128) exists for other consumers and is pruned
of uncached games during library repair.

Raises `DiscordAPIError` when a request fails: connection problems, rate
limiting, an invalid response, or a timeout.

```python
from launcher.api import DiscordAPIClient, DiscordAPIError

try:
    was_synced, count, skipped = client.sync_cache(force=False)
except DiscordAPIError as e:
    print(f"Sync failed: {e}")
```

## Executable selection

Discord matches process names strictly, and a launcher executable may not be
detected at all, so each candidate is scored:

- Not a launcher: +1000. Discord ignores launchers.
- Shorter name: -10 per character.
- No path separator: +50 (avoid `_retail_/bg3.exe`).
- No `_` prefix: +20 (avoid `_wow.exe`).

```python
executables = [
    {"name": "_launcher.exe", "os": "win32", "is_launcher": True},
    {"name": "_retail_/wow-64.exe", "os": "win32", "is_launcher": False},
    {"name": "wow.exe", "os": "win32", "is_launcher": False},
]
```

An executable entry without a `name` falls back to the basename of its first
argument. `normalize_process_name()` keeps only the filename
(`_retail_/wow-64.exe` becomes `wow-64.exe`), while the full path is preserved
on disk so the copied dummy keeps the relative layout Discord expects.

## Payload shape

```json
{
  "id": "356869127241072640",
  "name": "Minecraft",
  "aliases": ["Minecraft"],
  "executables": [
    {"is_launcher": false, "name": "java.exe", "os": "win32"}
  ],
  "icon_hash": "a0c9d2c4e6f8g0h2i4j6k8l0m2n4o6p8q0r2s4t6u8v0w2x4",
  "themes": ["action", "fps", "multiplayer"],
  "isPublished": true
}
```

`id` is a snowflake-scale integer stored as INTEGER and serialized as a string
on the bridge. `aliases`, `executables`, and `themes` are JSON arrays in the
database.

## Async methods

`_fetch_all_games_async()` and `download_icon_async()` mirror the sync versions.
Nothing in the app calls them yet.

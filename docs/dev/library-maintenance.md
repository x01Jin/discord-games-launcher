# Library Maintenance

## Overview

The library is the join of database rows (`user_library`) and files on
disk (`games/<game_id>/`). Crashes, upgrades, antivirus quarantine, and
changing Discord data can leave the two out of sync. Three cooperating
mechanisms keep them converged: boot repair, candidate refresh, and
schema migration. All of them are best-effort (log and count, never
raise) and never touch live processes.

## On-Disk Layout

```structure
%LOCALAPPDATA%\discord-games-launcher\
├── launcher.db            # games_cache, user_library, history, runtime
├── cache\icons\           # <game_id>_<hash>_<size>.png
└── games\
    └── <game_id>\         # dummy executables (subdirs preserved)
```

A library entry is healthy when its row exists, its `executable_path`
file exists, and its stored executable candidates match the cache.

## Boot and On-Demand Repair

`GameManager.repair_library()` runs the full pass and returns summary
counts. It runs automatically at startup (with runtime reset) and on
demand via the bridge `repair_library()` endpoint plus the Repair
button in the library toolbar (with a permanent-deletion warning).

Steps, in order:

1. **Runtime reset (boot only).** Previous-run `running_processes`
   rows are dropped without touching OS processes (PIDs may be
   recycled). On-demand repair skips this so live games keep tracking.
2. **Dangling purge.** Library rows whose game left the cache are
   invisible in the UI (the library query joins the cache) and block
   re-adding, so they are removed with their directories. Skipped when
   the cache is empty (fresh install) or the game has a live process.
   A failed row delete keeps the row scheduled for the later steps.
3. **Orphan sweep.** Directories under `games/` without a library entry
   are deleted, as are stray executables sitting directly under
   `games/` (valid exes live under `<game_id>/`). A root `DummyGame.exe`
   is kept only when it is the resolved template.
4. **Executable recreation.** Every remaining library entry must have
   its file on disk; missing ones are recreated from stored candidates
   and the row is updated to the recreated path, so a second repair is
   a no-op.
5. **Icon prune.** Icons for games no longer cached are deleted.

## Candidate Refresh

`refresh_library_candidates()` reconciles stored executables with
Discord's current data:

- Rewrites the stored candidate blob when the order or set changed.
- When the best executable changed, materializes the new dummy, points
  the row at it, drops the superseded file, and prunes newly empty
  parent directories.
- Skips games with live processes and games with no Windows
  executables left in the cache (both reported in the summary).

Refresh runs after every successful catalogue sync and inside repair,
with one policy difference: the silent sync path updates rows and
materializes new files but never deletes — file deletion happens on
explicit repair only.

## Schema Migration

Opening an older database upgrades it in place: missing columns are
added with `ALTER TABLE` and rows are preserved. Migrated rows with
empty candidate blobs converge on the next refresh. Only an
unrecognized newer schema falls back to recreating the database.

## Running-Game Guards

Live processes are detected through PID verification (exact path
segments, immune to PID recycling). Dangling purges, candidate
replacement, and file deletion all skip running games; on-demand repair
never resets runtime tracking.

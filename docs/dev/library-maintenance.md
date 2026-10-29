# Library maintenance

The library joins database rows in `user_library` with files under
`games/<game_id>/`. Crashes, upgrades, antivirus quarantine, and changing
Discord data can leave the two out of sync. Repair, candidate refresh, and
schema migration keep them converged; all of them are best effort (log and
count, never raise) and never touch live processes.

The code lives in `launcher/library_maintenance.py` and reaches `GameManager`
as `MaintenanceMixin`.

```structure
%LOCALAPPDATA%\discord-games-launcher\
├── launcher.db            # games_cache, user_library, history, runtime
├── cache\icons\           # <game_id>_<hash>_<size>.png
└── games\
    └── <game_id>\         # dummy executables (subdirs preserved)
```

An entry is healthy when its row exists, its `executable_path` file exists, and
its stored candidates match the cache.

## Repair

`repair_library()` returns summary counts. It runs at startup with a runtime
reset, and on demand from the bridge `repair_library()` and the Library
toolbar, behind a permanent-deletion warning. Steps, in order:

1. Runtime reset, boot only: previous-run `running_processes` rows are dropped
   without touching OS processes, since PIDs may be recycled. On-demand repair
   skips this so live games keep tracking.
2. Dangling purge: rows whose game left the cache are invisible in the UI and
   block re-adding, so they are removed with their directories. Skipped when
   the cache is empty (fresh install) or the game has a live process; a failed
   row delete keeps the row for the later steps.
3. Orphan sweep: directories without a library row are deleted, as are stray
   executables sitting directly under `games/` (valid ones live under
   `<game_id>/`). A root `DummyGame.exe` is kept only when it is the resolved
   template.
4. Executable recreation: every remaining entry gets its file back from stored
   candidates, and the row is updated to the recreated path, so a second repair
   is a no-op.
5. Icon prune: icons for games no longer cached are deleted.

## Candidate refresh

`refresh_library_candidates()` rewrites the stored candidate blob when the order
or set changed. When the best executable changed, it materializes the new dummy,
points the row at it, drops the superseded file, and prunes newly empty parent
directories. Games with live processes and games with no Windows executables
left in the cache are skipped, and both are reported in the summary.

Refresh runs after every successful catalogue sync and inside repair, with one
policy difference: the silent sync path updates rows and materializes new files
but never deletes. File deletion happens on explicit repair only.

## Schema migration

Opening an older database upgrades it in place: missing columns are added with
`ALTER TABLE` and rows are preserved. Rows with empty candidate blobs converge
on the next refresh. Only an unrecognized newer schema falls back to recreating
the database.

## Running-game guards

Live processes are detected through PID verification (exact path segments,
immune to PID recycling). Dangling purges, candidate replacement, and file
deletion all skip running games, and on-demand repair never resets runtime
tracking.

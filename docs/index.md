# Documentation

Discord Games Launcher is a Windows app that runs a dummy process under a name
Discord compares against, which makes Discord show that game as playing. It
also reads the quest list from the running Discord client and starts the game a
quest asks for.

## Start here

- [Installation](./user/installation.md) and [Getting started](./user/getting-started.md)
- [Features](./user/features.md), [Troubleshooting](./user/troubleshooting.md)

## Developer docs

- [Architecture](./dev/architecture.md): how the pieces fit, request flow, events
- [Quests](./dev/quests.md): reading the running client, mapping quests to executables, silent setup
- [API](./dev/api.md): the Discord catalogue client
- [Database](./dev/database.md): schema, migrations, queries
- [UI](./dev/ui.md): pages, components, theme, performance rules
- [Bridge](./dev/bridge.md): the pywebview contract
- [Library maintenance](./dev/library-maintenance.md): repair, candidate refresh, schema migration
- [Testing](./dev/testing.md): how to run the suite and what it covers
- [Logging](./dev/logging.md): log files and rotation
- [Build](./dev/build.md): packaging `dcgl.exe`

## Stack

Python 3.14 and pywebview for the window, React 19 with Vite and Tailwind 4 for
the interface, SQLite for storage, httpx for the catalogue, psutil for process
control, and a small hand-written CDP client for reading Discord.

## Layout

```structure
discord-games-launcher/
├── docs/               # This documentation
├── launcher/           # Backend modules
│   ├── api.py         # Discord catalogue client
│   ├── bridge.py      # pywebview frontend contract
│   ├── database.py    # SQLite storage and migrations
│   ├── discord_native.py   # Running Discord client access (CDP)
│   ├── discord_setup.py    # Endpoint flag in Discord's launch entries
│   ├── dummy_generator.py  # Dummy executable generation
│   ├── game_manager.py     # Game operations and repair
│   ├── logger.py           # Logging setup
│   ├── prefs.py            # Quest options stored in settings.json
│   ├── process_manager.py  # Process lifecycle and detection
│   └── quests.py           # Quest list, executable mapping, run and stop
├── frontend/          # React UI
│   └── src/
│       ├── modules/   # quests, catalogue, library, settings
│       └── shared/    # api-client, components, hooks, store, lib
├── frontend-dist/     # Built frontend, served by pywebview
├── templates/         # PyInstaller templates
├── tests/             # Test suite
└── main.py            # Entry point
```

_Last updated: 2026-10-29_

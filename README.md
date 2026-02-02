# Discord Games Launcher

A Windows application that creates dummy executables to trigger Discord's game detection. Browse Discord's supported games database, add them to your library, and launch dummy processes that make Discord display "Playing [Game]".

## What It Does

Discord automatically detects running games by scanning process names. This launcher:

1. Fetches Discord's official supported games database (3,000+ games)
2. Lets you browse and search all supported games
3. Generates lightweight dummy executables with matching process names
4. Runs them in the background so Discord shows your status

**Use Cases:**

- Streamers maintaining consistent "Playing" status during setup/breaks
- Testing Discord integrations without launching full games
- Managing your Discord activity presence

## Features

### Browse Games

- Search Discord's complete supported games database
- Filter by name and aliases
- View game details: executables, themes, publishers
- Add games to your personal library

### Library Management

- Personal game collection with persistent storage
- One-click dummy generation and launch
- Run multiple games simultaneously
- Remove games to clean up generated files

### Discord Detection

Discord scans running processes every ~15 seconds. When it sees `overwatch.exe`, it displays "Playing Overwatch 2" using the game ID and assets from its database.

## Download

**Download the latest from [GitHub Releases](../../releases)**

No installation required - just download and run!

## Quick Start

1. **Download**: Get `dcgl.exe` from the releases page above
2. **First Launch**: Double-click to run (auto-fetches Discord games database)
3. **Browse Tab**: Search for games, click "Add to Library"
4. **Library Tab**: Click "Start" to run dummy process
5. **Check Discord**: Your status shows "Playing [Game Name]"
6. **Stop**: Click "Stop" or close the launcher

For detailed setup, see the [Download & Setup Guide](docs/user/installation.md)

## Limitations

- **Windows Only**: Discord's detection works differently on macOS/Linux
- **Existing Games Only**: Can only simulate games Discord already recognizes
- **No Rich Presence**: Only basic "Playing" status, not detailed activity info
- **API Risk**: Uses undocumented Discord API (may break, but cached data persists)
- **Anti-Cheat**: Some games use protected process names that can't be mimicked

## Documentation

For detailed documentation, check the **[Documentation Index](docs/index.md)**

## Disclaimer

This tool is for legitimate use cases like testing and content creation. Don't use it to:

- Farm Discord quests/rewards (violates Discord ToS)
- Impersonate games for malicious purposes
- Circumvent game security/anti-cheat systems

## License

MIT - Use responsibly.

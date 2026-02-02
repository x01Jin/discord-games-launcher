# Discord Games Launcher

A Windows application that creates dummy executables with GUI windows to trigger Discord's game detection. Browse Discord's supported games database, add them to your library, and launch dummy processes, making Discord show your "Playing" status.

## What It Does

Discord automatically detects running games by scanning process names. This launcher:

1. Fetches Discord's official supported games database (20,000+ games)
2. Lets you browse and search all supported games
3. Generates dummy executables with matching process names and GUI windows
4. Runs them in background windows so Discord shows your status

## Features

### Browse Games

- **Tree View Display:** Organized view with columns for Game Name, Executables, and Status
- **Real-time Search:** Filter 20000+ games instantly as you type
- **Multi-select:** Add multiple games to your library at once
- **Visual Status:** See which games are already in your library

### Library Management

- **Clean List View:** See all your games with rich formatting and status indicators
- **One-click Control:** Double-click to start/stop games
- **Context Menus:** Right-click for quick actions (Start/Stop/Remove)
- **Proper Cleanup:** Removing a game stops its process and deletes all files completely

### Discord Detection

Discord scans running processes every ~15 seconds. When it sees a matching executable name (e.g., `minecraft.exe`), it displays "Playing minecraft" using the game ID and assets from its database.

## Download

**Download the latest from [GitHub Releases](../../releases)**

No installation required - just download and run!

## Quick Start

1. **Download:** Get `dcgl.exe` from the releases page above
2. **First Launch:** Double-click to run (auto-fetches Discord games database)
3. **Browse Tab:** Search for games, select them, click "Add Selected to Library"
4. **Library Tab:** Double-click a game or right-click and select "Start Game"
5. **Dummy Window:** A small window appears showing "{Game} is running"
6. **Check Discord:** Your status shows "Playing [Game Name]" within 15 seconds
7. **Stop:** Close the dummy window, double-click in library, or click "Stop All"

For detailed setup, see the [Download & Setup Guide](docs/user/installation.md)

## System Requirements

- **OS:** Windows 10/11 (64-bit)
- **Discord:** Desktop app
- **Storage:** 500 MB free storage
- **Network:** Required for initial game database sync

When you stop a game:

1. Launcher finds the process and all its children recursively
2. Gracefully terminates child processes first
3. Then terminates the parent process
4. Dummy window closes automatically
5. Discord removes the status within ~15 seconds

### Cleanup on Removal

When you remove a game from library:

1. Stops the process if running (with recursive termination)
2. Removes the executable file
3. Removes the PID tracking file
4. Removes PyInstaller build artifacts (dist/, build/, .spec)
5. Removes the entire game directory
6. Removes the database entry

## Limitations

- **Windows Only:** Discord's detection works differently on macOS/Linux
- **Existing Games Only:** Can only simulate games Discord already recognizes
- **No Rich Presence:** Only basic "Playing" status, not detailed activity info
- **API Risk:** Uses undocumented Discord API (may break, but cached data persists)
- **Anti-Cheat:** Some games use protected process names that can't be mimicked

## Documentation

For detailed documentation, check the **[Documentation Index](docs/index.md)**

## Technical Details

### Built With

- **PyQt6** - Modern GUI framework with dark theme
- **httpx** - Async HTTP client for Discord API
- **PyInstaller** - Compiles dummy scripts to executables
- **psutil** - Process management and termination
- **SQLite** - Local database for caching and library

## Disclaimer

This tool is for educational purpose only. Don't use it to:

- Farm Discord quests/rewards (violates Discord ToS)
- Impersonate games for malicious purposes
- Circumvent game security/anti-cheat systems

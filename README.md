# Discord Games Launcher

A Windows application that creates dummy executables with GUI windows to trigger Discord's game detection. Browse Discord's supported games database, add them to your library, and launch dummy processes that display "{Game Name} is running" in a small window, making Discord show your "Playing" status.

## What It Does

Discord automatically detects running games by scanning process names. This launcher:

1. Fetches Discord's official supported games database (3,000+ games)
2. Lets you browse and search all supported games in a clean tree view
3. Generates dummy executables with matching process names and GUI windows
4. Runs them in background windows so Discord shows your status

**Use Cases:**

- Streamers maintaining consistent "Playing" status during setup/breaks
- Testing Discord integrations without launching full games
- Managing your Discord activity presence

## Features

### Browse Games

- **Tree View Display:** Organized view with columns for Game Name, Executables, and Status
- **Real-time Search:** Filter 3000+ games instantly as you type
- **Multi-select:** Add multiple games to your library at once
- **Visual Status:** See which games are already in your library

### Library Management

- **Clean List View:** See all your games with rich formatting and status indicators
- **One-click Control:** Double-click to start/stop games
- **Context Menus:** Right-click for quick actions (Start/Stop/Remove)
- **Visual Feedback:** Green "Running" or gray "Stopped" indicators
- **Proper Cleanup:** Removing a game stops its process and deletes all files completely

### Discord Detection

Discord scans running processes every ~15 seconds. When it sees a matching executable name (e.g., `overwatch.exe`), it displays "Playing Overwatch 2" using the game ID and assets from its database.

**Key Improvements:**

- **GUI Windows:** Each dummy displays "{Game Name} is running" in a small window
- **Process Names:** Exact matching to Discord's database (handles paths like `_retail_/wow.exe`)
- **Proper Termination:** Stopping a game kills all child processes recursively
- **Complete Cleanup:** Removing a game stops processes and removes all files/folders

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
- **Storage:** ~50 MB for launcher + ~2 MB per game
- **Network:** Required for initial game database sync

## How It Works

### Dummy Executables

When you add a game to your library, the launcher:

1. Finds the Windows executable name from Discord's database
2. Generates a Python script with tkinter GUI showing "{Game} is running"
3. Compiles it with PyInstaller to create the executable
4. Names it exactly as Discord expects (e.g., `overwatch.exe`)
5. Stores it in your user data directory

### Process Management

When you start a game:

1. Launcher runs the dummy executable
2. A small window opens showing game name and "is running" status
3. Process name matches Discord's detection list
4. Discord detects it within ~15 seconds
5. Your status updates to "Playing [Game Name]"

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

Key documents:

- [Installation Guide](docs/user/installation.md)
- [Getting Started](docs/user/getting-started.md)
- [Features](docs/user/features.md)
- [Troubleshooting](docs/user/troubleshooting.md)
- [Architecture](docs/dev/architecture.md)
- [UI Documentation](docs/dev/ui.md)

## Technical Details

### Built With

- **PyQt6** - Modern GUI framework with dark theme
- **httpx** - Async HTTP client for Discord API
- **PyInstaller** - Compiles dummy scripts to executables
- **psutil** - Process management and termination
- **tkinter** - GUI for dummy executables
- **SQLite** - Local database for caching and library

### Architecture

```structure
UI (PyQt6)
├── Browser Tab (QTreeWidget) - Browse/search games
└── Library Tab (QListWidget) - Manage library

Backend
├── Game Manager - High-level coordination
├── API Client - Discord API communication
├── Database - SQLite storage
├── Dummy Generator - PyInstaller + tkinter GUI
└── Process Manager - psutil with recursive termination
```

### Process Termination

Proper cleanup uses recursive process termination:

```python
# 1. Find all child processes
children = parent.children(recursive=True)

# 2. Terminate children gracefully
for child in children:
    child.terminate()

# 3. Wait for termination
psutil.wait_procs(children, timeout=3)

# 4. Force kill if needed
for child in alive:
    child.kill()

# 5. Terminate parent
parent.terminate()
```

## Disclaimer

This tool is for legitimate use cases like testing and content creation. Don't use it to:

- Farm Discord quests/rewards (violates Discord ToS)
- Impersonate games for malicious purposes
- Circumvent game security/anti-cheat systems

## License

MIT - Use responsibly.

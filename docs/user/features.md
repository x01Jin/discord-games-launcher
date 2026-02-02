# Features

## Overview

Discord Games Launcher provides a complete solution for managing your Discord "Playing" status with support for 3000+ games.

## Core Features

### 1. Game Database Browser

Browse and search Discord's official supported games database.

**Features:**

- Real-time search across 3000+ games
- Instant filtering as you type
- Shows game aliases (alternative names)
- Displays Windows executables
- Grid layout with game cards

**Usage:**

1. Go to "Browse Games" tab
2. Type in the search box
3. Results filter instantly
4. Clear search to see all games

### 2. Personal Game Library

Create your own collection of games to manage.

**Features:**

- Add unlimited games to library
- One-click add from browser
- Persistent storage (survives app restarts)
- Shows game status (Running/Stopped)

**How it works:**
When you add a game, the launcher:

1. Finds the Windows executable name from Discord's database
2. Generates a dummy executable using PyInstaller
3. Stores it in your user data directory
4. Adds to your library database

### 3. Discord Status Control

Show "Playing [Game]" in Discord with dummy processes.

**Features:**

- Start/Stop games individually
- Run multiple games simultaneously
- Status updates in real-time
- "Stop All" button for quick cleanup

**Discord Detection:**
Discord detects running processes by their executable name. The launcher creates processes with the exact names Discord expects (e.g., `overwatch.exe`, `minecraft.exe`).

### 4. Automatic Caching

Smart caching system for optimal performance.

**Features:**

- Automatic sync on first launch
- Weekly auto-refresh (configurable)
- Manual sync button
- Persisted across sessions

**Cache Details:**

- 7-day TTL by default
- Stores in SQLite database
- ~5-10 seconds initial download
- Background updates don't interrupt usage

### 5. Dark Theme Interface

Modern, eye-friendly dark interface.

**Features:**

- Visual Studio Code inspired theme
- Consistent dark colors throughout
- Blue accent color (#007acc)
- Smooth hover effects
- Professional appearance

**Colors:**

- Background: #1e1e1e (dark gray)
- Cards: #252526 (slightly lighter)
- Accent: #007acc (blue)
- Text: #cccccc (light gray)
- Success: #4ec9b0 (green)
- Error: #f44336 (red)

### 6. Process Management

Robust process lifecycle management.

**Features:**

- PID tracking in database
- Automatic cleanup on exit
- Graceful process termination
- Stale process detection
- Status verification every 5 seconds

**Safety:**

- Processes run without console windows
- Minimal CPU usage (sleep loops)
- Force kill if graceful termination fails
- All processes stopped on app exit

### 7. Statistics and Monitoring

Track your launcher usage.

**Features:**

- Live status bar stats
- Detailed statistics dialog
- Cache information
- Running process count
- Library size tracking

**Stats Include:**

- Total cached games (from Discord)
- Games in your library
- Currently running processes
- Last sync timestamp

## Advanced Features

### Icon Caching

Game icons are downloaded and cached locally.

**Features:**

- Automatic download on demand
- 128x128 default size
- Local cache for offline use
- PNG format

**Location:** `%LOCALAPPDATA%\discord-games-launcher\cache\icons\`

### Multi-Platform Support (Code)

While designed for Windows, the codebase supports multi-platform.

**Features:**

- Cross-platform path handling (platformdirs)
- OS detection for executables
- Future macOS/Linux potential

### Error Handling

Comprehensive error handling throughout.

**Features:**

- Network error recovery
- Database error handling
- Process management errors
- User-friendly error messages

### High DPI Support

Crisp display on high-resolution monitors.

**Features:**

- Automatic DPI scaling
- Qt6 HiDPI support
- Windows scaling compatibility

## Technical Specifications

### Performance

- **Memory:** ~50-100 MB RAM for launcher
- **CPU:** Minimal usage (idle waiting)
- **Storage:** ~50 MB for database, ~1-2 MB per dummy executable
- **Network:** ~1 MB download on first sync

### Compatibility

- **OS:** Windows 10/11 (64-bit)
- **Python:** 3.13.11+
- **Discord:** Desktop app required
- **Permissions:** User-level (no admin required)

### Scalability

- **Games:** 3000+ in database
- **Library:** Unlimited (tested with 100+)
- **Concurrent:** Multiple games can run simultaneously

## Feature Comparison

| Feature | Discord Games Launcher | Manual Method |
| --------- | ---------------------- | --------------- |
| Game Database | 3000+ games | Must find manually |
| Search | Instant | N/A |
| Library Management | Built-in | Manual tracking |
| Start/Stop | One click | Task Manager |
| Multiple Games | Yes | Tedious |
| Dark Theme | Yes | N/A |
| Auto-sync | Weekly | Manual updates |
| Status Persistence | Database | N/A |

## Roadmap

### Planned Features

- [ ] Game categories/folders in library
- [ ] Favorite games list
- [ ] Recently played tracking
- [ ] Custom game support (add unsupported games)
- [ ] Icon display in game cards
- [ ] Library import/export
- [ ] Keyboard shortcuts
- [ ] System tray minimization
- [ ] Auto-start with Windows
- [ ] Play time tracking

### Under Consideration

- [ ] Game launching (start real games)
- [ ] Rich presence customization
- [ ] Friend activity feed
- [ ] Achievement display
- [ ] Game recommendations

## Tips for Best Experience

### Organization

- Keep 10-20 frequently played games in library
- Remove games you don't play anymore
- Use search to quickly find games

### Discord Integration

- Keep Discord running while using launcher
- Status may take 5-10 seconds to appear
- Some games appear faster than others
- Discord mobile shows same status

### Maintenance

- Sync games weekly for latest database
- Clear unused games periodically
- Check for launcher updates

## Limitations

### Current Limitations

1. **Windows Only:** Currently Windows 10/11 only
2. **Discord Desktop:** Requires Discord desktop app (not web)
3. **Game Detection:** Only works with Discord-supported games
4. **No Rich Presence:** Shows basic "Playing" status only
5. **No Game Launch:** Doesn't launch actual games

### Workarounds

- **Unsupported games:** Use similar game names (e.g., use "Steam" for unsupported Steam games)
- **Web Discord:** Use desktop app for status to appear
- **Rich Presence:** Use game's official Discord integration if available

## Getting Help

For feature requests or issues:

1. Check [Troubleshooting](./troubleshooting.md)
2. Search existing GitHub issues
3. File a new issue with feature request template
4. Join community Discord (link in README)

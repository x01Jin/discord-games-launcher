# Features

## Overview

Discord Games Launcher provides a complete solution for managing your Discord "Playing" status with support for 3000+ games. Features proper list views, GUI windows for running games, and robust process management.

## Core Features

### 1. Game Database Browser (QTreeWidget)

Browse and search Discord's official supported games database in an organized tree view.

**Features:**

- **Tree View Display:** Three columns showing Game Name, Executables, and Status
- **Real-time Search:** Instant filtering as you type across 3000+ games
- **Multi-select Support:** Add multiple games at once with Ctrl+Click or Shift+Click
- **Visual Indicators:** Green "In Library" status for games you've already added
- **Detailed Information:** Shows game aliases and available Windows executables

**Usage:**

1. Go to "Browse Games" tab
2. Type in the search box to filter results
3. Select one or more games (Ctrl+Click for multiple)
4. Click "Add Selected to Library"
5. Right-click any game for quick add option

### 2. Personal Game Library (QListWidget)

Manage your game collection in a clean, scannable list view with rich formatting.

**Features:**

- **Rich List Items:** HTML-formatted display showing game name, process name, and status
- **Visual Status:** Green "Running" or gray "Stopped" indicators
- **Quick Actions:** Double-click to toggle start/stop
- **Context Menus:** Right-click for Start/Stop/Remove options
- **Persistent Storage:** Library survives app restarts
- **Stop All Button:** Quickly stop all running games

**Interactions:**

- **Double-click:** Toggle start/stop a game
- **Right-click:** Open context menu with actions
- **Visual Feedback:** Status updates every 5 seconds

**How it works:**

When you add a game:

1. Finds the Windows executable name from Discord's database
2. Generates a Python script with tkinter GUI window
3. Compiles with PyInstaller to create the executable
4. Names it exactly as Discord expects (handles paths like `_retail_/wow.exe`)
5. Stores in your user data directory

When you start a game:

1. Launcher runs the dummy executable
2. A small window opens showing "{Game Name} is running"
3. Process stays active with the GUI window open
4. Discord detects it within ~15 seconds
5. Your status updates to "Playing [Game Name]"

### 3. Discord Status Control with GUI Windows

Show "Playing [Game]" in Discord with dummy processes that display GUI windows.

**Features:**

- **GUI Windows:** Each running game shows a small window with game name
- **Start/Stop Control:** Individual control over each game
- **Multiple Games:** Run multiple games simultaneously
- **Proper Termination:** Recursive child process killing for complete cleanup
- **Real-time Updates:** Status bar shows running count

**Discord Detection:**

Discord detects running processes by their executable name. The launcher:

- Creates processes with exact names Discord expects (e.g., `overwatch.exe`)
- Handles path prefixes (e.g., `_retail_/wow-64.exe` → `wow-64.exe`)
- GUI window keeps process active and alive
- Discord scans every ~15 seconds for process changes

### 4. Robust Process Management

Advanced process lifecycle management with proper cleanup.

**Features:**

- **PID Tracking:** Tracks process IDs in database for persistence
- **Recursive Termination:** Kills child processes before parent process
- **Graceful Shutdown:** Attempts graceful termination before force kill
- **Stale Detection:** Automatically cleans up dead process records
- **Force Cleanup:** Stops all processes on app exit

**Process Termination Process:**

```list
1. Find all child processes recursively
2. Send terminate signal to all children
3. Wait up to 3 seconds for children to exit
4. Force kill any remaining children
5. Send terminate signal to parent
6. Wait up to 3 seconds for parent to exit
7. Force kill parent if still running
```

**Benefits:**

- No zombie processes left behind
- Clean system state after stopping games
- Handles PyInstaller child processes properly
- Complete cleanup guaranteed

### 5. Complete Cleanup on Removal

Removing a game from library performs complete cleanup.

**Cleanup Actions:**

1. **Stop Process:** If running, stops with recursive termination
2. **Remove Executable:** Deletes the .exe file
3. **Remove PID File:** Cleans up tracking file
4. **Remove Build Artifacts:** Deletes dist/, build/, .spec files
5. **Remove Directory:** Removes entire game directory
6. **Database Cleanup:** Removes library entry

**Result:** Zero leftover files or processes.

### 6. Automatic Caching

Smart caching system for optimal performance.

**Features:**

- Automatic sync on first launch
- Weekly auto-refresh (7-day TTL, configurable)
- Manual sync button
- Persisted across sessions
- Works offline with cached data

**Cache Details:**

- Stores in SQLite database (~5-10 MB)
- ~5-10 seconds initial download (3000+ games)
- Background updates don't interrupt usage
- Game icons cached locally

### 7. Dark Theme Interface

Modern, eye-friendly dark interface.

**Features:**

- Visual Studio Code inspired theme
- Consistent dark colors throughout all components
- Blue accent color (#007acc)
- Smooth hover effects on list items
- Professional appearance
- High DPI support

**Color Palette:**

- Background: #1e1e1e (dark gray)
- Lists/Cards: #252526 (slightly lighter)
- Accent: #007acc (blue)
- Text: #cccccc (light gray)
- Success: #4ec9b0 (green)
- Error: #f44336 (red)

### 8. Context Menus and Quick Actions

Right-click context menus for efficient workflow.

**Browser Tab Context Menu:**

- Add to Library (if not already added)
- Quick add without clicking main button

**Library Tab Context Menu:**

- Start Game (if stopped)
- Stop Game (if running)
- Remove from Library (with confirmation)

**Styling:**

Dark theme context menus matching the application style.

## Advanced Features

### Icon Caching

Game icons downloaded and cached locally for offline use.

**Features:**

- Automatic download on demand
- 128x128 default size
- Local cache for offline use
- PNG format

**Location:** `%LOCALAPPDATA%\discord-games-launcher\cache\icons\`

### Process Name Normalization

Handles complex executable paths from Discord's database.

**Examples:**

- `_retail_/wow-64.exe` → `wow-64.exe`
- `bin/win64/game.exe` → `game.exe`
- `game.exe` → `game.exe` (no change)

Ensures exact name matching for Discord detection.

### Multi-Platform Code Support

While designed for Windows, the codebase supports multi-platform.

**Features:**

- Cross-platform path handling (platformdirs)
- OS detection for executables
- Future macOS/Linux potential

### Error Handling

Comprehensive error handling throughout.

**Features:**

- Network error recovery with retry
- Database error handling
- Process management error recovery
- User-friendly error messages
- Graceful degradation

### High DPI Support

Crisp display on high-resolution monitors.

**Features:**

- Automatic DPI scaling enabled
- Qt6 HiDPI support
- Windows scaling compatibility

## Technical Specifications

### Performance

- **Launcher Memory:** ~50-100 MB RAM
- **Launcher CPU:** <1% when idle
- **Dummy Memory:** ~10-20 MB RAM per game (GUI window)
- **Dummy CPU:** Minimal (tkinter event loop)
- **Storage:** ~50 MB for database, ~2 MB per dummy executable
- **Network:** ~1 MB download on first sync

### Compatibility

- **OS:** Windows 10/11 (64-bit)
- **Python:** 3.13.11+
- **Discord:** Desktop app required (not web)
- **Permissions:** User-level (no admin required)

### Scalability

- **Games:** 3000+ in database
- **Library:** Unlimited games (tested with 100+)
- **Concurrent:** Multiple games can run simultaneously

## Feature Comparison

| Feature | Discord Games Launcher | Manual Method |
| --------- | ------------------------ | --------------- |
| Game Database | 3000+ games | Must find manually |
| Search | Instant with tree view | N/A |
| Library View | Clean list with rich formatting | Manual tracking |
| GUI Windows | Yes (shows running status) | N/A |
| Start/Stop | One click or double-click | Task Manager |
| Process Cleanup | Recursive termination | Manual killing |
| Complete Cleanup | Yes (removes all files) | Manual deletion |
| Multiple Games | Yes | Tedious |
| Dark Theme | Yes with proper widgets | N/A |
| Auto-sync | Weekly | Manual updates |
| Status Persistence | Database tracking | N/A |

## Tips for Best Experience

### Organization

- Keep 10-20 frequently played games in library
- Remove games you don't use to keep list clean
- Use search to quickly find games instead of scrolling

### Discord Integration

- Keep Discord running while using launcher
- Status may take 10-15 seconds to appear or disappear
- Some games appear faster than others based on detection priority
- Discord mobile app shows same status

### Performance_

- Each running game uses ~10-20 MB RAM (for GUI window)
- Stop games you're not actively displaying
- Use "Stop All" button for quick cleanup
- Launcher itself uses minimal resources

### Maintenance

- Sync games weekly for latest database updates
- Clear unused games periodically
- Check for launcher updates
- Verify Discord has "Display currently running game" enabled

## Limitations

### Current Limitations

1. **Windows Only:** Currently Windows 10/11 only
2. **Discord Desktop:** Requires Discord desktop app (web version won't work)
3. **Game Detection:** Only works with Discord-supported games
4. **No Rich Presence:** Shows basic "Playing" status only (not detailed info)
5. **No Game Launch:** Doesn't launch actual games

### Workarounds

- **Unsupported games:** Use similar game names
- **Web Discord:** Use desktop app for status
- **Rich Presence:** Use game's official Discord integration

## Getting Help

For feature requests or issues:

1. Check [Troubleshooting](./troubleshooting.md)
2. Search existing GitHub issues
3. File a new issue with feature request template
4. Join community Discord (link in README)

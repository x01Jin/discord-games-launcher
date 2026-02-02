# Download & Setup Guide

## System Requirements

### Minimum Requirements

- **Operating System:** Windows 10/11 (64-bit)
- **RAM:** 4 GB
- **Storage:** 500 MB free space (for database and dummy executables)
- **Internet:** Required for initial game database sync

### Recommended

- **Operating System:** Windows 11
- **RAM:** 8 GB
- **Storage:** 1 GB free space
- **Discord:** Desktop app installed (required for "Playing" status)

## Download

### From GitHub Releases (Recommended)

1. Go to the [GitHub Releases page](../../releases)
2. Download the latest `dcgl.exe`
3. Save it to a folder of your choice (e.g., `C:\Tools\dcgl` or your Desktop)

**Note:** You only need the single `dcgl.exe` file - it contains everything needed to run.

### Prerequisites

### 1. Install Discord Desktop App

Download and install Discord from [discord.com](https://discord.com/download)

**Note:** Discord must be running to see the "Playing" status.

## First Launch

1. Double-click `dcgl.exe` or run it from Command Prompt:

   ```cmd
   dcgl.exe
   ```

2. **What happens on first run:**
   - Creates data directory: `%LOCALAPPDATA%\discord-games-launcher\`
   - Initializes SQLite database
   - Syncs game database from Discord API (3000+ games, ~5-10 seconds)
   - Opens main window with dark theme

## Data Directory Structure

```structure
%LOCALAPPDATA%\discord-games-launcher\
├── launcher.db              # SQLite database
├── cache\
│   └── icons\              # Downloaded game icons
│       ├── 123_icon1_128.png
│       └── 456_icon2_128.png
└── games\                  # Generated dummy executables
    ├── 123\               # Game ID directory
    │   └── game.exe       # Dummy executable
    └── 456\
        └── another.exe
```

## Updating

To update to a new version:

1. Download the latest `dcgl.exe` from GitHub Releases
2. Replace your old `dcgl.exe` with the new one
3. Your library and settings are preserved in the data directory

## Uninstallation

To completely remove:

1. Delete `dcgl.exe`
2. Delete user data directory:

   ```cmd
   rmdir /s "%LOCALAPPDATA%\discord-games-launcher"
   ```

**Warning:** This deletes your library and settings!

## Next Steps

- Read the [Getting Started Guide](./getting-started.md)
- Learn about [Features](./features.md)
- Check [Troubleshooting](./troubleshooting.md) if you encounter issues

## Getting Help

- Check [Troubleshooting](./troubleshooting.md)
- File an issue on GitHub

# Download & Setup Guide

## What You Need

- **Computer:** Windows 10 or 11 (64-bit)
- **Memory:** 4 GB or more (8 GB is nicer)
- **Free space:** 500 MB or more
- **Internet:** needed once at the start to download the game list
- **Discord:** the Discord desktop app must be installed for your "Playing" status to show

## Download

1. Go to the [GitHub Releases page](../../releases)
2. Download the latest `dcgl.exe`
3. Save it anywhere you like (for example your Desktop)

That single file is the whole app — nothing to install.

## First Launch

1. Double-click `dcgl.exe`
2. On first run the app sets up its own storage folder and opens its dark-themed window
3. Press **Sync catalogue** to download the game list (20,000+ games, takes about 5-10 seconds)

Your games and settings live in `%LOCALAPPDATA%\discord-games-launcher\` on your PC.

## Updating

To update:

1. Download the latest `dcgl.exe` from GitHub Releases
2. Replace your old `dcgl.exe` with the new one
3. Your library and settings are kept

## Uninstallation

To remove everything:

1. Delete `dcgl.exe`
2. Delete the app's storage folder by running this in Command Prompt:

   ```cmd
   rmdir /s "%LOCALAPPDATA%\discord-games-launcher"
   ```

**Warning:** this deletes your library and settings!

## Next Steps

- Read the [Getting Started Guide](./getting-started.md)
- Learn about [Features](./features.md)
- Check [Troubleshooting](./troubleshooting.md) if something goes wrong

## Getting Help

- Check [Troubleshooting](./troubleshooting.md)
- File an issue on GitHub

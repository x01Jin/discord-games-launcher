# Download and setup

## Requirements

- Windows 10 or 11, 64-bit
- 4 GB of memory (8 GB is comfortable)
- 500 MB of free disk space
- Internet at least once, for the game list
- The Discord desktop app, for the status to appear

## Download

Get the latest `dcgl.exe` from the [releases page](https://github.com/x01Jin/discord-games-launcher/releases) and put it
wherever you keep programs. That one file is the whole app; there is no
installer.

## First launch

Double-click `dcgl.exe`. It creates its storage folder under
`%LOCALAPPDATA%\discord-games-launcher\` and opens.

Press **Sync catalogue** in the Catalogue toolbar if the game count is still
zero. The download is about 20,000 games and takes a few seconds.

## Updating

Download the newer `dcgl.exe` and replace the old one. Your library and
settings stay where they are.

## Uninstalling

Delete `dcgl.exe`, then remove the storage folder:

```cmd
rmdir /s "%LOCALAPPDATA%\discord-games-launcher"
```

That deletes the library, the game list, and the logs. If you enabled the launch
patch for quests, remove it in Settings first; it lives in your Discord
shortcuts and startup entry, not in this folder.

Next: [Getting started](./getting-started.md), [Features](./features.md),
[Troubleshooting](./troubleshooting.md).

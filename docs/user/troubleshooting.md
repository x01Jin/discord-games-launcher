# Troubleshooting Guide

## Discord Status Not Showing

**Problem:** you started a game but Discord does not show "Playing".

**Good to know:** the launcher cannot check what Discord sees. It opens a game window that Discord should notice — whether Discord picks it up depends on Discord's settings.

**Things to try, in order:**

1. **Make sure Discord is running**
   - Discord must be open and logged in
   - Use the Discord desktop app (the website cannot show game activity)
   - Try running Discord as administrator (right-click its icon → Run as administrator)

2. **Check one Discord setting (most common cause)**
   - Open Discord Settings → Activity Privacy
   - Turn **Display current activity as a status message** ON

3. **Wait a little**
   - Discord looks for games roughly every 15-30 seconds
   - Wait 30-60 seconds after starting a game

4. **Check the game is really running**
   - The launcher should show it as Running
   - In Task Manager, look for the game's process name (shown on its library card)

5. **Restart Discord**
   - Close Discord fully (right-click its tray icon → Quit)
   - Open it again, wait until it finishes loading, and check your status

6. **Try a different game**
   - Popular games (Minecraft, VALORANT, League of Legends) are usually noticed quickly
   - Test with one of those first

**If it still does not show:**

- The game might not be one Discord recognizes
- Your security software might be hiding processes from Discord
- Discord might need to run as administrator

## Launcher Won't Start

**Problem:** double-clicking `dcgl.exe` does nothing or shows an error.

**Things to try:**

1. **Restart your PC** and try again
2. **Check your antivirus** — it may be blocking the app. Allow `dcgl.exe` and the folder `%LOCALAPPDATA%\discord-games-launcher\`
3. **Re-download** the latest `dcgl.exe` from GitHub Releases — your copy may be damaged
4. **Check Windows is up to date** — the app needs Windows 10/11 (64-bit)

## Cannot Add a Game to the Library

**Problem:** pressing "Add to Library" shows an error or nothing happens.

**Things to try:**

1. **The game may have no Windows version** — some games are Mac or Linux only, and those cannot be added. Try another game
2. **Check disk space** — you need at least 50 MB free
3. **Check your antivirus** — it may have removed the game's files. Allow the folder `%LOCALAPPDATA%\discord-games-launcher\`, then remove the game from your library and add it again

## Game Won't Start

**Problem:** you try to start a game but it stays Stopped.

**Things to try:**

1. **Press Stop All**, then try starting the game again
2. **Re-add the game** — remove it from your library and add it back, which recreates its files
3. **Check Task Manager** for a stuck copy of the game already running, and end it
4. **Check your antivirus** — it may be deleting the game's files as soon as they are created

## Sync Catalogue Fails

**Problem:** the **Sync catalogue** button fails or takes very long.

**Things to try:**

1. **Check your internet connection**
2. **Try again in 5-10 minutes** — Discord may be temporarily down
3. **Keep using the app** — it works fine with the games it already saved; sync again later
4. **Try another network** — some office or school networks block Discord (try your phone hotspot)

## App Feels Slow or Heavy

Each running game uses about 10-20 MB of memory for its little window. If things feel heavy:

1. Stop games you are not showing — or press **Stop All**
2. The launcher itself should use almost no CPU when idle

Normal usage looks like this:

- Launcher: about 50-100 MB of memory, almost no CPU
- Each running game: about 10-20 MB of memory, almost no CPU

## Same Game Twice in the Library

This should not happen, but if it does: remove the extra copy from your library. If problems persist, do a **Full Reset** (below) and add your games again.

## Antivirus Warnings

Your antivirus may flag the launcher or its game windows. This is a false alarm — each game window only shows the game name and a timer, nothing harmful.

- Allow the folder `%LOCALAPPDATA%\discord-games-launcher\` in your antivirus settings
- All of the app's code is open source, so anyone can inspect it

## Error Messages

### "Game not found in cache"

Press **Sync catalogue** first to download the game list. If it still fails, press **Repair** in the My Library toolbar.

### "Game is already in library"

It is already there — check your **My Library** tab.

### "Game is not in library"

Its saved info is out of date — press **Repair** in the My Library toolbar.

### "No Windows executable found"

That game has no Windows version in Discord's list. Try a different game.

### "Executable not found"

Its files were deleted or moved. Press **Repair** in the My Library toolbar (it recreates missing files), or remove the game and add it again.

### "Failed to start game"

Make sure the game is not already running, then re-add it and check your antivirus.

### "Sync failed"

Check your internet, try again later — the app keeps working with its saved games meanwhile.

## Starting Over

### Full Reset

Erases everything (your library included) and starts fresh:

```cmd
rmdir /s "%LOCALAPPDATA%\discord-games-launcher"
```

Then start the app again — it sets everything up like new.

## Getting More Help

When asking for help, include:

1. **What went wrong** — the exact message or a screenshot
2. **What you did** — the steps before it happened
3. **Your setup** — Windows version and Discord app version
4. **Log file** — from `%LOCALAPPDATA%\discord-games-launcher\logs\` (pick the file with today's date)

**Where to ask:**

1. **GitHub Issues** — file an issue describing the problem
2. **Community Discord** — link in README

**Still stuck?** Don't hesitate to ask — the community is happy to help!

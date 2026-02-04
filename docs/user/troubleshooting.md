# Troubleshooting Guide

## Common Issues and Solutions

### Issue: Discord Status Not Showing

**Problem:** Started a game but Discord doesn't show "Playing" status.

**Important:** The launcher CANNOT verify Discord detection. It only creates a process that Discord should detect. Whether Discord actually detects it depends on Discord's settings and behavior.

**Solutions:**

1. **Check Discord is running**
   - Discord must be open and logged in
   - Use Discord desktop app (web version won't work)
   - Try running Discord as Administrator

2. **Check Discord settings (CRITICAL)**
   - Discord Settings > Activity Privacy
   - Ensure "Display current activity as a status message" is ON
   - This is the most common reason for detection failure

3. **Wait for Discord's scan cycle**
   - Discord scans for processes every 15-30 seconds
   - Wait at least 30-60 seconds after starting a game
   - Status may not appear immediately

4. **Verify process is running**
   - Check launcher shows "Running" status
   - Open Task Manager and look for the process
   - Process name should match the game executable (e.g., `devilmaycry5.exe`)

5. **Restart Discord**
   - Close Discord completely (exit from system tray)
   - Reopen Discord
   - Wait for it to fully load
   - Check if status appears

6. **Try a different game**
   - Some games have better detection than others
   - Popular games (Minecraft, VALORANT, League of Legends) usually work well
   - Test with a known working game first

**Understanding the Detection Process:**

The launcher creates a process with the exact name Discord expects (e.g., `devilmaycry5.exe`). Discord independently scans running processes and matches them against its database. The launcher has no way to verify if Discord detected the game - it can only verify the process is running.

**If Discord still doesn't detect:**

- The game might not be in Discord's detectable games database
- Discord might have bugs with specific games
- Windows security software might be blocking Discord from seeing processes
- Discord might need elevated permissions (run as Administrator)

### Issue: Launcher Won't Start

**Problem:** Running `python main.py` fails or shows errors.

**Solutions:**

1. **Check Python version**

    ```cmd
    python --version
    # Should be 3.13 or higher
    ```

2. **Activate virtual environment**

   ```cmd
   .venv\Scripts\activate
   python main.py
   ```

3. **Reinstall dependencies**

   ```cmd
   pip install -r requirements.txt --force-reinstall
   ```

4. **Check for missing modules**

   ```cmd
   pip list
   # Should show: PyQt6, httpx, platformdirs, pyinstaller, psutil
   ```

**Error Messages:**

- `ModuleNotFoundError`: Install missing package
- `ImportError`: Check Python version (needs 3.13+)
- `Permission denied`: Run as administrator or check antivirus

### Issue: "Add to Library" Fails

**Problem:** Clicking "Add to Library" shows an error or doesn't work.

**Solutions:**

1. **Check game has Windows executable**
   - Some games are macOS/Linux only
   - Game row shows available executables
   - Look for "win32" in the list

2. **Check dummy template is available**
   - The launcher uses a pre-built template for instant game addition
   - Template must be in `templates/dist/DummyGame.exe`
   - If template is missing, games cannot be added

3. **Check disk space**
   - Need at least 50 MB free
   - Each dummy executable is ~2 MB

4. **Check antivirus**
   - Antivirus may flag the template executable as a false positive
   - Add exception for `%LOCALAPPDATA%\discord-games-launcher\` and project directory

-- **Error: "No Windows executable found"** --

- This game doesn't have a Windows version in Discord's database
- Try a different game
- Some indie games may not be supported

### Issue: Games Not Starting

**Problem:** Click "Start" but game shows as "Stopped".

**Solutions:**

1. **Check executable exists**
   - May have been deleted by antivirus
   - Remove and re-add the game
   - Check path: `%LOCALAPPDATA%\discord-games-launcher\games\{game_id}\`

2. **Check process isn't already running**
   - Open Task Manager
   - Look for existing process with same name
   - Kill existing process if found

3. **Try "Stop All" then restart**
   - Click "Stop All" in library tab
   - Try starting the game again

4. **Regenerate executable**
   - Remove game from library
   - Add it back (generates fresh executable)
   - Try starting again

**Check Windows Event Viewer:**

- If executable crashes repeatedly
- Look for application errors
- May indicate PyInstaller issues

### Issue: Sync Fails or Times Out

**Problem:** "Sync Games" button fails or takes too long.

**Solutions:**

1. **Check internet connection**

   ```cmd
   curl https://discord.com/api/v10/applications/detectable
   # Should return JSON data
   ```

2. **Try again later**
   - Discord API may be temporarily down
   - Try again in 5-10 minutes

3. **Use cached data**
   - Launcher works with cached data
   - You can still browse and add cached games
   - Sync again later when connection is better

4. **Check firewall/proxy**
   - Some corporate networks block Discord API
   - Try on different network (home/mobile hotspot)

### Issue: High CPU/Memory Usage

**Problem:** Launcher or dummy processes using too many resources.

**Solutions:**

1. **Check number of running games**
   - Each dummy process uses ~1-2 MB RAM
   - Stop games you're not actively displaying
   - Use "Stop All" button

2. **Launcher CPU usage**
   - Should be near 0% when idle
   - Periodic updates every 5 seconds
   - Check if refresh timer is stuck

3. **Game addition**
   - Copying template is instant (low CPU usage)
   - Should complete immediately
   - No compilation needed

**Normal Resource Usage:**

- Launcher: ~50-100 MB RAM, <1% CPU
- Each dummy: ~10-20 MB RAM, 0% CPU (sleeping)

### Issue: Duplicate Games in Library

**Problem:** Same game appears multiple times in library.

**Solution:**
This shouldn't happen due to database constraints, but if it does:

1. **Remove duplicates**
   - Click "Remove" on duplicate entries
   - Each game ID should only appear once

2. **Check database integrity**

   ```cmd
   # Advanced users only
   sqlite3 %LOCALAPPDATA%\discord-games-launcher\launcher.db
   .tables
   SELECT * FROM user_library;
   ```

3. **Reset database (last resort)**
   - Delete data directory (loses all data)
   - Re-add games after restart

### Issue: Antivirus Blocks Launcher

**Problem:** Antivirus flags the launcher or dummy executables.

**Solutions:**

1. **False positive**
   - PyInstaller executables are commonly flagged
   - The dummy executables are harmless (they only sleep)

2. **Add exceptions**
   - Add `%LOCALAPPDATA%\discord-games-launcher\` to exclusions
   - Add launcher project directory to exclusions

3. **Verify safety**
   - Check source code on GitHub
   - All code is open source and auditable
   - Dummy template at `templates/dummy_template.py`

**Note:** We can't prevent all antivirus false positives. This is a known limitation of PyInstaller.

## Error Messages

### "Game not found in cache"

**Cause:** Game ID doesn't exist in database

**Fix:** Sync games or search for the game again

### "Game is already in library"

**Cause:** Trying to add a game that's already added

**Fix:** Check your library tab, it's already there

### "No Windows executable found"

**Cause:** Game doesn't have Windows support in Discord's database

**Fix:** Try a different game, some are macOS/Linux only

### "Executable not found"

**Cause:** Dummy executable was deleted or moved

**Fix:** Remove game from library and re-add it

### "Failed to start game"

**Cause:** Various (see specific error)

**Fix:** Check process isn't running, regenerate executable, check antivirus

### "Sync failed"

**Cause:** Network error or Discord API issue

**Fix:** Check internet, try again later, use cached data

## Recovery Procedures

### Reset Cache Only

Removes cached games but keeps library:

```python
# Run in Python
from pathlib import Path
from platformdirs import user_data_dir
import sqlite3

db_path = Path(user_data_dir("discord-games-launcher", appauthor=False)) / "launcher.db"
with sqlite3.connect(db_path) as conn:
    conn.execute("DELETE FROM games_cache")
    conn.execute("DELETE FROM cache_metadata")
```

### Full Reset

Complete reset (loses everything):

```cmd
# Delete data directory
rmdir /s "%LOCALAPPDATA%\discord-games-launcher"

# Restart launcher - will recreate everything
python main.py
```

### Repair Installation

Reinstall without losing data:

```cmd
.venv\Scripts\activate
pip install -r requirements.txt --force-reinstall
python main.py
```

## Getting More Help

### Collect Information

When reporting issues, include:

1. **Error message** - Exact text or screenshot
2. **Steps to reproduce** - What you did before error
3. **Python version** - `python --version`
4. **OS version** - Windows 10/11, build number
5. **Discord version** - Desktop app version
6. **Logs** - Application logs from:
   - Run with verbose output: `python main.py 2>&1 | tee launcher.log`

### Debug Mode

Run with verbose output:

```cmd
python main.py 2>&1 | tee launcher.log
```

### Contact Support

1. **GitHub Issues** - File an issue with bug report template
2. **Discord Server** - Join community server (link in README)
3. **Email** - Contact maintainers (if listed in README)

### Check Documentation

- [Installation Guide](./installation.md) - Setup issues
- [Getting Started](./getting-started.md) - Usage questions
- [Features](./features.md) - What the launcher can do

---

**Still stuck?** Don't hesitate to ask for help! The community is here to assist.

# Getting Started

## First Launch

After [downloading and setup](./installation.md), launch the application by double-clicking `dcgl.exe` or running it from the command line:

```cmd
dcgl.exe
```

## Understanding the Interface

The Discord Games Launcher has a clean, dark-themed interface with two main tabs:

### Browse Games Tab

This is your game discovery area:

- **Search Bar:** Type to search through 3000+ Discord-supported games
- **Game Cards:** Each card shows:
  - Game name and aliases (alternative names)
  - Supported executables (Windows versions)
  - "Add to Library" button

### My Library Tab

This is your personal game collection:

- **Game Status:** Shows which games are Running or Stopped
- **Controls:** Start/Stop buttons for each game
- **Remove Button:** Remove games you no longer want

### Header Controls

- **Sync Games:** Updates the game database from Discord API (happens automatically on first launch)
- **Stats:** Shows cache statistics (total cached games, library size, running processes)
- **Status Bar:** Bottom bar showing live statistics

## Quick Start Guide

### Step 1: Search for a Game

1. Click on the **Browse Games** tab
2. Type a game name in the search box (e.g., "Minecraft", "Cyberpunk 2077", "Valorant")
3. Results appear instantly as you type

### Step 2: Add to Library

1. Find your desired game in the search results
2. Click the **"Add to Library"** button
3. The button changes to **"In Library"** (green)
4. The launcher copies a pre-built template and adds the game instantly

**Note:** This happens nearly instantly - the dummy executable is created by copying a template, not compilation.

### Step 3: Go to Your Library

1. Click the **My Library** tab
2. You'll see your newly added game
3. Status shows as **"Stopped"**

### Step 4: Start the Game

1. Click the **"Start"** button next to your game
2. Status changes to **"Running"** (green)
3. Check Discord - you should see "Playing [Game Name]" in your status!

### Step 5: Stop the Game

1. Click the **"Stop"** button
2. Status returns to **"Stopped"**
3. Discord status disappears

## Running Multiple Games

You can run multiple games simultaneously:

1. Add several games to your library
2. Click "Start" on each one
3. Your Discord status will show all active games
4. Use "Stop All" button to stop all at once

## Common Workflows

### Finding Games

- Use partial names: "mine" finds "Minecraft", "Minecraft Dungeons", etc.
- Try aliases: Searching "wow" finds "World of Warcraft"
- Browse all: Clear the search box to see all cached games

### Managing Your Library

- **Add games:** From Browse tab, click "Add to Library"
- **Remove games:** In Library tab, click "Remove" button
- **Check status:** Running games show green "Running" badge

### Syncing Games

The game database syncs automatically:

- First launch: Downloads all games (~5-10 seconds)
- Weekly: Auto-refresh (checks if cache is older than 7 days)
- Manual: Click "Sync Games" button anytime

## Tips and Best Practices

### Performance

- The launcher runs dummy processes with minimal CPU usage
- Each dummy process uses ~10-20 MB RAM (GUI window)
- No impact on gaming performance
- Adding games is instant (copy-based, no compilation)

### Discord Status

- Discord must be running to see the status
- Status appears within ~15 seconds of starting a game
- Some games may take longer for Discord to detect
- Status clears when you stop the game or close Discord

### Organization

- Add your most-played games to the library
- Use descriptive search terms
- Remove games you no longer play
- Group similar games together

### Safety

- Dummy executables are simple processes that display a GUI window
- No malicious activity is performed
- Generated executables are stored in your user data directory
- Antivirus may flag them initially (false positive - they're legitimate copies of a template)

## What to Do Next

Now that you know the basics:

1. **Explore the game database** - Browse through 3000+ supported games
2. **Build your library** - Add 5-10 games you play most
3. **Test with Discord** - Start a game and verify your status updates
4. **Read feature documentation** - Learn about advanced features in [Features](./features.md)

## Troubleshooting

Having issues? Check the [Troubleshooting Guide](./troubleshooting.md) for solutions to common problems.

## Updates

The launcher checks for stale cache automatically:

- Cache older than 7 days triggers a sync prompt
- Click "Sync Games" anytime for latest data
- Game database updates as Discord adds new supported games

---

**Enjoy showing off your game collection in Discord!**

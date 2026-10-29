<div align="center">

# Discord Games Launcher

<img src="assets/dcgl.png" alt="Discord Games Launcher" width="256">

A Windows app that makes Discord show a game as playing without owning it, and finishes quests from the client you already have open. Library games run as a small dummy process named what Discord looks for; quests need no process at all.

</div>

## Screenshots

| [![Quests view with desktop and video quests, their state, and the action that fits](docs/images/quests.png)](docs/images/quests.png) | [![Catalogue search results showing the Windows executable for each game](docs/images/catalogue.png)](docs/images/catalogue.png) |
| --- | --- |
| [![Library listing games and whether their dummy process is running](docs/images/library.png)](docs/images/library.png) | [![Settings showing the Discord client state and the launch patch entries](docs/images/settings.png)](docs/images/settings.png) |

[![Running view with the video being credited, a running game, and the queue of what runs next](docs/images/running.png)](docs/images/running.png)

## How it works

Discord scans running processes about every 15 seconds and matches executable names against its own game database. For a library game the launcher copies a prebuilt dummy executable to the process name the game needs and starts it, so Discord shows "Playing <game>" for as long as the process runs. Stopping ends the children first, then the parent.

A quest run works differently: it posts the same play-time heartbeat Discord's client posts, so no process, window, or library entry is created.

## Quests

The Quests view lists desktop play quests and video quests from your own client, including the ones Discord keys for its phone app. Each row carries the game, its executable, the reward, the time left, and the one button that fits the quest state (Run, Stop, or Watch).

The header shows the orb balance next to the quest counts. Sort by suggested order, expiry, orbs, or progress, filter by reward and quest type, and tick rows to queue them. Start selected accepts the quests you never accepted, runs play quests one at a time, and credits videos in the background; a play quest started while another runs joins the queue.

Quests are read out of the running client over loopback. A quest only counts after you accept it, so Run and Watch accept it first through the client: there is no separate Accept step and no Discord window opens. A quest run adds nothing to your library and copies nothing to disk.

A run that finishes on its own posts a Windows notification naming the quest and its reward, so a queue can be left running. A finished quest keeps its reward until claimed; the row then reads Claim, which claims through the running client. Discord answers some claims with a captcha, which can only be solved in its own window, so the client is brought to its quest page for it.

If Discord was started without the local endpoint, the view offers one setup that adds the flag to your Discord shortcuts and startup entry. It restarts Discord once, and the list is there every time Discord starts.

Settings holds Play activity (show a run on your profile or keep it private) and the pause between quests in minutes, which spaces finished runs out. The same page lists every Discord entry the setup touched, so the switch can be removed again.

Read [docs/dev/quests.md](docs/dev/quests.md) for how the reading works and where it fails.

## Catalogue

Browse every game Discord can display as activity.

- Search by game name or executable, filtered in SQL as you type.
- 200 games per page, loaded as you scroll, with only the visible rows mounted.
- Select several games and add them together; games you already own are marked and skipped.
- Only games with a Windows build are listed.

## Library

Your games, with the state Discord sees.

- Each row shows running or stopped and the exact process name.
- Start and Stop on the row, plus a menu to remove.
- Tick rows to remove several at once, or Select all; removal asks first.
- Removal stops the process, deletes the copied executable and its folder, and drops the database entry.
- Repair rebuilds the dummy files for every game, for when a file went missing.

## Download

Get `dcgl.exe` from [GitHub Releases](https://github.com/x01Jin/discord-games-launcher/releases). There is no installer; the executable is self-contained and the game database fills in on first launch.

## Quick start

1. Start `dcgl.exe`. The first launch downloads the game database.
2. Open Quests and press Run on a quest.
3. To play something else, find it in the Catalogue and press Add.
4. Start and stop it from the Library, or press Stop all.
5. Check Discord: the status appears within about 15 seconds of a process starting.

## Requirements

- Windows 10 or 11, 64-bit
- The Discord desktop app
- 500 MB free disk space
- Internet for the first database sync (about 20,000 games)

## Limits

- Windows only. Discord's detection works differently on macOS and Linux.
- Only games Discord already knows can be simulated.
- Basic "Playing" status, with no rich presence details.
- The catalogue comes from an undocumented Discord endpoint. Cached data keeps working if it changes.
- Some anti-cheat protected games use process names that cannot be mimicked.

## Documentation

[Documentation index](docs/index.md) covers installation, the bridge, the database, and the quest reader.

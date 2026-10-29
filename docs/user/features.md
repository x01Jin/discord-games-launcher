# Features

Discord Games Launcher puts a game of your choice in your Discord status. It
also lists the quests your Discord client is offering and starts the game each
one asks for.

## Quests

The Quests view shows what your own Discord client is offering right now: the
game, the reward, the time left, and one button that fits the state of the
quest. The list is read from the running app over a loopback endpoint, so the
request stays on this machine.

| Quest kind | What the row offers |
| --- | --- |
| Play on desktop | **Run**. Reports your play time to Discord, with no game window and no library entry. |
| Watch video | **Watch**. Discord credits the video while the app reports its progress, so no player window opens. |
| Mobile video | **Watch**. The progress post Discord accepts for this task is the same as the desktop one, so it finishes here too. |

Discord counts progress only for quests you accepted in the client. The app
accepts a quest itself the moment you press **Run** or **Watch**, without
opening a Discord window, so there is no separate Accept step. Rows that are
still unaccepted say so with a chip.

Rows show the artwork, the game and the executable Discord expects, the reward
(Orbs or an item), the time left in amber inside the last day, and the progress
bar once counting starts. The header shows your current orb balance, which Discord loads
once you have opened its quest page at least once.

The toolbar filters by All, Play, or Watch and by reward type (Orbs, avatar
decorations, in-game items), sorts by suggested order, expiry, orbs, or
progress, and keeps a switch for finished and expired quests.

### Running several quests

A quest run opens no game window at all. Play time is reported to Discord the
same way its own client reports it, so nothing pops up and your Playing status
stays as it is. The catalogue still uses the dummy game executable for games you
start yourself.

Every unfinished play or video quest has a checkbox, accepted or not. Tick the
ones you want and press **Start selected**: the queue accepts each quest that
was never accepted, runs play quests one after another, and credits video quests
in the background without touching the Discord window. Games and videos run in
their own queue, so a video starts while a game keeps running. The bar above the
list names what is running or which video is playing, with **Skip video** and
**Clear queue**. Pressing Watch on a single row queues that one quest the same
way.

While a video is being credited its button reads **Stop**, and the Running view
has the same Stop, so a mistaken watch does not have to run to the end.

### Running

The Running view lists what is in flight: the video being credited, every game
that is running, and what comes next. Queued games and queued videos are listed
in their own lanes, both always on screen, and each row can be moved up or down
or removed, so the next quest in a lane is whatever you put first. **Clear
queue** stops the video and empties the queue but leaves a running game alone.

### Quest options

Under Quest runs, **Play activity** picks what Discord shows while a quest runs.
**Show activity** (the default) puts the game on your profile; **Private** shows
nothing. Neither one opens a game or touches your Playing status elsewhere, and
both earn the same quest time.

**Pause between quests** (0 to 30 minutes, default 2) spaces runs out. After a
quest finishes on its own, the next queued one waits a random part of that pause,
so runs do not follow each other back to back. 0 starts the next quest on the
next tick. A manual **Stop** skips the pause.

Discord sometimes offers the same game in two quests. They run one after the
other from the queue, because two runs at once would only split the same play
time between two requests, and the second row waits its turn like any other.

### Starting Discord through the launcher

The Quests view can start Discord for you with the endpoint already in place,
so there is no restart. This only works while Discord is closed.

If Discord is already running, the view offers **Set up and restart Discord**.
That adds the endpoint switch to your Discord shortcuts and startup entry, then
restarts Discord once. You stay signed in.

From then on the list is there whenever Discord starts. The toolbar keeps a
**Set up silent start** button while the switch is missing, so the one restart
can wait until a convenient moment. **Turn silent connection off** removes the
switch again, and **Settings** in the sidebar lists every entry it touched and
can remove it from there.

## Catalogue

Browse every game Discord can display as an activity. Only games with a Windows
build are listed.

- Search by game name or executable; the filter runs in SQL as you type.
- Click rows to select several games, then add them together, or use Add on one
  row.
- Games already in your library are dimmed and skipped.
- More games load as you scroll. Only the visible rows are drawn, so the full
  list stays quick.

**Sync catalogue** pulls the current game list from Discord again, for when new
games have appeared.

## Library

The Library holds the games you added, each with its running state and the
exact process name Discord compares against.

Start and Stop sit on the row. The three-dot menu offers Start, Stop, and
Remove, and Remove asks before it deletes files. Tick the checkboxes to select
several games at once and remove them with one confirm, or use **Select all**;
removal stops a running game first. Refresh reloads the list, Repair rebuilds
the dummy files for every game (useful after antivirus removed one), and Stop
all ends every running game.

An empty library offers **Browse catalogue**, which jumps to the view where
games are added.

The library survives a restart of the app. Adding a game is instant because only
the dummy executable is copied, not a real game.

## Status on Discord

Starting a game opens a small window with the game name, "Game Started!", and a
running timer. Discord notices the process within about 15 seconds and your
status becomes "Playing [Game Name]". Several games can run at once, each with
its own window, and closing the launcher stops all of them.

For the status to appear:

- Discord must be running as the desktop app, not in a browser
- **Display current activity as a status message** must be on in Discord's
  Activity Privacy settings
- Give Discord one scan cycle, about 15 seconds

Each dummy window uses roughly 10 to 20 MB while it runs, and the launcher
itself is close to idle when no game is started.

## Artwork

Rows and cards use the artwork Discord serves for the game. When a game has no
picture, or you are offline, the first letter of its name fills in instead.

## Look

The whole app uses Discord's dark palette with one accent colour, and it follows
your Windows display scaling.

## Limits

- Windows only. Discord detects games differently on macOS and Linux.
- The Discord desktop app is required; the web version cannot show activity.
- Only games Discord already knows about can be shown.
- The status is plain "Playing X", without the detail a real rich presence
  integration provides.
- The launcher fakes the status. It does not start the real game.

## Getting help

[Troubleshooting](./troubleshooting.md) covers the common failures. For
anything else, open an issue on the project page.

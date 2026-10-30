# Features

Discord Games Launcher puts a game of your choice in your Discord status. It
also lists the quests your own client is offering and finishes them through
that client.

## Quests

Rows show the game, the executable Discord expects, the reward (Orbs or an
item), the time left in amber inside the last day, the progress bar once
counting starts, and one button that fits the quest state. The list is read
from the running app over a loopback endpoint, so the request stays on this
machine.

| Quest kind | What the row offers |
| --- | --- |
| Play on desktop | **Run**. Reports play time to Discord, with no game window and no library entry. |
| Watch video | **Watch**. Discord credits the video while the app reports its progress, so no player window opens. |
| Mobile video | **Watch**. The progress post Discord accepts for this task is the same as the desktop one, so it finishes here too. |

Discord counts progress only for quests you accepted in the client. **Run** and
**Watch** accept the quest themselves the moment you press them, without
opening a Discord window, so there is no separate Accept step. Rows that are
still unaccepted say so with a chip. The header shows your current orb balance,
which Discord loads once you have opened its quest page at least once.

The toolbar filters by All, Play, or Watch and by reward type (Orbs, avatar
decorations, in-game items), sorts by suggested order, expiry, orbs, or
progress, and keeps a switch for finished and expired quests.

### Queueing several quests

Every unfinished play or video quest has a checkbox, accepted or not. Tick the
ones you want and press **Start selected**: the queue accepts each quest that
was never accepted, runs play quests one after another, and credits video
quests in the background without touching the Discord window. Games and videos
run in their own lane, so a video starts while a game keeps running. The bar
above the list names what is running or which video is playing, with **Skip
video** and **Clear queue**. Pressing Watch on a single row queues that quest
the same way.

While a video is being credited its button reads **Stop**, and the Running view
has the same Stop, so a mistaken watch does not have to run to the end.

### Running view

Lists what is in flight: the video being credited, every game that is running,
and what comes next. Queued games and queued videos are listed in their own
lanes, both always on screen, and each row can be moved up or down or removed.
**Clear queue** stops the video and empties the queue but leaves a running game
alone.

### Finished quests and rewards

A quest that finishes on its own posts a Windows notification with its name and
reward, so a queue can be left running. A quest Discord marks completed outside
a run started here gets the same notification, once per quest.

The reward does not land on its own. A finished quest whose reward is still
unclaimed shows **Claim**, and pressing it claims the reward through the
running client. When Discord refuses that, the app switches Discord to its
Quests page and presses the client's own Claim button for that quest, which is
what makes Discord ask for a captcha when it wants one.

A claim that succeeds flips the row to **Done** and adds the reward to the orb
count even though Discord's own cached list updates later, so the page does not
keep showing a reward you already own. If the row stays after a press, Discord
refused the claim; check its Quests page.

### Quest options

Under Quest runs, **Play activity** picks what Discord shows while a quest runs.
**Show activity** (the default) puts the game on your profile; **Private** shows
nothing. Neither one opens a game, and both earn the same quest time.

Show activity gives the game to Discord the way a running game would, so the
card appears on your profile even while your status is **Invisible** or **Share
my activity** is off. In those cases the card reads **Not Sharing**: you see it,
other people do not. Turn **Share my activity** on under **Activity Privacy**
(older clients call it "Display current activity as a status message") and use a
visible status to share it.

**Pause between quests** (0 to 30 minutes, default 2) spaces runs out. After a
quest finishes on its own, the next queued one starts at a random point between
10 seconds and that pause. 0 starts it on the next tick. A manual **Stop** skips
the pause.

**Test mode** runs a quest only far enough to prove it works: a game quest stops
after two credited beats, a video quest after three progress posts. Nothing is
claimed and the quest stays unfinished, so you can queue everything, watch each
one prove itself, and still run them for real later.

Discord sometimes offers the same game in two quests. They run one after the
other from the queue, because two runs at once would only split the same play
time between two requests.

### Starting Discord through the launcher

The launch patch is what lets the launcher read quests: it adds the local
endpoint to every entry Windows starts Discord from. The Quests panel names the
one action that fits the situation:

- Discord closed, patch off: **Patch and run Discord** writes the patch and
  starts Discord with it.
- Discord open, patch off: **Patch and restart Discord** writes the patch and
  restarts Discord once. You stay signed in.
- Patch on: **Start Discord** or **Restart Discord now**, with no patch work.

Removing it works the same way round. With Discord closed, **Remove launch
patch** only restores the original shortcuts. With Discord open, both the
Quests panel and Settings ask first, because removing the patch also restarts
Discord without the endpoint so the port really closes.
Every launch here opens Discord from its own shortcut, so it behaves exactly
like clicking that shortcut: the window opens and the endpoint, when the patch
is on, is already in place.

## Catalogue

Browse every game Discord can display as an activity. Only games with a Windows
build are listed.

- Search by game name or executable; the filter runs in SQL as you type.
- Click rows to select several games, then add them together, or use Add on one
  row.
- Games already in your library are dimmed and skipped.
- More games load as you scroll. Only the visible rows are drawn.

**Sync catalogue** pulls the current game list from Discord again.

## Library

The Library holds the games you added, each with its running state and the
exact process name Discord compares against.

Start and Stop sit on the row. The three-dot menu offers Start, Stop, and
Remove, and Remove asks before it deletes files. Tick the checkboxes to select
several games and remove them with one confirm, or use the **Select all**
checkbox. Removal stops a running game first. Refresh reloads the list, Repair rebuilds the dummy
files for every game, and Stop all ends every running game. An empty library
offers **Browse catalogue**.

The library survives a restart of the app. Adding a game is instant because only
the dummy executable is copied, not a real game.

## Status on Discord

Starting a game opens a small window with the game name, "Game Started!", and a
running timer. Discord notices the process within about 15 seconds and your
status becomes "Playing [Game Name]". Several games can run at once, each with
its own window, and closing the launcher stops all of them.

For the status to appear, Discord must run as the desktop app with **Share my
activity** on under **Activity Privacy**, and it needs one scan cycle of about
15 seconds. Each dummy window uses roughly 10 to 20 MB while it runs, and the
launcher itself is close to idle when no game is started.

## Look

Rows and cards use the artwork Discord serves for the game; when a game has no
picture, or you are offline, the first letter of its name fills in instead. The
palette is Discord's dark set with one accent colour, scaled by Windows.

## Version and updates

The row below Settings shows the current version and a GitHub icon. Clicking it
opens the repository. The app checks GitHub's latest release at start and once an
hour; when a newer version exists, an amber **Update** chip appears and the row
opens that release instead.

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

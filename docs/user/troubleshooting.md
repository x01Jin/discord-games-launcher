# Troubleshooting

## Discord does not show a playing status

The launcher cannot see what Discord does with the process. It starts a dummy
executable with the name Discord compares against; whether the status appears
depends on Discord.

Check these, in order:

1. Discord is open and signed in, as the desktop app. The web client cannot
   show game activity.
2. Discord settings, Activity Privacy, **Display current activity as a status
   message** is on. This is the most common cause.
3. The library row says **Running**, and Task Manager shows the process name the
   row lists.
4. Give Discord one scan cycle, 15 to 30 seconds, and up to a minute on a busy
   machine.
5. Restart Discord from its tray icon, wait for it to load, and look again.
6. Try a well-known game such as Minecraft or VALORANT. Obscure titles take
   longer to be noticed.

If none of that works, the game may not be in Discord's database, your security
software may be hiding the process, or Discord itself may need to run as
administrator.

## Quests are not listed

The Quests page says Discord is not running, or that it cannot read the client.

1. Start Discord and sign in. The list comes from your own client, so it has to
   be open.
2. Read the reason on the panel. "Not installed" means Discord is missing for
   this Windows account. "Running, no endpoint" means Discord is open but was
   started in a way that does not expose the local endpoint.
3. If the panel offers **Set up and restart Discord**, press it. It adds the
   endpoint switch to your Discord shortcuts and startup entry, then restarts
   Discord once. You stay signed in. Anything running inside Discord, a call
   included, ends with the restart.
4. Open Discord's own Quests page. If Discord lists nothing there, the launcher
   has nothing to show either.
5. Press **Check again** after Discord finishes loading.

To undo the setup, use **Turn silent connection off** on the Quests panel, or
**Remove patch** in Settings. Both restore the original command lines and leave
nothing behind.

Watch quests are credited from here: the app reports the video progress to
Discord, so no player window opens and Discord stays usable. Phone quests only
count in the mobile app, and those are listed but cannot be finished here.

## A quest says "Accept"

Press **Accept**. It accepts the quest through the running Discord client without
opening a window, and the row becomes **Run** within about 20 seconds. The
queue accepts unaccepted rows for you.

The same applies to a game you started from the Library. Discord only counts
progress for accepted quests.

## Run does not change the quest

- **Done** or **Expired**: nothing to run. The quest is finished or past its end
  date.
- **Unsupported**: Discord did not include the game this quest belongs to.
- Nothing happens at all: check Activity Privacy in Discord (see the first
  section) and allow 15 to 30 seconds.

Progress only counts while the process runs. Stopping the game stops the
progress.

## The launcher does not start

1. Restart the PC and try again.
2. Allow `dcgl.exe` and `%LOCALAPPDATA%\discord-games-launcher\` in your
   antivirus.
3. Download `dcgl.exe` again from GitHub Releases. The copy may be damaged.
4. Confirm Windows 10 or 11, 64-bit.

## A game cannot be added

- The game may have no Windows build. Mac and Linux only titles cannot be added.
- Discord's list may not have arrived yet. Press **Sync catalogue**.
- Antivirus may have removed the game's files. Allow the launcher folder, remove
  the game, and add it again.

## A game stays Stopped

1. Press **Stop all**, then Start again.
2. Remove the game and add it back. That recreates its files.
3. Look in Task Manager for a leftover process with the same name and end it.
4. Antivirus may be deleting the executable right after it is copied.

## Catalogue sync fails

1. Check the connection.
2. Try again later. Discord's endpoint is sometimes slow or down.
3. Keep using the app. It works with the games it already saved.
4. Some school and office networks block Discord. Try another network.

## The app feels heavy

Each running game holds a small window, roughly 10 to 20 MB. The launcher itself
sits near 50 to 100 MB and almost no CPU when idle.

Press **Stop all** for games you are not showing.

## Antivirus flags the app

Each game window shows a name and a timer. That is all it does. Allow
`%LOCALAPPDATA%\discord-games-launcher\` in your antivirus. The source is
public, so the build can be checked.

## The same game appears twice

Remove the extra copy from the Library. If it comes back, do a full reset (below)
and add the game again.

## Error messages

`Game not found in cache`
: Press **Sync catalogue**, then try again. If it still fails, press **Repair**
  in the Library.

`Game is already in library`
: The game is in the Library already.

`Game is not in library`
: The saved entry is out of date. Press **Repair** in the Library.

`No Windows executable found`
: Discord's list has no Windows build for this game.

`Executable not found`
: The files were deleted or moved. Press **Repair**, or remove and re-add the
  game.

`Failed to start game`
: Check that no copy is already running, re-add the game, and check your
  antivirus.

`Sync failed`
: Check the connection and try again later. Saved games keep working.

## Full reset

This erases the library, the game list, and the logs:

```cmd
rmdir /s "%LOCALAPPDATA%\discord-games-launcher"
```

Start the app again and it rebuilds everything. The launch patch, if it was
enabled, is written to your Discord shortcuts and the startup entry, so remove
it in Settings first if you want a clean slate.

## Asking for help

Include the message you saw, the steps that led to it, your Windows version, the
Discord version, and the log from
`%LOCALAPPDATA%\discord-games-launcher\logs\` for today's date. Open an issue
on the project page.

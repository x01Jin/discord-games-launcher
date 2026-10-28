# Getting started

## First launch

Double-click `dcgl.exe`. The window opens on the Quests page. The first run
downloads Discord's game database, about 20,000 games, which takes a few
seconds.

## The window

A single window with a narrow left rail and one page at a time. The rail lists
Quests, Catalogue, and Library with their counts, Settings at the bottom, and
the Discord client state under it: a green dot and the port when the client can
be read, grey when it cannot.

## Quests

Rows show what your Discord client is offering: artwork, game, process name,
reward, time left, and one button. **Run** adds the game to your library and
starts its dummy process. **Stop** ends it. **Accept first** opens Discord's
quest page, because Discord only counts quests you accepted there. **Watch**
opens a video quest in Discord.

If Discord is closed, the page says so and offers **Start Discord**. If Discord
is running but was started without the local endpoint, the page explains the one
restart that fixes it for good. See [Features](./features.md#quests) for the
details.

## Catalogue

Type in the search box to filter by game name or executable. Each row has an Add
button; tick several rows and use the button in the toolbar to add them together.
Rows for games you already own are dimmed. Scrolling loads more games, 200 at a
time.

**Sync catalogue** in the toolbar downloads the game list again, for when new
games appear in Discord.

## Library

Every game you added, with its state and the process name Discord compares
against. **Start** and **Stop** are on the row; the three-dot menu also has
Remove. **Refresh** reloads the list, **Repair** rebuilds the dummy files if one
went missing, and **Stop all** ends every running game.

## Your Discord status

About 15 seconds after you press Start, Discord shows "Playing <game>". The
dummy window carries the game name and a running timer.

For the status to show, Discord must be open as the desktop app, and
**Display current activity as a status message** must be enabled under Discord's
Activity Privacy settings. Several games can run at once and all of them appear
in the status.

## Removing a game

Remove from the row menu. It asks first, then stops the process, deletes the
copied executable and its folder, and drops the library entry.

## If something looks wrong

[Troubleshooting](./troubleshooting.md) covers the common cases: a quest that
will not start, a status that never appears, and antivirus flags on the dummy
executable.

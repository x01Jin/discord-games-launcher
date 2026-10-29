# Getting started

## First launch

Double-click `dcgl.exe`. The window opens on the Quests page. The first run
downloads Discord's game database, about 20,000 games, which takes a few
seconds.

## The window

A single window with a narrow left rail and one page at a time. The rail lists
Quests, Running, Catalogue, and Library with their counts, Settings at the
bottom, and the Discord client state under it: a green dot and the port when
the client can be read, grey when it cannot.

## Quests

Rows show what your Discord client is offering: artwork, game, executable,
reward, time left, and one button. **Run** reports your play time to Discord
without opening a game; **Watch** credits a video quest in the background;
**Stop** ends either. Both accept the quest first, because Discord only counts
quests you accepted.

If Discord is closed, the page says so and offers **Start Discord**. If it is
running without the local endpoint, the page explains the one restart that
fixes it for good. [Features](./features.md#quests) covers the queue, the
Running view, and the quest options.

## Catalogue

Type in the search box to filter by game name or executable. Each row has an Add
button; tick several rows and add them together from the toolbar. Rows for games
you already own are dimmed, and scrolling loads 200 more at a time. **Sync
catalogue** downloads the game list again, for when new games appear.

## Library

Every game you added, with its state and the process name Discord compares
against. **Start** and **Stop** are on the row; the three-dot menu also has
Remove, which asks first and deletes the copied files. **Refresh** reloads the
list, **Repair** rebuilds dummy files, and **Stop all** ends every running game.

## Your Discord status

About 15 seconds after you press Start, Discord shows "Playing <game>", and the
dummy window carries the game name and a running timer. For the status to show,
Discord must be open as the desktop app, with **Share my activity** enabled
under its Activity Privacy settings (older clients call it "Display current
activity as a status message"). Several games can run at once and all of them
appear.

## If something looks wrong

[Troubleshooting](./troubleshooting.md) covers a quest that will not start, a
status that never appears, and antivirus flags on the dummy executable.

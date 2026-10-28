# Quests

## Overview

A Discord quest can pay out for playing a game on this PC. Discord decides
that by watching which games are running, which is the same signal this
launcher already fakes. The Quests view closes the loop: it lists the
play-on-desktop quests your own client is showing you, and starts the matching
dummy process.

Two rules shaped the implementation:

1. **The quest list comes from the client, not the REST API.** Reading a
   user's quests from discord.com needs their token. This app never touches
   tokens, and the client already holds the data.
2. **The quest list is the short one.** The catalogue exists so you can pick
   any of 24,000 games. A quest tells you which one is worth running, so the
   Quests view is the shortest path from "Discord is offering X" to "process
   named X is alive".

Modules: `launcher/discord_native.py` (client access),
`launcher/discord_setup.py` (launch-argument setup), `launcher/quests.py`
(quest model, executable resolution, start/stop).

## Which quests appear

The list is not filtered down to games. Three task families are read, and each
one is labelled with what this PC can actually do about it:

| Kind           | Discord task key       | Can this app finish it?             |
| -------------- | ---------------------- | ----------------------------------- |
| `play`         | `PLAY_ON_DESKTOP`      | Yes, by running the dummy executable |
| `watch`        | `WATCH_VIDEO`          | No - the client has to play the video. The row opens Discord instead |
| `watch_mobile` | `WATCH_VIDEO_ON_MOBILE` | No - it only counts on the phone app |

A quest that offers several keys is filed under the first of those three, so a
quest with both a desktop and a console task still shows up as `play`. Console
and activity quests are not listed at all: nothing on this machine can move
them.

Watch quests are listed because "no quests" and "four quests, two of which you
have to watch yourself" are different answers, and only the second one is
true. Their video thumbnail and required watch time come from the same payload.

## Accepting a quest first

Discord only credits progress for a quest the account has **accepted in the
client** (`userStatus.enrolledAt` is set). Running the fake process for a quest
that was never accepted produces heartbeats nobody counts, which looks like the
app doing nothing.

So the row is explicit: an unaccepted play quest shows **Accept first**, which
opens Discord's quest page, and `QuestService.start_quest()` refuses with
"Accept the quest in Discord first". Once the client reports the quest as
enrolled, the same row offers **Run**. The list refreshes on the poll, so no
manual step is needed after accepting.

## Why the DevTools protocol

Discord's desktop client is an Electron app. Its quest state lives in the
renderer's Flux stores and nowhere durable on disk: the client caches the
`/quests/@me` response in its Chromium disks only until it is evicted, and
persists no quest rows in Local Storage or IndexedDB. Parsing those caches is
both unreliable and stale.

The one stable door into a running Electron app is the Chrome DevTools
Protocol endpoint that Electron opens when the browser process starts with
`--remote-debugging-port`. Discord forwards that switch only from its own
command line: `chromiumSwitches` in `settings.json` is filtered through a fixed
allow-list that does not include it.

Three states matter:

- Discord started with the switch: quests are read live, in roughly 200 ms.
  That covers `DiscordNative.start()`, the Connect button, and every launch
  after the silent setup below.
- Discord closed: start it with the switch. Nothing was open, so this is not
  a restart at all.
- Discord already running without it: the renderer cannot be read, and no
  API exists to switch the endpoint on after launch. The app says so and offers
  one action that restarts Discord with a loopback `--remote-debugging-port`.
  Sign-in state survives because the same user data directory is reused.

Nothing is injected into Discord, no script is patched into the client, and no
Discord account data leaves the machine.

## Silent connection

The endpoint has to exist when Discord's browser process starts, so a client the
user opens by double-clicking its icon never has it. Instead of asking for a
restart after every manual launch, `launcher/discord_setup.py` adds
`--remote-debugging-port=9223` to the entries Windows starts Discord from:

| Entry          | Where                                                                     |
| -------------- | ------------------------------------------------------------------------- |
| Run key        | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `Discord` |
| Start menu     | `Programs\Discord.lnk` and `Programs\Discord Inc\Discord.lnk`          |
| Startup folder | `Discord*.lnk`                                                             |
| Desktop        | the user's and the Public desktop                                          |
| Taskbar        | the pinned `Discord.lnk`                                                   |

Squirrel launches Discord from shortcuts as
`Update.exe --processStart Discord.exe`, so the flag goes into
`--process-start-args "--remote-debugging-port=9223"` instead of being appended
to the shortcut target. A plain `Discord.exe` entry keeps its own
`--process-start-args` group and only gains the switch (`with_switch()`).
Shortcuts are read and written through one PowerShell call each, because `.lnk`
editing needs the `WScript.Shell` COM object and the app window must not flash
(`CREATE_NO_WINDOW`).

`enable()` is idempotent and replaces an existing port when one is already
there. `disable()` restores the original arguments and leaves entries it never
touched byte-identical, which is why `without_switch()` returns its input
unchanged when there is nothing to strip. The user's choice is recorded in
`%LOCALAPPDATA%\discord-games-launcher\silent_mode.json`; `DiscordNative.status()`
calls `heal()` on every status read, so a Discord update or reinstall that
rewrites a shortcut is repaired (rate limited to once per
`_REAPPLY_INTERVAL`, 120 s) without asking the user again.

The setup is per Windows account, changes no file inside the Discord
installation, sends nothing anywhere, and is reversible: **Turn silent
connection off** on the Quests panel and **Settings → Remove patch** both call
`disable_silent_mode()`. Settings also lists every entry that was touched, so
the change can be inspected before it is removed.

## Reading quests

`DiscordNative.candidate_ports()` collects, in order:

1. `DCGL_DISCORD_CDP_PORT`, if set.
2. Localhost TCP ports the Discord process tree is already listening on.
3. `9222`, `9223`, `9224`, `9229`.

`find_target()` asks each port's `/json/list` and takes the first page target
whose host is a Discord host. The route is deliberately not part of the test:
the client is a single-page app and can be sitting on `/channels/...`,
`/quest-home`, `/store`, or `/login`.

`CdpConnection` is a minimal RFC 6455 client (handshake, masked text frames,
fragmentation, ping/pong) rather than a dependency, because the only peer is a
loopback socket and the only method used is `Runtime.evaluate`.

The expression in `QUESTS_EXPRESSION` runs inside the renderer:

1. Pull the webpack require function out of `window.webpackChunkdiscord_app`.
2. Find the store whose `getName()` (or static `displayName`) is `QuestStore`,
   with a duck-typed fallback on `getQuest` plus `quests` for builds that rename
   it.
3. Read `store.quests` (Map, array, or plain object) and keep quests whose
   `taskConfigV2.tasks` (or legacy `taskConfig.tasks`) contains
   `PLAY_ON_DESKTOP`, `WATCH_VIDEO`, or `WATCH_VIDEO_ON_MOBILE`. The first
   match in that order sets `kind`, so a quest with several tasks is filed
   under the one this PC can act on first.
4. Emit a compact, JSON-serialisable subset: name, game title, application id,
   target seconds, progress, expiry, reward, and artwork paths.

It also reports `questAccessSuspendedUntil` and
`questEnrollmentBlockedUntil`, the two fields Discord's own client uses to stop
quest work. The view surfaces them instead of pretending the list is usable.

## Mapping a quest onto an executable

Discord matches a running process name to an application. A quest gives the
application **id**, not the executable, so the id is resolved against the local
catalogue cache:

- `Database.get_games([...])` loads every quest application in one query.
- `DiscordAPIClient.get_best_win32_executables()` scores the candidates the
  same way the catalogue does (non-launcher, shortest, no path separators).
- When the catalogue has never seen the application (a brand-new game the
  weekly sync has not delivered), the name is reduced to a plausible
  executable (`Risk of Rain 2` becomes `RiskofRain2.exe`) and a cache row is
  inserted with `Database.ensure_game_row()` so the library foreign key holds.
  The next catalogue sync overwrites that row with real data.

Two quests can point at the same application (Discord ships one offer per
region). Running the game once credits all of them, so each row reports
`shares_game_with` instead of looking like a duplicate.

## States and actions

`state` is the lifecycle; `action` is what the row's button should do. The
backend decides both so the UI never has to infer capability from a task key.

| State        | Meaning                                                |
| ------------ | ------------------------------------------------------ |
| `running`    | The dummy process for this quest's game is alive       |
| `ready`      | Inside its window and not finished                     |
| `expired`    | Past `expiresAt`; the client keeps these in its store  |
| `completed`  | `completedAt` set, or progress reached the target      |
| `unresolved` | A play quest with no application id, so nothing to fake |

| Action        | Button          | When                                      |
| ------------- | --------------- | ----------------------------------------- |
| `run`         | Run             | Accepted play quest, not running          |
| `stop`        | Stop            | Its dummy process is alive                |
| `enroll`      | Accept first    | Play quest not accepted in the client     |
| `open`        | Watch           | Desktop watch quest                       |
| `mobile`      | Phone           | Mobile-only watch quest                   |
| `done`        | Done / Expired  | Finished or past its end date             |
| `unsupported` | Unsupported     | No application id to fake                 |

Sort order is running, ready, expired, unresolved, completed; inside a state,
play quests come before watch quests, then soonest expiry. The page hides
finished rows behind "Show finished" and can filter to Play or Watch.

`start_quest()` only accepts a play quest, and only once it is enrolled, so a
stray call cannot start a process that would never be credited. `stop_quest()`
works for any quest whose dummy process is alive.

## Caching

`QuestService` keeps the last payload for `CACHE_TTL_SECONDS` (20 s). The
DevTools read costs a round trip and the client refreshes quests on its own
schedule, so a per-render fetch would be waste. Mutations invalidate the cache
and `Bridge.get_quests(force=True)` bypasses it.

## Failure modes

| Symptom                                | What the app does                                          |
| -------------------------------------- | ---------------------------------------------------------- |
| Discord not installed                  | Says so, no action offered                                  |
| Discord not running                    | "Start Discord", re-check button                            |
| Running without an endpoint, setup off | Explains the one restart, offers "Set up and restart Discord" |
| Running without an endpoint, setup on  | "One restart finishes the setup", offers "Restart Discord now" |
| Endpoint present, `QuestStore` missing | Reports the renderer's own message (usually: still loading)  |
| CDP call times out                     | Returns an error payload; never a partial list              |

`Bridge.get_quests()` never raises: connection problems become
`{connected: false, error}` and the view renders the reason.

## Scope

This app starts a process Discord already recognises as a game. It does not
join quests, send heartbeats, or touch the quest API, and it cannot complete
quest types other than play-on-desktop. Discord enforces against quest
automation; that risk belongs to running any tool like this one, and the app
does not hide it behind a green checkmark.

## Tests

- `tests/test_discord_native.py`: install discovery, target selection, frame
  codec, a full `Runtime.evaluate` round trip against a fake DevTools peer,
  payload parsing, status wording.
- `tests/test_quests.py`: decoration, executable resolution, states, sorting,
  cache behaviour, start and stop.
- `tests/test_bridge_quests.py`: bridge surface, error wrapping, event push.
- `tests/test_discord_setup.py`: argument rewriting, shortcut and Run key
  round trips against fakes, idempotence, disable restoring the original line.

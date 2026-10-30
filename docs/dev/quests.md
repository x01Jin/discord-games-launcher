# Quests

A Discord quest can pay out for playing a game on this PC, which Discord decides
from the play-time heartbeats a running game sends. The Quests view lists the
quests your own client is showing and posts those heartbeats itself.

Two rules shaped the implementation:

1. The quest list comes from the client, not the REST API. Reading a user's
   quests from discord.com needs their token, which this app never touches, and
   the client already holds the data.
2. A quest run opens no game. The client posts `POST /quests/{id}/heartbeat`
   while a game is open, and nothing on the server checks that the named process
   exists: the executable path is a label. Posting that request from here credits
   play time with no dummy executable, no library entry, and no window. The
   catalogue keeps the dummy executable for games you add yourself.

Code: `launcher/discord_native/` (client access: `client.py`, `cdp.py`,
`discovery.py`, `renderer/`), `launcher/discord_setup.py` (launch-argument
setup), `launcher/quests/` (model, service, play, watch, queue, monitor).

## Which quests appear

The list is not filtered down to games. Three task families are read, and each
one is labelled with what this PC can do about it:

| Kind | Discord task key | Can this app finish it? |
| --- | --- | --- |
| `play` | `PLAY_ON_DESKTOP` | Yes, by posting the play-time heartbeat from here |
| `watch` | `WATCH_VIDEO` | Yes, by posting the video progress from here |
| `watch_mobile` | `WATCH_VIDEO_ON_MOBILE` | Yes, the same `video-progress` post finishes it |

A quest with several keys is filed under the first of those three, so a quest
with both a desktop and a console task still shows up as `play`. Console and
activity quests are not listed: nothing on this machine can move them. Watch
quests are listed because "no quests" and "two quests, one of which pays for
watching a video" are different answers. Their thumbnail and required watch time
come from the same payload.

## Accepting a quest first

Discord credits progress only for a quest the account has accepted in the client
(`userStatus.enrolledAt` is set). A heartbeat for a quest that was never
accepted counts for nothing, which looks like the app doing nothing.

So the app accepts the quest itself. `start_quest()` and the queue call
`accept_quest()`, which posts `/quests/{id}/enroll` from the renderer with the
quest's `trafficMetadataSealed` blob, the same request Discord's own button
makes. Run and Watch both accept on the way in, so the row has no separate
Accept step. An unaccepted quest still carries a "Not accepted" chip, and a
failed enrollment is reported instead of starting a run nobody would credit.

## Why the DevTools protocol

Discord's desktop client is an Electron app, and its quest state lives in the
renderer's Flux stores and nowhere durable on disk: the client caches the
`/quests/@me` response in its Chromium disks only until eviction and keeps no
quest rows in Local Storage or IndexedDB. The one stable door into a running
Electron app is the DevTools endpoint Electron opens when the browser process
starts with `--remote-debugging-port`; Discord forwards that switch only from its
own command line, since `chromiumSwitches` in `settings.json` is filtered
through a fixed allow-list. Three states matter:

- Discord started with the switch: quests are read live, in roughly 200 ms. That
  covers `DiscordNative.start()`, the Connect button, and every launch after the
  silent setup below.
- Discord closed: start it with the switch. Nothing was open, so this is not a
  restart at all.
- Discord already running without it: the renderer cannot be read, and no API
  exists to switch the endpoint on after launch. The app says so and offers one
  action that restarts Discord with a loopback `--remote-debugging-port`.
  Sign-in state survives because the same user data directory is reused.

A restart asks Discord's windows to close with `WM_CLOSE`, then terminates what
is left, including every `app-*` build of that channel. Stopping only the newest
build left the pre-patch client running, so the new instance lost the
single-instance race and exited.

The relaunch opens Discord from its own shortcut (`discord_setup.shortcut_path()`),
the same file Explorer runs when the user clicks it, so the window opens
normally and the arguments already in the shortcut apply. Nothing is
synthesized: no `Update.exe` line, no extra flags. The shortcut carries the
endpoint switch when the patch is on, which is all a connected start needs.
When the patch is off the shortcut starts Discord exactly as before, and the
app reports that no endpoint came up instead of pretending it failed. This
replaces an `Update.exe --processStart ... --process-start-args` line that the
app built itself; that line dropped the shortcut's own arguments and produced a
Discord with no usable tray icon. A launch that dies within a couple of seconds
is reported as an early exit rather than waiting out the whole timeout.

Nothing is injected into Discord, no script is patched into the client, and no
account data leaves the machine.

## Silent connection

The endpoint has to exist when Discord's browser process starts, so a client
opened by double-clicking its icon never has it. `launcher/discord_setup.py`
adds `--remote-debugging-port=9223` to the entries Windows starts Discord from:

| Entry | Where |
| --- | --- |
| Run key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `Discord` |
| Start menu | `Programs\Discord.lnk` and `Programs\Discord Inc\Discord.lnk` |
| Startup folder | `Discord*.lnk` |
| Desktop | the user's and the Public desktop |
| Taskbar | the pinned `Discord.lnk` |

The default port is 9223. The Settings page reports the port the entries
actually carry, so a machine already patched to 9222 shows 9222.

Squirrel launches Discord from shortcuts as `Update.exe --processStart
Discord.exe`, so the flag goes into `--process-start-args
"--remote-debugging-port=9223"` instead of being appended to the target. A plain
`Discord.exe` entry keeps its own `--process-start-args` group and only gains
the switch (`with_switch()`). Shortcuts are read and written through one
PowerShell call each, because `.lnk` editing needs the `WScript.Shell` COM
object and the app window must not flash (`CREATE_NO_WINDOW`).

`enable()` is idempotent and replaces an existing port. `disable()` restores the
original arguments and leaves untouched entries byte-identical, which is why
`without_switch()` returns its input unchanged when there is nothing to strip.
The user's choice is recorded in `%LOCALAPPDATA%\discord-games-launcher\silent_mode.json`;
`DiscordNative.status()` calls `heal()` on every status read, so a Discord
update that rewrites a shortcut is repaired (rate limited to once per
`_REAPPLY_INTERVAL`, 120 s) without asking again.

The patch is only written by an explicit action. `start_discord()` and
`connect_discord()` patch first and then start or restart Discord with the
endpoint, which is what the Quests panel's two labels describe ("Patch and run
Discord", "Patch and restart Discord"). Nothing in `DiscordNative` patches on
its own: `start()` and `restart()` launch with the switch only for that run, so
an unpatched machine stays unpatched unless the user asks for it.

Removing the patch is the mirror image. `disable_silent_mode()` restores the
entries and, when Discord is running, restarts it without the endpoint
(`restart_without_endpoint()`). That restart is what makes the removal visible:
a running client keeps the endpoint it was started with, so restoring shortcuts
alone left the port open until the next manual restart, and any later Connect
silently patched the machine again. Both UIs confirm the removal first when
Discord is running, because it closes the window and drops voice connections.
Both restarts open Discord from the user's own shortcut, so it comes up the way
a click on that shortcut does.

The setup is per Windows account, changes no file inside the Discord
installation, sends nothing anywhere, and is reversible: **Turn silent
connection off** on the Quests panel and **Settings → Remove patch** both call
`disable_silent_mode()`.

## Reading quests

`DiscordNative.candidate_ports()` collects, in order:

1. `DCGL_DISCORD_CDP_PORT`, if set.
2. Localhost TCP ports the Discord process tree is already listening on.
3. `9222`, `9223`, `9224`, `9229`.

`find_target()` asks each port's `/json/list` and takes the first page target
whose host is a Discord host. The route is not part of the test: the client is a
single-page app and can be sitting on `/channels/...`, `/quest-home`,
`/store`, or `/login`.

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
   `PLAY_ON_DESKTOP`, `WATCH_VIDEO`, or `WATCH_VIDEO_ON_MOBILE`. The first match
   in that order sets `kind`.
4. Emit a compact, JSON-serialisable subset: name, game title, application id,
   target seconds, progress, expiry, reward, and artwork paths.

### Orbs and rewards

Rewards are read from every entry of `rewardsConfig.rewards`: orb rewards carry
`orbQuantity` with `premiumOrbQuantity` as the fallback, avatar decorations are
type 3, and in-game rewards (tokens, calling cards) are type 1. The orb amounts
are summed per quest and the first reward name labels the row.

The orb balance lives in a second store,
`VirtualCurrencyStore.getCurrentBalance()`, which the expression reads alongside
the quest list. The client returns null until it has fetched the balance, which
it defers until the quest page is opened once. The service passes null through
instead of 0 so the header can leave the chip out.

It also reports `questAccessSuspendedUntil` and `questEnrollmentBlockedUntil`,
the two fields Discord uses to stop quest work. The view surfaces them instead
of pretending the list is usable.

## The executable path is a label

The heartbeat needs an `executable_path` and Discord does not check it against
the filesystem: a fabricated name credits the same as a real one.

- The path comes from the quest payload (`process_name`) when the catalogue row
  exists, otherwise `derive_executable_name()` reduces the game name to a
  plausible file (`Risk of Rain 2` becomes `RiskofRain2.exe`).
- No cache row is written, no library entry is added, and nothing is copied to
  disk, so a quest for a game the catalogue cannot search still completes.
- Quest rows read the library only to show an "in library" badge.

Two quests can point at the same application (Discord ships one offer per
region). They run one after the other from the queue, because two play runs at
once would only split the same account's play time between two requests.

## Run modes

Two ways to credit a play quest, chosen in Settings and stored as `run_mode` in
`settings.json`:

- `activity` (default) posts the heartbeat and also tells the client the game is
  running, so the profile shows it. Nothing launches.
- `silent` posts the heartbeat and nothing else. The profile stays as it was.

Both earn the same quest time, because the time comes from the heartbeat and not
from a process. Activity mode adds a fake running game to the client's own
running-game store, the same route the reference userscript takes
(`ACTIVITY_EXPRESSION` in `launcher/discord_native/`).

Discord builds the "Playing X" card from `RunningGameStore`, not from the RPC
pipe: the store feeds `LocalActivityStore`, which is what the profile popout
reads. So the client is given the game the way it lists a real one:

1. Find `RunningGameStore` and the Flux dispatcher in the renderer's module
   registry.
2. Patch `getRunningGames`, `getGameForPID`, `getVisibleGame`,
   `getVisibleRunningGames`, `getRunningDiscordApplicationIds`, and
   `getCandidateGames` to append one fake game (pid, application id, name, start
   time, plausible executable fields).
3. Dispatch `RUNNING_GAMES_CHANGE` and `LOCAL_ACTIVITY_UPDATE`.

Stopping restores every original method and dispatches an empty
`RUNNING_GAMES_CHANGE` plus a null `LOCAL_ACTIVITY_UPDATE`, so no fake game
outlives the run.

Finding the store by name does not work: a scan that trusted `getName()` on
Discord 1.0.9265 found 460 stores and none of them was the game store. Real Flux
stores carry their class name on `__proto__.constructor.displayName`, which is
the finder both the userscript and this app use.

### Sharing, Invisible, and the profile card

Because the game comes from a local store, the card renders even when the client
is set not to share activity. Verified live on Discord 1.0.9265 while the status
was Invisible: `LocalActivityStore` held the game, `SelfPresenceStore` stayed
empty, and the profile popout drew the card with a **Not Sharing** subtitle. The
same happens with **Share my activity** off; only the gateway presence is
suppressed, never the local card.

`QuestService._activity_note()` reads `LocalActivityStore` through
`DiscordNative.activity_state()` after the game is added and only speaks up when
the client is not holding the game. The read is best effort.

### The rich presence pipe as a fallback

`launcher/rpc_activity.py` speaks `SET_ACTIVITY` over
`\\.\pipe\discord-ipc-0` to `discord-ipc-9`. Activity mode uses it only when
the store cannot be reached (no DevTools endpoint, or an unknown build without
`RunningGameStore`). Nothing in the pipe path is required while the store hook
works; a pipe-only activity credits nothing and draws no card, because the
profile card is driven by the store's `getVisibleGame()`.

## States and actions

`state` is the lifecycle; `action` is what the row's button should do. The
backend decides both, so the UI never infers capability from a task key.

| State | Meaning |
| --- | --- |
| `running` | This quest's play run or video is being credited here |
| `ready` | Inside its window and not finished |
| `expired` | Past `expiresAt`; the client keeps these in its store |
| `completed` | `completedAt` set, or progress reached the target |
| `unresolved` | A play quest with no application id, so nothing to fake |

| Action | Button | When |
| --- | --- | --- |
| `run` | Run | Play quest inside its window, not running |
| `stop` | Stop | Its play run or video wait is active |
| `open` | Watch | Video quest, credited in the background |
| `claim` | Claim | Finished, and `claimedAt` is still empty |
| `done` | Done / Expired | Finished and claimed, or past its end date |
| `unsupported` | Unsupported | Play quest with no application id |

Sort order is running, ready, expired, unresolved, completed; inside a state,
play quests come before watch quests, then soonest expiry. The page hides
finished rows behind "Show finished" and can filter to Play or Watch.

## Queue

Start selected (`start_quest_queue`) keeps the selection in one queue, and the
queue lives in the service so it survives a page change. It is pumped in two
independent lanes, one play runner and one video runner:

- Play quests start through `start_quest()` and run one at a time. A run posts
  `heartbeat` every `PLAY_BEAT_SECONDS` (20 s); the server credits the time that
  passed since the previous beat. The run ends when the response sets
  `completed_at` or the credited seconds reach the target, and a run that never
  completes stops after `PLAY_TIMEOUT_SECONDS` (4 h). The monitor thread ticks
  every second while a run is in flight and every 20 s when idle; it never
  exits, so a run that starts between two idle ticks cannot find a thread that
  already decided to stop.
- A beat whose credited total does not move means Discord is not counting the
  run (wrong task key, a refused executable, a quest pulled). After
  `PLAY_STALL_BEATS` beats like that the run stops and says so, instead of
  beating nothing for four hours.
- When a play run finishes on its own, the next queued game starts at a random
  point between 10 seconds and the configured pause (default 2 min), so runs do
  not follow each other back to back. A manual Stop skips the pause.
- Video quests are credited in the background without opening a Discord window.
  A mobile video quest takes this lane too, because Discord accepts the same
  progress post. The queue accepts the quest if needed, then posts
  `video-progress` every 7 to 9.5 s until the client reports `completedAt` or a
  progress that reached the target. One video is posted at a time, and it does
  not wait for a play run. A watch gives up after `WATCH_TIMEOUT_SECONDS`
  (30 min), and the full quest payload is re-read at most every
  `WATCH_REFRESH_SECONDS` (15 s).
- Stop on a row whose video is in flight calls `stop_quest()`, which ends the
  wait. Skip video (`skip_quest_watch`) does the same from the queue bar. Clear
  queue (`clear_quest_queue`) empties both lanes and drops the wait. A quest
  already being watched is not queued again by pressing Watch twice.
- `reorder_queue()` takes the order given and keeps unlisted ids at the end;
  `drop_queue_item()` removes one. The Running view moves ids within their own
  lane, so a video never changes where a game sits in its lane.
- A play quest that fails to start (Discord refused the heartbeat, the quest
  expired before its turn) rotates to the back of the queue and is retried after
  20 s, so one bad row cannot block everything behind it. At
  `PLAY_MAX_ATTEMPTS` failures it is dropped and remembered in the skip set,
  which a manual Run or a new Start selected clears. Anything that cannot be
  queued is skipped at enqueue time, and the message names both counts.
- A video quest the account has not accepted is dropped rather than watched:
  `video-progress` for an unenrolled quest credits nothing, and the old path
  posted into that void until the 30 minute timeout.
- A video run starts its timestamp at the progress Discord already holds, not at
  zero, so a part-watched quest resumes instead of sending a lower value.
- Pressing Run while another play quest is running enqueues it and answers
  "Queued behind the game quest that is running", so two runs never overlap.

## The client API

Every write runs in the renderer through `QUEST_API_EXPRESSION`
(`launcher/discord_native/`). The expression finds `QuestStore` the same way the
read does, then finds Discord's HTTP client by shape: the module export whose
value has `get`, `post`, and `del` functions and no `_dispatcher`. Some modules
export the global object, whose numeric keys are cross-origin iframes, so each
property read sits inside its own try block. That client already carries the
session, so no token is read or stored here.

| Op | Method | Route | Body |
| --- | --- | --- | --- |
| `enroll` | POST | `/quests/{id}/enroll` | `{location: 11, is_targeted: false, metadata_sealed: null, traffic_metadata_sealed}` |
| `heartbeat` | POST | `/quests/{id}/heartbeat` | `{application_id, terminal, executable_path}` |
| `video` | POST | `/quests/{id}/video-progress` | `{timestamp: <seconds, 6 decimals>}` |
| `claim` | POST | `/quests/{id}/claim-reward` | `{platform: 0, location: 11, is_targeted: false, metadata_sealed: null, traffic_metadata_sealed}` |

`traffic_metadata_sealed` comes from the quest payload and ties the request to
an offer the client actually saw. Expired quests answer `{"message": "Quest has
expired", "code": 260017}` with HTTP 404, so the queue only picks quests whose
`config.expiresAt` is still in the future.

The heartbeat is the request the client sends while a game is open. It was
captured from a real run and credits about 20 s per 20 s beat, both with a
running process and with nothing on disk. `terminal: true` closes the run: it
credits one last beat and clears the client-side heartbeat field. The response
carries `progress.PLAY_ON_DESKTOP.value` and `completed_at`, which the service
reads to decide when the quest is done.

Video progress is accumulated from the monotonic clock between posts, capped at
15 s per step, and the timestamp sent is that sum. Discord credits it as watch
time, so the video plays in Discord's sense without a player window, a quest
page, or a focus change.

`claim_quest_reward()` claims a reward the account already earned. A claim is
not always accepted, and the app cannot work around it: Discord answers with a
captcha challenge (`captcha_key` / `captcha_sitekey` in the error body) or its
own bot check, and only the client's own claim button carries the challenge. On
Discord 1.0.9265, a desktop claim for a finished mobile video quest came back
`403 {"message":"Unknown Message","code":10008}`, while the same endpoint
answered `260004` ("Quest does not support codes for this platform") for
platform 1 or 2, so the path and body are accepted and the refusal is
Discord-side.

A claim that succeeds does not update the client's own QuestStore: the request
goes through the client's HTTP layer, but nothing dispatches the result into the
store. A list read right after it therefore still showed the reward as unclaimed
and the old orb balance. The claim branch now writes `userStatus.claimedAt` on
the cached quest, and the service keeps a short overlay
(`CLAIM_OVERLAY_SECONDS`, 180 s) that marks the quest claimed and adds the
reward orbs to the balance it was claimed against. The overlay entry is dropped
as soon as the payload reports `claimedAt`, and the orb credit is dropped as
soon as the client's balance moves away from the recorded one, so a real balance
always wins over the estimate.

A refusal therefore hands the claim to the client's own UI.
`DiscordNative.open_quest_page()` switches the SPA route with

```js
history.pushState({}, "", "/quest-home");
window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
```

instead of the `discord://-/quest-home` deep link, which opened a second window.
`click_claim_reward(quest_id, name, alt_name)` then finds the quest's own card
and presses its Claim button, retrying for about ten seconds while the page
renders.

The card is the closest ancestor of a Claim button that still holds exactly one
Claim button and either an attribute ending in the quest id or the quest name or
game title in its text. The first version stopped at the first ancestor with
"enough text", which is the grid that holds every quest, so the click landed on
whichever Claim button came first: that is the wrong-quest claim, and Discord
answered it with its reward error. Two matches now come back as `ambiguous` and
nothing is pressed, so the user claims from Discord's page instead.

That UI click is the only path that can raise Discord's captcha. If the button
never appears, `launcher/discord_window.py` focuses the window and a Windows
toast states the failure, because the webview toast would be behind Discord by
then.

Verified on Discord 1.0.9266: the request that button sends is byte-identical to
the app's own claim body and got the same `403`, so a claim that fails here can
fail in the client too. `_focus_discord()` only restores a minimized window;
SW_RESTORE on a maximized one drops it back to its floating size.

The queue never claims on its own; only the row's button does.

## Notifications

A run that finishes by itself posts a Windows toast naming the quest and its
reward (`launcher/notifications.py`). Both lanes notify: a play quest when the
beat that crosses the target comes back, a video quest when its progress post
reports the target reached. A quest Discord marks completed outside a run
started here also gets a toast, the first time a read sees it completed and
unclaimed; duplicates are suppressed per quest for the life of the process. A
manual Stop does not notify, because the user already knows.

The toast is built as XML and handed to Windows PowerShell 5.1 as one base64
`-EncodedCommand`, launched with `CREATE_NO_WINDOW`. That is the only PowerShell
on a stock Windows that resolves the WinRT notification types; PowerShell 7
fails to find `[Windows.UI.Notifications.ToastNotificationManager]`. The app id
(`DCGL.DiscordGamesLauncher`) is not registered with the Start Menu, which
Windows accepts for desktop toasts.

A failure is logged and swallowed: a missing `powershell.exe` costs a warning
line, never a stalled run.

## Live progress

Every beat and every video-progress post answers with the server's credited
total for the quest's task. The service keeps that value per running quest
(`_live`), the monitor pushes it as a `quest_progress` event at most once a
second, and the frontend patches the one row in its quest cache. The list read
merges the same value, so a manual refresh and the pushed bar agree.

Play progress between beats is extrapolated from the last beat, capped at the
target and at one beat window. When Discord stops reporting, the bar freezes at
the last known value instead of inventing movement; a free-running bar reaching
100% while Discord's own page sat at 0% is the failure Orion documents as its
issue #43, and the same rule applies here. Video progress is the local clock,
which is the value being posted.

## Quest options

Two options live in `%LOCALAPPDATA%\discord-games-launcher\settings.json`
(`launcher/prefs.py`). They reach the service through `get_quest_prefs` /
`set_quest_prefs` and apply on the next tick, with no restart.

- `run_mode` (Play activity, default `activity`) picks between showing the game
  on the profile and staying private. An unknown value falls back to `activity`.
- `play_session_tail_min` (Pause between quests, default 2, allowed 0 to 30)
  spaces out finished runs: the next queued game starts at a random point
  between 10 seconds and those minutes. 0 starts it on the next tick.
- `test_mode` (default off) runs quests only far enough to prove the pipeline:
  enrolment, a beat the server credits, and a progress value coming back. A
  play run stops after `TEST_MODE_BEATS` beats, a video after
  `TEST_MODE_VIDEO_POSTS` posts, the stop is a normal terminal heartbeat, and
  nothing is claimed. The quest stays unfinished, so a test run can be repeated
  instead of consuming the offer.

`QuestService` keeps the last payload for `CACHE_TTL_SECONDS` (20 s), because
the DevTools read costs a round trip and the client refreshes quests on its own
schedule. Mutations invalidate the cache and `Bridge.get_quests(force=True)`
bypasses it.

## Failure modes

| Symptom | What the app does |
| --- | --- |
| Discord not installed | Says so, no action offered |
| Discord not running | "Start Discord", re-check button |
| Running without an endpoint, setup off | Explains the one restart, offers "Set up and restart Discord" |
| Running without an endpoint, setup on | "One restart finishes setup", offers "Restart Discord now" |
| Endpoint present, `QuestStore` missing | Reports the renderer's own message (usually: still loading) |
| CDP call times out | Returns an error payload; never a partial list |

`Bridge.get_quests()` never raises: connection problems become
`{connected: false, error}` and the view renders the reason.

## Scope

This app posts quest enrollment, play-time heartbeats, and video progress
through the client's own HTTP layer, and in activity mode gives the running game
to the client's own running-game store (rich presence pipe as a fallback). Video
tasks finish the same way whether Discord keys them for desktop or for mobile,
because both accept the same progress post. Console, stream, and activity quests
are not listed. Discord enforces against quest automation; that risk belongs to
running any tool like this one, and the app does not hide it.

The suite is described in [Testing](./testing.md).
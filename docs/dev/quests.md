# Quests

## Overview

A Discord quest can pay out for playing a game on this PC. Discord decides
that from the play-time heartbeats a running game sends. The Quests view closes
the loop: it lists the play-on-desktop quests your own client is showing you,
and posts those heartbeats itself.

Two rules shaped the implementation:

1. **The quest list comes from the client, not the REST API.** Reading a
   user's quests from discord.com needs their token. This app never touches
   tokens, and the client already holds the data.
2. **A quest run opens no game.** Discord's client posts
   `POST /quests/{id}/heartbeat` while a game is open, and nothing on the server
   checks that the named process exists: the executable path is a label. Posting
   that request from here credits play time with no dummy executable, no library
   entry, and no window. The catalogue keeps the dummy executable feature for
   games you add yourself.

Modules: `launcher/discord_native.py` (client access),
`launcher/discord_setup.py` (launch-argument setup), `launcher/quests.py`
(quest model, heartbeat and video runs, queue, prefs).

## Which quests appear

The list is not filtered down to games. Three task families are read, and each
one is labelled with what this PC can actually do about it:

| Kind           | Discord task key       | Can this app finish it?             |
| -------------- | ---------------------- | ----------------------------------- |
| `play`         | `PLAY_ON_DESKTOP`      | Yes, by posting the play-time heartbeat from here |
| `watch`        | `WATCH_VIDEO`          | Yes, by posting the video progress from here |
| `watch_mobile` | `WATCH_VIDEO_ON_MOBILE` | Yes - the same `video-progress` post finishes it |

A quest that offers several keys is filed under the first of those three, so a
quest with both a desktop and a console task still shows up as `play`. Console
and activity quests are not listed at all: nothing on this machine can move
them.

Watch quests are listed because "no quests" and "four quests, two of which pay
for watching a video" are different answers, and only the second one is true.
Their video thumbnail and required watch time come from the same payload.

## Accepting a quest first

Discord only credits progress for a quest the account has **accepted in the
client** (`userStatus.enrolledAt` is set). A heartbeat for a quest that was
never accepted counts for nothing, which looks like the app doing nothing.

So the app accepts the quest itself. `start_quest()` and the queue call
`accept_quest()`, which posts `/quests/{id}/enroll` from the renderer with the
quest's `trafficMetadataSealed` blob, the same request Discord's own button
makes. Run and Watch both accept on the way in, so the row has no separate
Accept step. An unaccepted quest still carries a "Not accepted" chip, and a
failed enrollment is reported instead of starting a run nobody would credit.

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

The default port is 9223. The Settings page reports the port the entries
actually carry, so a machine already patched to 9222 shows 9222 rather than
the default.

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

### Orbs and rewards

Rewards are read from every entry of `rewardsConfig.rewards`: orb rewards
carry `orbQuantity` with `premiumOrbQuantity` as the fallback, avatar
decorations are type 3, and in-game rewards (tokens, calling cards) are type 1.
The orb amounts are summed per quest and the first reward name labels the row.

The orb balance is not part of a quest; it lives in a second store,
`VirtualCurrencyStore.getCurrentBalance()`, which the expression reads
alongside the quest list. The client returns null until it has fetched the
balance, which it defers until the quest page is opened once. The service passes
null through instead of 0 so the header can leave the chip out.

It also reports `questAccessSuspendedUntil` and
`questEnrollmentBlockedUntil`, the two fields Discord's own client uses to stop
quest work. The view surfaces them instead of pretending the list is usable.

## The executable path is a label

The heartbeat needs an `executable_path` and Discord does not check it against
the filesystem: a fabricated name credits the same as a real one, which was
verified against a live account with an application the catalogue had never
seen.

- The path comes from the quest payload (`process_name`) when the catalogue row
  exists, otherwise `derive_executable_name()` reduces the game name to a
  plausible file (`Risk of Rain 2` becomes `RiskofRain2.exe`).
- No cache row is written, no library entry is added, and nothing is copied to
  disk, so a quest for a game the catalogue cannot search still completes.
- Quest rows read the library only to show an "in library" badge; the quest
  path never writes to it.

Two quests can point at the same application (Discord ships one offer per
region). They run one after the other from the queue, because two play runs at
once would only split the same account's play time between two requests.

## Run modes

Two ways to credit a play quest, chosen in Settings and stored as `run_mode` in
`settings.json`:

- `activity` (default) posts the heartbeat and also tells the client the game is
  running, so the profile shows it. Nothing launches.
- `silent` posts the heartbeat and nothing else. The profile stays as it was.

Both earn the same quest time because the time comes from the heartbeat, not from
a process. What the client shows is a separate matter.

Activity goes through Discord's own rich presence pipe,
`\\.\pipe\discord-ipc-0` to `discord-ipc-9` (`launcher/rpc_activity.py`): a JSON
handshake carrying the quest's application id, then `SET_ACTIVITY` with the game
name as `details` and a start timestamp. Closing the pipe withdraws the activity,
which is what a stop or a finished quest does. The handshake answer echoes the
activity back with the game name and application id, which is the confirmation
that the client accepted it.

The reference userscript patches `RunningGameStore` instead. That store does not
exist in Discord 1.0.9265: a scan of 460 stores in the loaded client found only
`OverlayRunningGameStore`, and duck-typed matchers for `getRunningGames` landed
on i18n proxies that return message objects. The pipe is the route that survived
on this build, and it needs no injected script and no debug port.

Two limits worth knowing:

- The pipe only works while the client has its RPC endpoint open, which it does
  by default. If `show()` fails the run continues on heartbeats and the log says
  why, so a quest never stalls over a cosmetic feature.
- An account set to Invisible shows no Playing line no matter what the client
  holds. The activity is still there; the status setting hides it.

A stale activity can outlive the pipe in `LocalActivityStore`. It credits
nothing (verified: no progress drift over 50 s with one sitting there) and clears
when the client next refreshes presence.

## States and actions

`state` is the lifecycle; `action` is what the row's button should do. The
backend decides both so the UI never has to infer capability from a task key.

| State        | Meaning                                                |
| ------------ | ------------------------------------------------------ |
| `running`    | This quest's play run or video is being credited here  |
| `ready`      | Inside its window and not finished                     |
| `expired`    | Past `expiresAt`; the client keeps these in its store  |
| `completed`  | `completedAt` set, or progress reached the target      |
| `unresolved` | A play quest with no application id, so nothing to fake |

| Action        | Button          | When                                      |
| ------------- | --------------- | ----------------------------------------- |
| `run`         | Run             | Play quest inside its window, not running |
| `stop`        | Stop            | Its play run or video wait is active      |
| `open`        | Watch           | Video quest, credited in the background   |
| `claim`       | Claim           | Finished, and `claimedAt` is still empty  |
| `done`        | Done / Expired  | Finished and claimed, or past its end date |
| `unsupported` | Unsupported     | Play quest with no application id         |

Sort order is running, ready, expired, unresolved, completed; inside a state,
play quests come before watch quests, then soonest expiry. The page hides
finished rows behind "Show finished" and can filter to Play or Watch.

`start_quest()` accepts a play quest first when it was never enrolled, then
begins the heartbeat run; an enrollment failure is reported instead of starting
a run nobody would credit. When another play quest is already running the call
queues the new one and says so, so pressing Run twice never starts two runs at
once. `stop_quest()` ends the running play quest or the video being credited.
A manual stop skips the pause between quests and starts the next queued one
right away.

## Queue

Start selected (`start_quest_queue`) keeps the selection in one queue, and the
queue lives in the service so it survives a page change. The queue is pumped in
two independent lanes, the same split the reference userscript uses (one play
runner and a separate video runner):

- Play quests start through `start_quest()` and run one at a time. A run posts
  `heartbeat` (see below) every `PLAY_BEAT_SECONDS` (20 s); the server credits
  the time that passed since the previous beat. The run ends when the response
  sets `completed_at` or when the credited seconds reach the target, and a run
  that somehow never completes stops after `PLAY_TIMEOUT_SECONDS` (4 h).
  The monitor thread ticks every 2 s while a run is in flight.
- When a play run finishes on its own, the next queued game waits a random 40%
  to 100% of the configured pause (default 2 min) before it starts, so runs do
  not follow each other back to back. A manual Stop skips the pause.
- Video quests are credited in the background, without opening a Discord
  window. A mobile video quest takes this lane too, because Discord accepts the
  same progress post for it. The queue accepts the quest if needed, then posts
  `video-progress` from here (see below) every 7 to 9.5 s until the client
  reports `completedAt` or a progress that reached the target. One video is
  posted at a time, and it does not wait for a play run: a video starts while a
  play run continues, and the next game starts while a video is in flight. A
  watch gives up after `WATCH_TIMEOUT_SECONDS` (30 min). While a video is in
  flight the monitor re-reads the full quest payload at most every
  `WATCH_REFRESH_SECONDS` (15 s).
- Stop on a row whose video is in flight calls `stop_quest()`, which ends the
  wait instead of greying the action out. Skip video (`skip_quest_watch`) does
  the same from the queue bar. Clear queue (`clear_quest_queue`) empties both
  lanes and drops the wait. A quest that is already being watched is not queued
  again by pressing Watch twice.
- Reordering and removal work on the pending ids. `reorder_queue()` takes the
  order given and keeps unlisted ids at the end; `drop_queue_item()` removes
  one. The Running view moves ids within their own lane, so a video never
  changes where a game sits in its lane.
- A play quest that fails to start (Discord refused the heartbeat, the quest
  expired between selection and its turn) stays queued and is retried on the
  next tick with the reason logged. Anything that cannot be queued is skipped at
  enqueue time, and the message names both counts.
- Pressing Run while another play quest is running enqueues it and answers
  "Queued behind the game quest that is running", so two runs never overlap.

## The client API

Every write runs in the renderer through `QUEST_API_EXPRESSION`
(`launcher/discord_native.py`). The expression finds `QuestStore` the same way
the read does, then finds Discord's HTTP client by shape: the module export whose
value has `get`, `post`, and `del` functions and no `_dispatcher`. Some modules
export the global object, whose numeric keys are cross-origin iframes, so each
property read sits inside its own try block; one of those frames used to abort
the whole scan with "Blocked a frame with origin https://discord.com". That
client already carries the session, so no token is read or stored here.

| Op          | Method | Route                        | Body                                                                                  |
| ----------- | ------ | ---------------------------- | ------------------------------------------------------------------------------------- |
| `enroll`    | POST   | `/quests/{id}/enroll`        | `{location: 11, is_targeted: false, metadata_sealed: null, traffic_metadata_sealed}` |
| `heartbeat` | POST   | `/quests/{id}/heartbeat`     | `{application_id, terminal, executable_path}`                                        |
| `video`     | POST   | `/quests/{id}/video-progress` | `{timestamp: <seconds, 6 decimals>}`                                                   |
| `claim`     | POST   | `/quests/{id}/claim-reward`  | `{platform: 0, location: 11, is_targeted: false, metadata_sealed: null, traffic_metadata_sealed}` |

`traffic_metadata_sealed` comes from the quest payload and is what ties the
request to an offer the client actually saw. Expired quests answer
`{"message": "Quest has expired", "code": 260017}` with HTTP 404, so the queue
only picks quests whose `config.expiresAt` is still in the future.

The heartbeat is the request the Discord client sends while a game is open. It
was captured from a real run and credits about 20 s per 20 s beat, both with a
running process and with nothing on disk. `terminal: true` closes the run: it
credits one last beat and clears the client-side heartbeat field. The response
carries `progress.PLAY_ON_DESKTOP.value` and `completed_at`, which the service
reads to decide when the quest is done.

Video progress is accumulated from the monotonic clock between posts
(`_watch_step`), capped at 15 s per step, and the timestamp sent is that sum.
Discord credits it as watch time, so the video plays in Discord's own sense
without a player window, a quest page, or any focus change.

`claim_quest_reward()` claims a reward the account already earned. A claim is
not always accepted: Discord answers some accounts with a captcha challenge
(`captcha_key` / `captcha_sitekey` in the error body) and only the client's own
claim button can drive it. `QuestApiError` carries that as `.captcha`, and
`QuestService.claim_reward()` returns it as `needs_user_action`, at which point
the bridge opens `discord://-/quest-home` and brings the Discord window forward
with `_focus_discord()`. The queue never claims on its own; only the row's
button does.

## Notifications

A run that finishes by itself posts a Windows toast naming the quest and its
reward (`launcher/notifications.py`). Both lanes notify: a play quest when the
beat that crosses the target comes back, a video quest when its progress post
reports the target reached. A manual Stop does not, because the user already
knows.

The toast is built as XML here and handed to Windows PowerShell 5.1 as one
base64 `-EncodedCommand`, launched with `CREATE_NO_WINDOW`. That is the only
PowerShell on a stock Windows that resolves the WinRT notification types;
PowerShell 7 fails to find `[Windows.UI.Notifications.ToastNotificationManager]`.
The app id (`DCGL.DiscordGamesLauncher`) is not registered with the Start Menu,
which Windows accepts for desktop toasts: verified by showing one and reading it
back from `ToastNotificationManager.History`.

Anything that goes wrong is logged and swallowed. A missing `powershell.exe`
costs a warning line, never a stalled run.

## Why a run can be visible but not shown

Setting the activity is not the same as Discord displaying it. Two account
settings gate the display, both read on demand from `UserSettingsProtoStore`
(`presence_state()`):

- `status.status` set to `invisible` broadcasts no presence at all.
- `status.showCurrentGame` off stops the client reporting any activity.

`start_quest()` checks both right after the activity is set and appends the
reason to its message, which the page shows as a toast. Verified against a live
client in this state: `LocalActivityStore.getActivities()` held
`{name: "Roblox", type: 0}` while the run was in flight, with the account
Invisible, so the activity itself was correct and the profile showed nothing.


## Quest options

Two options live in `%LOCALAPPDATA%\discord-games-launcher\settings.json`
(`launcher/prefs.py`). They reach the service through `get_quest_prefs` /
`set_quest_prefs` and apply on the next tick, with no restart.

- `run_mode` (Play activity, default `activity`) picks between showing the game
  on the profile and staying private. See "Run modes" above. An unknown value
  falls back to `activity`.
- `play_session_tail_min` (Pause between quests, default 2, allowed 0 to 30)
  spaces out finished runs: the next queued game starts after a random 40% to
  100% of those minutes. 0 starts it on the next tick.

"Hide activity" is gone. A run posts its own heartbeat, so the app does not turn
any client setting off, and the private mode is the thing that keeps the profile
quiet.

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

This app posts quest enrollment, play-time heartbeats, and video progress through
the client's own HTTP layer, and shows the running game over the client's rich
presence pipe in activity mode. Video tasks finish the same way whether Discord
keys them for desktop or for mobile, because both accept the same progress post.
Console, stream, and activity quests are not listed. Discord enforces against
quest automation; that risk belongs to running any tool like this one, and the
app does not hide it behind a green checkmark.

## Tests

- `tests/test_discord_native.py`: install discovery, target selection, frame
  codec, a full `Runtime.evaluate` round trip against a fake DevTools peer,
  payload parsing, status wording.
- `tests/test_quests.py`: decoration, executable labelling, states, sorting,
  heartbeat runs (first beat, cadence, completion, timeout, terminal beat on
  stop), run modes (activity shows and withdraws the game, silent never touches
  the pipe, a refused pipe falls back to private), orbs and prefs, the pause
  between quests, one run at a time, the queue including enrollment, mobile video
  quests, video progress cadence and the watch timeout.
- `tests/test_prefs.py`: settings file round trip, clamping, unknown keys,
  run mode validation, corrupt file fallback.
- `tests/test_bridge_quests.py`: bridge surface, error wrapping, event push.
- `tests/test_discord_setup.py`: argument rewriting, shortcut and Run key
  round trips against fakes, idempotence, disable restoring the original line.

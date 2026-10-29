"""Quest listing and quest runs for the running Discord client.

A play quest is credited by posting the client's own play heartbeat from here,
so no game process is ever launched and no dummy executable is created.
Activity mode also adds the game to the client's running-games store, which is
what Discord shows on the profile; silent mode leaves the store alone, so
nothing is shown. Both modes read quests from the running client (see
launcher.discord_native), never from Discord's REST API.
"""

from __future__ import annotations

import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from launcher import prefs as quest_prefs
from launcher.discord_native import DiscordNative, DiscordNativeError
from launcher.game_manager import GameManager
from launcher.rpc_activity import DiscordRpcActivity, RpcError

# How long a quest payload is reused before the client is asked again. The
# client only refreshes quests on its own schedule, so a shorter window would
# just cost a DevTools round-trip per repaint.
CACHE_TTL_SECONDS = 20.0

# Quest asset paths are relative to the media CDN root.
ASSET_BASE = "https://cdn.discordapp.com/"

# A video quest is credited by posting its progress from the running client,
# so a queued one is driven from here and the queue waits for it. The wait is
# abandoned after this long, otherwise a forgotten queue would sit on one
# video forever.
WATCH_TIMEOUT_SECONDS = 1800.0

# How often the watched video's quest is re-read to confirm it finished. The
# progress posts themselves are cheaper than a full quest read.
WATCH_REFRESH_SECONDS = 15.0

# Discord's game client beats every twenty seconds and the server credits the
# time since the previous beat, so this interval is also the progress rate.
PLAY_BEAT_SECONDS = 20.0

# A run that never reaches its target is abandoned rather than beaten forever.
PLAY_TIMEOUT_SECONDS = 4 * 3600.0

# The playing activity is injected into the client's own store, so it lasts
# until it is withdrawn. Nothing ticks it, and no game process exists.

def _parse_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _asset_url(path: Any) -> str | None:
    if not isinstance(path, str) or not path or path == "PLACEHOLDER":
        return None
    return ASSET_BASE + path.lstrip("/")


def _quest_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Quest payload keyed by quest id."""
    index: dict[str, dict[str, Any]] = {}
    for quest in payload.get("quests") or []:
        if not isinstance(quest, dict):
            continue
        quest_id = quest.get("id")
        if isinstance(quest_id, str) and quest_id:
            index[quest_id] = quest
    return index


def _quest_done(quest: dict[str, Any] | None) -> bool:
    """True when a quest stops holding a game session open.

    A quest that is gone from Discord, finished, or no longer credits play time
    cannot be helped by leaving the process alive, so it counts as done.
    """
    if quest is None:
        return True
    if quest.get("kind") != "play":
        return True
    if quest.get("state") in ("completed", "expired"):
        return True
    if quest.get("completedAt"):
        return True
    expires_at = _parse_time(quest.get("expiresAt"))
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        return True
    try:
        target = int(quest.get("target") or 0)
        progress = int(quest.get("progress") or 0)
    except (TypeError, ValueError):
        return False
    return target > 0 and progress >= target


def derive_executable_name(game_name: str) -> str:
    """Best-effort executable name for a quest app missing from the cache.

    Only used when the local catalogue has never seen the application. Discord
    matches process names case-insensitively, so dropping everything that
    cannot appear in a file name is enough to produce a plausible one.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]", "", game_name or "")
    return f"{cleaned or 'game'}.exe"


def _application_id(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if 0 < raw < 2**63 else None
    if isinstance(raw, str) and raw.isascii() and raw.isdigit():
        value = int(raw)
        return value if 0 < value < 2**63 else None
    return None


class QuestService:
    """Cached, decorated view of the client's quest list."""

    # How often the tail monitor looks at a running quest. Discord credits
    # play time in fifteen-second ticks, so a shorter interval buys nothing.
    MONITOR_INTERVAL = 10.0

    def __init__(
        self,
        game_manager: GameManager,
        native: DiscordNative | None = None,
        logger=None,
        ttl: float = CACHE_TTL_SECONDS,
        prefs_path: Path | None = None,
        monitor: bool = True,
        activity: DiscordRpcActivity | None = None,
    ):
        self.manager = game_manager
        self.native = native or DiscordNative(logger=logger)
        self._rpc = activity or DiscordRpcActivity(logger=logger)
        self.logger = logger
        self.ttl = ttl
        self.prefs_path = prefs_path
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._fetched_at = 0.0

        # One game quest runs at a time, credited by the heartbeats this
        # service posts. A video run is tracked separately, so both lanes can
        # move at once.
        self._run_lock = threading.Lock()
        self._playing: str | None = None
        self._playing_app: int | None = None
        self._playing_exe = ""
        self._playing_target = 0
        self._playing_at = 0.0
        self._beat_next = 0.0
        # True while a game is shown on the profile, so it can be withdrawn.
        self._activity_shown = False
        # Cooldown between a finished game quest and the next one.
        self._play_ready_at = 0.0
        self._queue: list[str] = []
        # The video quest the queue is crediting progress for.
        self._watching: str | None = None
        self._watching_at = 0.0
        self._watch_seconds = 0.0
        self._watch_last = 0.0
        self._watch_next = 0.0
        self._watch_checked_at = 0.0
        self._monitor_enabled = monitor
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()

    # -- cache ------------------------------------------------------------
    def _cached_payload(self) -> dict[str, Any] | None:
        if self._payload is None:
            return None
        if time.monotonic() - self._fetched_at > self.ttl:
            return None
        return self._payload

    def invalidate(self) -> None:
        with self._lock:
            self._payload = None
            self._fetched_at = 0.0

    def _refresh(self, force: bool) -> dict[str, Any]:
        with self._lock:
            if not force:
                cached = self._cached_payload()
                if cached is not None:
                    return cached
            payload = self.native.read_quests()
            self._payload = payload
            self._fetched_at = time.monotonic()
            return payload

    # -- reads ------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        state = self.native.status()
        state["cached"] = self._cached_payload() is not None
        state["fetched_at"] = self._fetched_at or None
        return state

    def list_quests(self, force: bool = False) -> dict[str, Any]:
        """Every play-on-desktop quest the client knows about, decorated."""
        status = self.native.status()
        if not status.get("running"):
            self.invalidate()
            return {
                "connected": False,
                "quests": [],
                "status": status,
                "error": None,
                "fetched_at": None,
            }

        try:
            payload = self._refresh(force)
        except DiscordNativeError as exc:
            self.invalidate()
            status = self.native.status()
            return {
                "connected": False,
                "quests": [],
                "status": status,
                "error": str(exc),
                "fetched_at": None,
            }

        raw_quests = [q for q in payload.get("quests", []) if isinstance(q, dict)]
        app_ids = [
            app_id
            for app_id in (_application_id(q.get("applicationId")) for q in raw_quests)
            if app_id is not None
        ]
        games = self._games_by_id(app_ids)

        library_ids = self._safe(lambda: self.manager.db.get_library_ids(), set())

        quests = [
            self._decorate(
                quest,
                games.get(_application_id(quest.get("applicationId"))),
                library_ids,
            )
            for quest in raw_quests
        ]
        with self._run_lock:
            queued = list(self._queue)
            playing = self._playing
            watching = self._watching
        if watching is not None:
            queued.insert(0, watching)
        queued_set = set(queued)
        for quest in quests:
            quest_id = quest.get("id")
            quest["queued"] = quest_id in queued_set
            # A run in flight has no game process behind it, so nothing marks
            # its row as running. Both lanes offer Stop instead of Run or Watch.
            if quest_id == playing or quest_id == watching:
                quest["state"] = "running"
                quest["action"] = "stop"
        quests.sort(key=_sort_key)

        return {
            "connected": True,
            "quests": quests,
            "status": status,
            "error": None,
            "fetched_at": self._fetched_at,
            "account": payload.get("account"),
            "suspended_until": payload.get("suspendedUntil"),
            "enrollment_blocked_until": payload.get("enrollmentBlockedUntil"),
            "total_quests": payload.get("questCount", len(quests)),
            # Discord's own Orb balance, null until the client has fetched it
            # once (opening its quest page does that).
            "orbs": payload.get("orbs"),
            "prefs": self.prefs(),
            "queue": {
                "ids": queued,
                "active": playing or watching,
                "watching": watching,
            },
        }

    def _games_by_id(self, app_ids: list[int]) -> dict[int, Any]:
        if not app_ids:
            return {}
        unique = sorted(set(app_ids))
        try:
            return self.manager.db.get_games(unique)
        except Exception:  # noqa: BLE001 - a cache miss must not break the list
            return {}

    @staticmethod
    def _safe(call, default):
        try:
            return call()
        except Exception:  # noqa: BLE001 - decoration is best-effort
            return default

    def _decorate(
        self, quest: dict[str, Any], game, library_ids: set[int]
    ) -> dict[str, Any]:
        app_id = _application_id(quest.get("applicationId"))
        game_name = str(quest.get("gameName") or "Unknown game")
        kind = str(quest.get("kind") or "play")
        playable = kind == "play"
        # Mobile video quests post the same progress payload as desktop ones.
        watchable = kind in ("watch", "watch_mobile")

        executables: list[dict[str, Any]] = []
        icon_hash: str | None = None
        if game is not None and playable:
            icon_hash = game.icon_hash
            try:
                executables = self.manager.api.get_best_win32_executables(
                    game.executables
                )
            except Exception:  # noqa: BLE001 - scoring failure means no candidates
                executables = []
        if not executables and playable:
            executables = [
                {"name": derive_executable_name(game_name), "os": "win32", "is_launcher": False}
            ]

        target = int(quest.get("target") or 0)
        progress = int(quest.get("progress") or 0)
        target = max(0, target)
        ratio = 0.0 if target <= 0 else min(1.0, max(0.0, progress / target))

        expires_at = _parse_time(quest.get("expiresAt"))
        now = datetime.now(timezone.utc)
        seconds_left = (
            int((expires_at - now).total_seconds()) if expires_at is not None else None
        )
        completed = bool(quest.get("completedAt")) or (
            target > 0 and progress >= target
        )
        expired = seconds_left is not None and seconds_left <= 0

        # Discord only credits a quest the account has accepted. A run before
        # that posts heartbeats nobody counts, which reads as "the app did
        # nothing", so the chip tells the row apart until Run or Watch accepts it.
        enrolled = bool(quest.get("enrolledAt"))

        # A quest run does not touch the library. The flag only says whether
        # the user already owns this game, which the row does not act on.
        in_library = app_id is not None and app_id in library_ids

        if completed:
            state = "completed"
        elif expired:
            state = "expired"
        elif not playable:
            state = "ready"
        elif app_id is None:
            state = "unresolved"
        else:
            state = "ready"

        # What the row's button does, decided here so the UI never has to infer
        # capability from a task key.
        if completed or expired:
            action = "done"
        elif not playable and not watchable:
            action = "mobile"
        elif playable and app_id is None:
            action = "unsupported"
        else:
            # Run and Watch accept the quest on the way in, so there is no
            # separate enrollment step in the row.
            action = "run" if playable else "open"

        video = quest.get("video") or {}
        return {
            "id": str(quest.get("id") or ""),
            "name": str(quest.get("name") or game_name),
            "game_name": game_name,
            "publisher": quest.get("publisher"),
            "kind": kind,
            "task_key": quest.get("taskKey"),
            "enrolled": enrolled,
            "action": action,
            "video_url": _asset_url(video.get("url")),
            "video_thumbnail": _asset_url(video.get("thumbnail")),
            "application_id": str(app_id) if app_id is not None else None,
            "icon_hash": icon_hash,
            "tile_url": _asset_url(quest.get("tile")),
            "hero_url": _asset_url(quest.get("hero")),
            "logotype_url": _asset_url(quest.get("logotype")),
            "accent": quest.get("accent"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "seconds_left": seconds_left,
            "target_seconds": target,
            "progress_seconds": progress,
            "progress": round(ratio, 4),
            "task_keys": [str(k) for k in quest.get("taskKeys") or []],
            "reward": {
                "label": quest.get("rewardName"),
                "labels": [
                    str(label) for label in (quest.get("rewardNames") or []) if label
                ],
                "orbs": quest.get("rewardOrbs"),
                "premium_orbs": quest.get("rewardPremiumOrbs"),
                "avatar_decoration": bool(quest.get("rewardAvatarDecoration")),
                "in_game": bool(quest.get("rewardInGame")),
            },
            "executables": [str(e.get("name", "")) for e in executables if e.get("name")],
            "process_name": str(executables[0].get("name", "")) if executables else None,
            "in_library": in_library,
            "is_running": False,
            "state": state,
        }

    # -- control ----------------------------------------------------------
    def _find(self, quest_id: str) -> dict[str, Any] | None:
        wanted = str(quest_id)
        for quest in self.list_quests().get("quests", []):
            if quest.get("id") == wanted:
                return quest
        # The click may land just after a quest expired or was claimed, so
        # re-read once before telling the user it is gone.
        for quest in self.list_quests(force=True).get("quests", []):
            if quest.get("id") == wanted:
                return quest
        return None

    def start_quest(self, quest_id: str) -> tuple[bool, str]:
        """Start crediting a play quest by posting heartbeats for it."""
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        if quest.get("state") == "completed":
            return False, "That quest is already complete"
        if quest.get("state") == "expired":
            return False, "That quest has expired"
        if quest.get("kind") != "play":
            return False, "That quest is not completed by playing a game"

        app_id = _application_id(quest.get("application_id"))
        if app_id is None:
            return False, "Discord did not send an application id for that quest"

        with self._run_lock:
            playing = self._playing
        if playing == quest_id:
            return True, "That quest is already running"
        if playing is not None:
            # One game quest at a time. Pressing Run while another runs lines
            # this one up instead of starting a second session.
            added = self._enqueue(quest_id)
            self._start_monitor()
            if not added:
                return True, "That quest is already in the queue"
            return True, "Queued behind the game quest that is running"

        if not quest.get("enrolled"):
            # Discord only counts progress for quests the account accepted.
            # This is the same request Discord's own Accept button sends.
            try:
                self.native.accept_quest(quest_id)
            except (DiscordNativeError, OSError) as exc:
                return False, f"Discord would not accept that quest: {exc}"
            quest["enrolled"] = True
            self.invalidate()

        return self._begin_play(quest, app_id)

    def _mode(self) -> str:
        """The run mode the user picked, defaulting to activity."""
        try:
            mode = str(self.prefs().get(quest_prefs.RUN_MODE) or "")
        except (OSError, ValueError):
            return quest_prefs.MODE_ACTIVITY
        return mode if mode in quest_prefs.RUN_MODES else quest_prefs.MODE_ACTIVITY

    def _begin_play(
        self, quest: dict[str, Any], app_id: int
    ) -> tuple[bool, str]:
        """Start a play run: post the heartbeat, then show the game if asked.

        The time always comes from the heartbeat. Activity mode also hands the
        game to the client over its game pipe, which is how the profile ends
        up saying Playing.
        """
        quest_id = str(quest.get("id"))
        name = str(quest.get("name") or "")
        executable = str(
            quest.get("process_name")
            or derive_executable_name(name or quest.get("game_name") or "")
        )
        target = int(quest.get("target_seconds") or 0)
        now = time.monotonic()
        try:
            self.native.send_heartbeat(quest_id, app_id, executable)
        except (DiscordNativeError, OSError) as exc:
            return False, f"Discord would not credit that quest: {exc}"
        activity = False
        if self._mode() == quest_prefs.MODE_ACTIVITY:
            try:
                self._rpc.show(app_id, name or executable)
                activity = True
            except (RpcError, OSError) as exc:
                # The quest still earns its time, it just does so privately.
                self._log("warning", f"Could not show the game as playing: {exc}")
        with self._run_lock:
            self._playing = quest_id
            self._playing_app = app_id
            self._playing_exe = executable
            self._playing_target = max(0, target)
            self._playing_at = now
            self._beat_next = now + PLAY_BEAT_SECONDS
            self._activity_shown = activity
        self.invalidate()
        self._start_monitor()
        self._log(
            "info",
            (
                f"Showing the play quest {name!r} as playing with heartbeats"
                if activity
                else f"Crediting the play quest {name!r} with heartbeats"
            ),
        )
        return True, f"Showing {name} as playing" if activity else f"Crediting {name}"

    def _enqueue(self, quest_id: str) -> bool:
        with self._run_lock:
            if quest_id in self._queue:
                return False
            self._queue.append(quest_id)
        self.invalidate()
        return True

    def accept_quest(self, quest_id: str) -> tuple[bool, str]:
        """Accept a quest without opening Discord's quest page."""
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        if quest.get("state") == "completed":
            return False, "That quest is already complete"
        if quest.get("state") == "expired":
            return False, "That quest has expired"
        if quest.get("enrolled"):
            return True, "That quest is already accepted"
        try:
            self.native.accept_quest(quest_id)
        except (DiscordNativeError, OSError) as exc:
            return False, f"Discord would not accept that quest: {exc}"
        self.invalidate()
        return True, "Quest accepted"

    def stop_quest(self, quest_id: str) -> tuple[bool, str]:
        with self._run_lock:
            watching = self._watching
            playing = self._playing
        if watching is not None and quest_id == watching:
            self._stop_watching(quest_id, "Stopped watching the video")
            return True, "Stopped watching the video"
        if playing is not None and quest_id == playing:
            # A manual stop starts the next quest right away: the tail only
            # spaces out quests that finished on their own.
            self._stop_playing("Stopped the quest session", tail=False)
            return True, "Stopped the quest session"
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        return False, "That quest is not running"


    # -- run tracking ------------------------------------------------------
    def prefs(self) -> dict[str, Any]:
        return quest_prefs.load(self.prefs_path)

    def update_prefs(self, values: dict[str, Any]) -> dict[str, Any]:
        return quest_prefs.save(values, self.prefs_path)

    def shutdown(self) -> None:
        """Close the beat in flight and stop the monitor thread."""
        with self._run_lock:
            playing = self._playing
            app_id = self._playing_app
            executable = self._playing_exe
            shown = self._activity_shown
        if shown:
            self._hide_activity()
        if playing is not None and app_id is not None:
            try:
                self.native.send_heartbeat(playing, app_id, executable, terminal=True)
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Could not close the quest session: {exc}")
        self._monitor_stop.set()
        with self._run_lock:
            self._playing = None
            self._playing_app = None
            self._activity_shown = False
            self._watching = None
            self._queue.clear()
            self._play_ready_at = 0.0
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0

    def _start_monitor(self) -> None:
        if not self._monitor_enabled:
            return
        with self._run_lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="dcgl-quest-run",
                daemon=True,
            )
            self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.is_set():
            with self._run_lock:
                busy = self._watching is not None or self._playing is not None
            # A video posts progress every 7 to 9.5 seconds and a play quest
            # beats every 20, so a short wake covers both.
            if self._monitor_stop.wait(2.0 if busy else self.MONITOR_INTERVAL):
                break
            try:
                self._monitor_tick(time.monotonic())
            except Exception as exc:  # noqa: BLE001 - the monitor must not die
                self._log("warning", f"Quest monitor error: {exc}")
            with self._run_lock:
                if (
                    self._playing is None
                    and not self._queue
                    and self._watching is None
                ):
                    break

    def _monitor_tick(self, now: float) -> None:
        """One pass: beat the running quest, post video progress, pump."""
        self._check_play(now)
        self._check_watch(now)
        self._pump()

    def _check_play(self, now: float) -> None:
        """Keep the run going and notice when the quest is done."""
        with self._run_lock:
            quest_id = self._playing
            app_id = self._playing_app
            executable = self._playing_exe
            target = self._playing_target
            started = self._playing_at
            beat_next = self._beat_next
        if quest_id is None or app_id is None:
            return
        if now - started > PLAY_TIMEOUT_SECONDS:
            self._stop_playing("Stopped the quest session after four hours")
            return
        if now < beat_next:
            return
        with self._run_lock:
            self._beat_next = now + PLAY_BEAT_SECONDS
        try:
            result = self.native.send_heartbeat(quest_id, app_id, executable)
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not beat the quest session: {exc}")
            return
        completed = bool(result.get("completed"))
        credited = result.get("credited")
        if (
            not completed
            and isinstance(credited, int)
            and not isinstance(credited, bool)
            and target > 0
            and credited >= target
        ):
            completed = True
        if completed:
            # The beat that crossed the target already credited the time, so
            # there is no terminal beat to send.
            self._stop_playing("Quest finished, starting the next one", close=False)

    def _hide_activity(self) -> None:
        """Close the game pipe so the profile stops showing the game."""
        with self._run_lock:
            self._activity_shown = False
        try:
            self._rpc.hide()
        except OSError as exc:
            self._log("warning", f"Could not clear the playing activity: {exc}")

    def _stop_playing(
        self, message: str, close: bool = True, tail: bool = True
    ) -> None:
        with self._run_lock:
            quest_id = self._playing
            app_id = self._playing_app
            executable = self._playing_exe
            if quest_id is None:
                return
            shown = self._activity_shown
            self._playing = None
            self._playing_app = None
            self._playing_exe = ""
            self._playing_target = 0
            self._playing_at = 0.0
            self._beat_next = 0.0
            self._activity_shown = False
        if shown:
            try:
                self._rpc.hide()
            except OSError as exc:
                self._log("warning", f"Could not clear the playing activity: {exc}")
        if close and app_id is not None:
            try:
                self.native.send_heartbeat(quest_id, app_id, executable, terminal=True)
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Could not close the quest session: {exc}")
        # Discord stops crediting the moment the beats stop, so a finished
        # quest waits out the configured tail before the next one starts.
        tail_minutes = int(self.prefs().get(quest_prefs.PLAY_SESSION_TAIL_MIN) or 0)
        if tail and tail_minutes > 0:
            self._play_ready_at = (
                time.monotonic() + random.uniform(0.4, 1.0) * tail_minutes * 60.0
            )
        else:
            self._play_ready_at = 0.0
        self.invalidate()
        self._log("info", message)
        self._pump()

    def _check_watch(self, now: float) -> None:
        """Post video progress for the queued video quest and notice the end."""
        with self._run_lock:
            quest_id = self._watching
            started = self._watching_at
            checked_at = self._watch_checked_at
        if quest_id is None:
            return
        if now - started > WATCH_TIMEOUT_SECONDS:
            self._stop_watching(
                quest_id, "Stopped waiting: the video quest did not finish"
            )
            return

        self._watch_step(now)
        with self._run_lock:
            if self._watching != quest_id:
                return
        # Reading the whole quest payload on every tick would spend more time
        # in DevTools than Discord spends crediting the video.
        if now - checked_at < WATCH_REFRESH_SECONDS:
            return
        with self._run_lock:
            self._watch_checked_at = now
        try:
            payload = self._refresh(force=True)
        except (DiscordNativeError, OSError):
            return
        quest = next(
            (
                raw
                for raw in payload.get("quests") or []
                if str(raw.get("id")) == quest_id
            ),
            None,
        )
        if quest is None:
            self._stop_watching(quest_id, "The waiting quest is gone from Discord")
            return
        try:
            target = int(quest.get("target") or 0)
            progress = int(quest.get("progress") or 0)
        except (TypeError, ValueError):
            return
        if quest.get("completedAt") or (target > 0 and progress >= target):
            self._stop_watching(quest_id, "Video quest finished, starting the next one")

    def _watch_step(self, now: float) -> None:
        """Report how many seconds of the video have played so far.

        Discord's own player posts a timestamp every few seconds; posting the
        same shape from the client is what earns the credit, with no page open
        and no visible window.
        """
        with self._run_lock:
            quest_id = self._watching
            if quest_id is None or now < self._watch_next:
                return
            elapsed = max(0.0, min(now - self._watch_last, 15.0))
            self._watch_last = now
            self._watch_seconds += elapsed
            self._watch_next = now + random.uniform(7.0, 9.5)
            seconds = self._watch_seconds
        try:
            result = self.native.send_video_progress(quest_id, seconds)
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not report video progress: {exc}")
            return
        if result.get("completed"):
            self._stop_watching(quest_id, "Video quest finished, starting the next one")

    def _stop_watching(self, quest_id: str, message: str) -> None:
        with self._run_lock:
            if self._watching != quest_id:
                return
            self._watching = None
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0
        self.invalidate()
        self._log("info", message)
        self._pump()


    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        try:
            getattr(self.logger, level)(message)
        except (AttributeError, OSError):
            pass

    # -- queue -------------------------------------------------------------
    # One game quest and one video quest run at a time. The two lanes are
    # independent, and each runs in the order the quests were selected.
    def start_queue(self, quest_ids: list[str]) -> tuple[bool, str]:
        if not isinstance(quest_ids, (list, tuple)):
            return False, "Invalid quest selection"
        wanted: list[str] = []
        for raw in quest_ids:
            if not isinstance(raw, str):
                continue
            quest_id = raw.strip()
            if quest_id and quest_id not in wanted:
                wanted.append(quest_id)
        if not wanted:
            return False, "Select at least one quest"

        accepted: list[str] = []
        skipped = 0
        for quest_id in wanted:
            quest = self._find(quest_id)
            with self._run_lock:
                running = quest_id == self._watching or quest_id == self._playing
            if quest is None or running:
                skipped += 1
                continue
            kind = quest.get("kind")
            # Play quests are credited by posting heartbeats and video quests
            # by posting progress, both from here. Neither opens Discord, so an
            # unaccepted quest is no reason to refuse it.
            ready = quest.get("state") == "ready"
            can_play = kind == "play" and ready
            can_watch = kind in ("watch", "watch_mobile") and ready
            if can_play or can_watch:
                accepted.append(quest_id)
            else:
                skipped += 1

        if not accepted:
            return False, (
                "None of the selected quests can run here: pick unfinished "
                "play or video quests"
            )

        with self._run_lock:
            for quest_id in accepted:
                if quest_id not in self._queue:
                    self._queue.append(quest_id)
        self._pump()
        message = f"Queued {len(accepted)} quest(s)"
        if skipped:
            message += f", skipped {skipped} that cannot run"
        return True, message

    def clear_queue(self) -> int:
        with self._run_lock:
            count = len(self._queue) + (1 if self._watching else 0)
            self._queue.clear()
            self._watching = None
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0
        return count

    def skip_watch(self) -> tuple[bool, str]:
        """Stop waiting for the video the queue opened in Discord."""
        with self._run_lock:
            quest_id = self._watching
        if quest_id is None:
            return False, "Nothing is waiting on a video"
        self._stop_watching(quest_id, "Skipped the waiting video")
        return True, "Skipped the video and moved on"

    def reorder_queue(self, quest_ids: list[str]) -> tuple[bool, str]:
        """Put the pending queue in the given order.

        Only ids already in the queue are taken, in the order given; anything
        the caller left out keeps its place at the end. The quest that is
        running or being watched is not part of the queue and cannot move.
        """
        if not isinstance(quest_ids, (list, tuple)):
            return False, "Invalid queue order"
        with self._run_lock:
            current = list(self._queue)
            if not current:
                return False, "The queue is empty"
            order: list[str] = []
            for raw in quest_ids:
                if not isinstance(raw, str):
                    continue
                quest_id = raw.strip()
                if quest_id in current and quest_id not in order:
                    order.append(quest_id)
            if not order:
                return False, "That order named no queued quest"
            order.extend(quest_id for quest_id in current if quest_id not in order)
            if order == current:
                return True, "The queue is already in that order"
            self._queue[:] = order
        return True, "Queue reordered"

    def drop_queue_item(self, quest_id: str) -> tuple[bool, str]:
        """Take one quest out of the pending queue without clearing the rest."""
        with self._run_lock:
            if quest_id not in self._queue:
                return False, "That quest is not waiting in the queue"
            self._queue.remove(quest_id)
            left = len(self._queue)
        return True, f"Removed it from the queue, {left} left"

    def _next_queued(self, kind: str, skip: str | None = None) -> str | None:
        """First pending quest of one kind, keeping the caller's order."""
        with self._run_lock:
            pending = list(self._queue)
        for quest_id in pending:
            if quest_id == skip:
                continue
            quest = self._find(quest_id)
            if quest is None:
                continue
            quest_kind = quest.get("kind")
            if quest_kind == kind or (kind == "watch" and quest_kind == "watch_mobile"):
                return quest_id
        return None

    def _pump(self) -> None:
        """Start the next queued quest in each lane.

        Discord credits one game and one video at a time, but the two lanes are
        independent: a video starts while a game keeps running, and the next
        game starts as soon as the previous one stops.
        """
        self._start_watching()
        self._start_playing()

    def _start_watching(self) -> bool:
        with self._run_lock:
            if self._watching is not None:
                return False
        quest_id = self._next_queued("watch")
        if quest_id is None:
            return False
        quest = self._find(quest_id) or {}
        if not quest.get("enrolled"):
            try:
                self.native.accept_quest(quest_id)
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Queued video quest could not be accepted: {exc}")
        now = time.monotonic()
        with self._run_lock:
            if quest_id in self._queue:
                self._queue.remove(quest_id)
            self._watching = quest_id
            self._watching_at = now
            # First progress post after one player-sized beat.
            self._watch_seconds = 0.0
            self._watch_last = now
            self._watch_next = now + random.uniform(7.0, 9.5)
            self._watch_checked_at = now
        self.invalidate()
        self._start_monitor()
        self._log(
            "info",
            f"Watching the video quest {quest.get('name')!r} in the background",
        )
        return True

    def _start_playing(self) -> bool:
        with self._run_lock:
            if self._playing is not None:
                return False
            if time.monotonic() < self._play_ready_at:
                # The tail after the previous quest has not run out yet.
                return False
        quest_id = self._next_queued("play")
        if quest_id is None:
            return False
        try:
            ok, message = self.start_quest(quest_id)
        except (DiscordNativeError, OSError, ValueError) as exc:
            ok, message = False, str(exc)
        if ok:
            with self._run_lock:
                if quest_id in self._queue:
                    self._queue.remove(quest_id)
            return True
        # Leave the id queued so the next tick retries. Draining the queue
        # against a disconnected client would lose the selection.
        self._log("warning", f"Queued quest did not start: {message}")
        return False

_STATE_ORDER = {
    "running": 0,
    "ready": 1,
    "expired": 2,
    "unresolved": 3,
    "completed": 4,
}

# Play quests are the ones this app can finish; watched ones come after them
# inside the same state so the actionable rows stay at the top.
_KIND_ORDER = {"play": 0, "watch": 1, "watch_mobile": 2}


def _sort_key(quest: dict[str, Any]) -> tuple[int, int, float, str]:
    state = _STATE_ORDER.get(str(quest.get("state")), 5)
    kind = _KIND_ORDER.get(str(quest.get("kind")), 3)
    left = quest.get("seconds_left")
    horizon = float(left) if isinstance(left, int) else float("inf")
    return (state, kind, horizon, str(quest.get("name") or "").lower())


__all__ = [
    "ASSET_BASE",
    "QuestService",
    "derive_executable_name",
]

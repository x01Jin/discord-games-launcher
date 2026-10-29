"""Quest listing for the Discord client that is running on this machine.

The launcher's usual job is to fake a game process so Discord shows a
"Playing" status. Quests need the same thing, but with one difference: the
user does not care which of 24,000 games is running, only which of the few
games an active quest is paying for. This module turns the client's quest
list into exactly that short list, and maps each quest onto the executable the
launcher already knows how to fake.

Quest data comes from the running client (see launcher.discord_native), never
from Discord's REST API. The executable names come from the local catalogue
cache, which is where they already live.
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
from launcher.api import DiscordAPIError
from launcher.discord_native import DiscordNative, DiscordNativeError
from launcher.game_manager import GameManager

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


def _completed_applications(payload: dict[str, Any]) -> set[int]:
    """Application ids whose desktop-play quest reached its target."""
    done: set[int] = set()
    for quest in payload.get("quests") or []:
        if not isinstance(quest, dict):
            continue
        if quest.get("kind") != "play":
            continue
        app_id = _application_id(quest.get("applicationId"))
        if app_id is None:
            continue
        try:
            target = int(quest.get("target") or 0)
            progress = int(quest.get("progress") or 0)
        except (TypeError, ValueError):
            continue
        if target > 0 and progress >= target:
            done.add(app_id)
    return done


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
    ):
        self.manager = game_manager
        self.native = native or DiscordNative(logger=logger)
        self.logger = logger
        self.ttl = ttl
        self.prefs_path = prefs_path
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._fetched_at = 0.0

        # Quest runs this service started, so the tail monitor and the
        # hide-activity switch know when the last one ends.
        self._run_lock = threading.Lock()
        self._quest_apps: dict[int, str] = {}
        self._tails: dict[int, float] = {}
        self._queue: list[str] = []
        # The video quest the queue is crediting progress for.
        self._watching: str | None = None
        self._watching_at = 0.0
        self._watch_seconds = 0.0
        self._watch_last = 0.0
        self._watch_next = 0.0
        self._watch_checked_at = 0.0
        self._hid_activity = False
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
        learner = LibState(library_ids, self.manager)

        quests = [
            self._decorate(quest, games.get(_application_id(quest.get("applicationId"))), learner)
            for quest in raw_quests
        ]
        # Several quests can point at one game (one offer per region). Discord
        # credits all of them while the game runs once, so the UI has to say so
        # instead of showing what look like duplicates.
        shared: dict[str, int] = {}
        for quest in quests:
            app = quest.get("application_id")
            if app:
                shared[app] = shared.get(app, 0) + 1
        with self._run_lock:
            queued = list(self._queue)
            active_ids = list(self._quest_apps.values())
            watching = self._watching
        if watching is not None:
            queued.insert(0, watching)
        queued_set = set(queued)
        for quest in quests:
            app = quest.get("application_id")
            quest["shares_game_with"] = max(0, shared[app] - 1) if app else 0
            quest["queued"] = quest.get("id") in queued_set
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
                "active": active_ids[0] if active_ids else watching,
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

    def _decorate(self, quest: dict[str, Any], game, learner: LibState) -> dict[str, Any]:
        app_id = _application_id(quest.get("applicationId"))
        game_name = str(quest.get("gameName") or "Unknown game")
        kind = str(quest.get("kind") or "play")
        playable = kind == "play"

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

        # Discord only credits a quest the account has accepted. Starting the
        # game before that produces heartbeats nobody counts, which reads as
        # "the app did nothing", so the row asks for enrollment first.
        enrolled = bool(quest.get("enrolledAt"))

        in_library = app_id is not None and app_id in learner.ids
        is_running = bool(learner.running(app_id)) if in_library else False

        if completed:
            state = "completed"
        elif expired:
            state = "expired"
        elif is_running:
            state = "running"
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
        elif not playable:
            action = "open" if kind == "watch" else "mobile"
        elif app_id is None:
            action = "unsupported"
        elif is_running:
            action = "stop"
        elif not enrolled:
            action = "enroll"
        else:
            action = "run"

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
            "is_running": is_running,
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
        """Add the quest's game to the library if needed, then start it."""
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        if quest.get("state") == "completed":
            return False, "That quest is already complete"
        if quest.get("state") == "expired":
            return False, "That quest has expired"
        if quest.get("kind") != "play":
            return False, "That quest is not completed by playing a game"
        if not quest.get("enrolled"):
            # Discord only counts progress for quests the account accepted.
            # This is the same request Discord's own Accept button sends.
            try:
                self.native.accept_quest(quest_id)
            except (DiscordNativeError, OSError) as exc:
                return False, f"Discord would not accept that quest: {exc}"
            quest["enrolled"] = True
            self.invalidate()

        app_id = _application_id(quest.get("application_id"))
        if app_id is None:
            return False, "Discord did not send an application id for that quest"

        if not quest.get("in_library"):
            try:
                registered = self._ensure_registered(app_id, quest)
            except (DiscordAPIError, OSError, ValueError) as exc:
                return False, f"Could not prepare the game: {exc}"
            if not registered:
                return False, "Could not prepare the game for this quest"
            quest["in_library"] = True

        ok, message = self.manager.start_game(app_id)
        if ok:
            self._track_start(app_id, quest_id)
        return ok, message

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
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        app_id = _application_id(quest.get("application_id"))
        if app_id is None:
            return False, "Discord did not send an application id for that quest"
        ok, message = self.manager.stop_game(app_id)
        if ok:
            self._track_stop(app_id)
        return ok, message

    def _ensure_registered(self, app_id: int, quest: dict[str, Any]) -> bool:
        """Make sure the catalogue and library know this application."""
        game = self.manager.db.get_game(app_id)
        if game is None:
            executables = [
                {
                    "name": name,
                    "os": "win32",
                    "is_launcher": False,
                }
                for name in (quest.get("executables") or [])
            ]
            self.manager.db.ensure_game_row(
                game_id=app_id,
                name=quest.get("game_name") or quest.get("name") or str(app_id),
                icon_hash=quest.get("icon_hash"),
                executables=executables,
            )
        ok, message = self.manager.add_to_library(app_id)
        if ok:
            return True
        return message == "Game is already in library"

    # -- run tracking ------------------------------------------------------
    # The reference userscript keeps a finished game's process alive for a
    # random slice of PLAY_SESSION_TAIL_MIN extra minutes, so a session does
    # not stop on the exact second the target is reached. Discord ends its own
    # heartbeat on completion, so the tail only extends the presence.
    def prefs(self) -> dict[str, Any]:
        return quest_prefs.load(self.prefs_path)

    def update_prefs(self, values: dict[str, Any]) -> dict[str, Any]:
        updated = quest_prefs.save(values, self.prefs_path)
        # Turning the setting off while a run is hidden puts the activity back
        # right away instead of at the end of the run.
        if not updated.get(quest_prefs.HIDE_ACTIVITY):
            self._restore_activity()
        return updated

    def _hide_activity(self) -> None:
        if not self.prefs().get(quest_prefs.HIDE_ACTIVITY):
            return
        with self._run_lock:
            if self._hid_activity:
                return
        try:
            previous = self.native.set_show_current_game(False)
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not hide the Discord activity: {exc}")
            return
        with self._run_lock:
            # previous False means the user already had it off; leave it alone
            # and do not turn it on later.
            self._hid_activity = bool(previous)

    def _restore_activity(self) -> None:
        with self._run_lock:
            if not self._hid_activity:
                return
            self._hid_activity = False
        try:
            self.native.set_show_current_game(True)
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not restore the Discord activity: {exc}")

    def _track_start(self, app_id: int, quest_id: str) -> None:
        with self._run_lock:
            self._quest_apps[app_id] = str(quest_id)
            self._tails.pop(app_id, None)
        self._hide_activity()
        self._start_monitor()

    def _track_stop(self, app_id: int) -> None:
        with self._run_lock:
            self._quest_apps.pop(app_id, None)
            self._tails.pop(app_id, None)
            idle = not self._quest_apps
        if idle:
            self._restore_activity()

    def shutdown(self) -> None:
        """Restore Discord's setting and stop the monitor thread."""
        self._monitor_stop.set()
        with self._run_lock:
            self._watching = None
            self._queue.clear()
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0
        self._restore_activity()

    def _start_monitor(self) -> None:
        if not self._monitor_enabled:
            return
        with self._run_lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="dcgl-quest-tail",
                daemon=True,
            )
            self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.is_set():
            with self._run_lock:
                watching = self._watching is not None
            # Video progress goes out every 7 to 9.5 seconds, so the loop has
            # to wake more often while a video is being watched.
            if self._monitor_stop.wait(2.0 if watching else self.MONITOR_INTERVAL):
                break
            try:
                self._monitor_tick(time.monotonic())
            except Exception as exc:  # noqa: BLE001 - the monitor must not die
                self._log("warning", f"Quest monitor error: {exc}")
            with self._run_lock:
                if (
                    not self._quest_apps
                    and not self._queue
                    and self._watching is None
                ):
                    break
        self._restore_activity()

    def _monitor_tick(self, now: float) -> None:
        """One pass: notice finished quests, start tails, end due ones."""
        self._check_watch(now)
        with self._run_lock:
            apps = list(self._quest_apps)
            tails = dict(self._tails)
        if not apps:
            self._restore_activity()
            self._pump()
            return

        due = [app_id for app_id, deadline in tails.items() if now >= deadline]
        for app_id in due:
            self._end_tail(app_id)

        with self._run_lock:
            apps = [
                app_id
                for app_id in self._quest_apps
                if self.manager.process_mgr.is_running(app_id)
            ]
            for app_id in list(self._quest_apps):
                if app_id not in apps:
                    self._quest_apps.pop(app_id, None)
                    self._tails.pop(app_id, None)
            idle = not self._quest_apps

        if idle:
            self._restore_activity()
            self._pump()
            return

        tail_minutes = int(self.prefs().get(quest_prefs.PLAY_SESSION_TAIL_MIN) or 0)
        try:
            payload = self._refresh(force=True)
        except (DiscordNativeError, OSError):
            return

        completed = _completed_applications(payload)
        with self._run_lock:
            for app_id in apps:
                if app_id in self._tails or app_id not in completed:
                    continue
                # Between 40% and 100% of the configured tail, per run.
                seconds = random.uniform(0.4, 1.0) * max(0, tail_minutes) * 60.0
                self._tails[app_id] = now + seconds
                self._log(
                    "info",
                    f"Quest finished for application {app_id}; "
                    f"keeping the process {seconds:.0f}s longer",
                )

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

    def _end_tail(self, app_id: int) -> None:
        with self._run_lock:
            self._tails.pop(app_id, None)
        try:
            ok, message = self.manager.stop_game(app_id)
        except Exception as exc:  # noqa: BLE001 - a failure is logged, not raised
            self._log("warning", f"Could not end the quest session: {exc}")
            return
        with self._run_lock:
            self._quest_apps.pop(app_id, None)
        self.invalidate()
        self._log("info", f"Quest session ended: {message if not ok else 'stopped'}")

    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        try:
            getattr(self.logger, level)(message)
        except (AttributeError, OSError):
            pass

    # -- queue -------------------------------------------------------------
    # Discord only credits one running game at a time, so selected quests run
    # in order: the next one starts when the previous one stops.
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
            if quest is None or quest_id == self._watching:
                skipped += 1
                continue
            kind = quest.get("kind")
            action = quest.get("action")
            # Play quests run as a faked game process; the queue accepts them
            # first when they were never started in Discord. Video quests are
            # credited by posting progress from here. Both kinds are queued
            # without opening Discord's quest page.
            can_play = kind == "play" and action in ("run", "enroll")
            can_watch = kind == "watch" and action == "open"
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

    def _pump(self) -> None:
        """Start the next queued quest when nothing is running or waiting."""
        while True:
            with self._run_lock:
                if self._quest_apps or self._watching is not None or not self._queue:
                    return
                quest_id = self._queue[0]
            quest = self._find(quest_id)
            if quest is not None and quest.get("kind") == "watch":
                if not quest.get("enrolled"):
                    try:
                        self.native.accept_quest(quest_id)
                    except (DiscordNativeError, OSError) as exc:
                        self._log(
                            "warning", f"Queued video quest could not be accepted: {exc}"
                        )
                now = time.monotonic()
                with self._run_lock:
                    if self._queue and self._queue[0] == quest_id:
                        self._queue.pop(0)
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
                return
            try:
                ok, message = self.start_quest(quest_id)
            except (DiscordNativeError, OSError, ValueError) as exc:
                ok, message = False, str(exc)
            if ok:
                with self._run_lock:
                    if self._queue and self._queue[0] == quest_id:
                        self._queue.pop(0)
                return
            # Leave the id at the head so the next tick retries. Draining the
            # queue against a disconnected client would lose the selection.
            self._log("warning", f"Queued quest did not start: {message}")
            return

class LibState:
    """Per-request library membership cache.

    Decorating 40 quests would otherwise run one process lookup each; the id
    set is one query and the running check is memoised per application.
    """

    __slots__ = ("_manager", "_running", "ids")

    def __init__(self, ids: set[int], manager: GameManager):
        self.ids = ids
        self._manager = manager
        self._running: dict[int, bool] = {}

    def running(self, app_id: int | None) -> bool:
        if app_id is None:
            return False
        if app_id not in self._running:
            try:
                self._running[app_id] = self._manager.process_mgr.is_running(app_id)
            except Exception:  # noqa: BLE001 - a dead process counts as not running
                self._running[app_id] = False
        return self._running[app_id]


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

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from launcher import prefs as quest_prefs
from launcher.discord_native import DiscordNative, DiscordNativeError, QuestApiError
from launcher.game_manager import GameManager
from launcher.rpc_activity import DiscordRpcActivity

from .model import (
    CACHE_TTL_SECONDS,
    CLAIM_OVERLAY_SECONDS,
    EMPTY_CACHE_TTL_SECONDS,
    PLAY_BEAT_SECONDS,
    PROGRESS_PUSH_SECONDS,
    _application_id,
    _asset_url,
    _parse_time,
    _sort_key,
    derive_executable_name,
)
from .monitor import MonitorMixin
from .play import PlayMixin
from .queue import QueueMixin
from .watch import WatchMixin


class QuestService(MonitorMixin, PlayMixin, WatchMixin, QueueMixin):
    def __init__(
        self,
        game_manager: GameManager,
        native: DiscordNative | None = None,
        logger=None,
        ttl: float = CACHE_TTL_SECONDS,
        prefs_path: Path | None = None,
        monitor: bool = True,
        activity: DiscordRpcActivity | None = None,
        notifier=None,
    ):
        self.manager = game_manager
        self.native = native or DiscordNative(logger=logger)
        self._rpc = activity or DiscordRpcActivity(logger=logger)
        self.notifier = notifier
        self.on_change = None
        self.on_progress = None
        self.logger = logger
        self.ttl = ttl
        self.prefs_path = prefs_path
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._fetched_at = 0.0

        self._live: dict[str, dict[str, Any]] = {}
        self._last_push = 0.0
        self._last_pushed: dict[str, float] = {}

        self._skipped: set[str] = set()
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}
        self._claimed: dict[str, float] = {}
        self._orbs_bonus = 0
        self._orbs_base: int | None = None

        self._run_lock = threading.Lock()
        self._playing: str | None = None
        self._playing_app: int | None = None
        self._playing_exe = ""
        self._playing_name = ""
        self._playing_reward: str | None = None
        self._playing_target = 0
        self._playing_task = ""
        self._playing_at = 0.0
        self._beats = 0
        self._idle_beats = 0
        self._last_credited: int | None = None
        self._beat_next = 0.0
        self._activity_shown = False
        self._play_ready_at = 0.0
        self._queue: list[str] = []
        self._notified: set[str] = set()
        self._watching: str | None = None
        self._watching_name = ""
        self._watching_reward: str | None = None
        self._watching_at = 0.0
        self._watching_task = ""
        self._watching_target = 0
        self._watch_posts = 0
        self._watch_seconds = 0.0
        self._watch_last = 0.0
        self._watch_next = 0.0
        self._watch_checked_at = 0.0
        self._monitor_enabled = monitor
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._monitor_wake = threading.Event()

    def _cached_payload(self) -> dict[str, Any] | None:
        if self._payload is None:
            return None
        ttl = self.ttl
        try:
            if int(self._payload.get("questCount") or 0) <= 0:
                ttl = min(ttl, EMPTY_CACHE_TTL_SECONDS)
        except (TypeError, ValueError):
            pass
        if time.monotonic() - self._fetched_at > ttl:
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

    def status(self) -> dict[str, Any]:
        state = self.native.status()
        state["cached"] = self._cached_payload() is not None
        state["fetched_at"] = self._fetched_at or None
        return state

    def _test_mode(self) -> bool:
        try:
            return bool(self.prefs().get(quest_prefs.TEST_MODE))
        except (OSError, ValueError):
            return False

    def _track_progress(
        self, quest_id: str | None, credited: Any, target: Any, kind: str
    ) -> None:
        if quest_id is None or credited is None:
            return
        try:
            value = float(credited)
            limit = float(target or 0)
        except (TypeError, ValueError):
            return
        if value < 0:
            return
        with self._run_lock:
            self._live[str(quest_id)] = {
                "credited": value,
                "target": max(0.0, limit),
                "kind": kind,
                "at": time.monotonic(),
            }

    def _live_values(self, now: float) -> dict[str, float]:
        with self._run_lock:
            playing = self._playing
            watching = self._watching
            entries = {
                quest_id: dict(entry)
                for quest_id, entry in self._live.items()
                if quest_id in (playing, watching)
            }
        values: dict[str, float] = {}
        for quest_id, entry in entries.items():
            credited = float(entry.get("credited") or 0.0)
            if quest_id == playing:
                since = max(0.0, now - float(entry.get("at") or now))
                credited += min(since, PLAY_BEAT_SECONDS)
            target = float(entry.get("target") or 0.0)
            if target > 0:
                credited = min(credited, target)
            values[quest_id] = credited
        return values

    def _push_progress(self, now: float) -> None:
        if self.on_progress is None:
            return
        if now - self._last_push < PROGRESS_PUSH_SECONDS:
            return
        self._last_push = now
        values = self._live_values(now)
        with self._run_lock:
            self._last_pushed = {
                key: value for key, value in self._last_pushed.items() if key in values
            }
        for quest_id, credited in values.items():
            previous = self._last_pushed.get(quest_id)
            if previous is not None and int(previous) == int(credited):
                continue
            self._last_pushed[quest_id] = credited
            with self._run_lock:
                entry = dict(self._live.get(quest_id) or {})
            try:
                self.on_progress(
                    {
                        "quest_id": quest_id,
                        "credited": round(credited, 1),
                        "target": float(entry.get("target") or 0.0),
                        "kind": str(entry.get("kind") or ""),
                    }
                )
            except Exception as exc:
                self._log("warning", f"Could not push quest progress: {exc}")

    def _forget_progress(self, quest_id: str) -> None:
        with self._run_lock:
            self._live.pop(quest_id, None)
            self._last_pushed.pop(quest_id, None)

    def _remember_claim(self, quest: dict[str, Any]) -> None:
        quest_id = str(quest.get("id") or "")
        if not quest_id:
            return
        reward = quest.get("reward") or {}
        orbs = reward.get("orbs")
        with self._run_lock:
            self._claimed[quest_id] = time.monotonic() + CLAIM_OVERLAY_SECONDS
            payload = self._payload or {}
            balance = payload.get("orbs")
            if (
                isinstance(orbs, int)
                and not isinstance(orbs, bool)
                and orbs > 0
                and isinstance(balance, int)
                and not isinstance(balance, bool)
            ):
                if self._orbs_base is None:
                    self._orbs_base = balance
                self._orbs_bonus += orbs

    def _claim_overlay(self, quests: list[dict[str, Any]]) -> None:
        now = time.monotonic()
        with self._run_lock:
            active = {
                quest_id: until
                for quest_id, until in self._claimed.items()
                if until > now
            }
            self._claimed = active
            for quest in quests:
                if quest.get("claimed"):
                    active.pop(str(quest.get("id")), None)
        for quest in quests:
            if str(quest.get("id")) not in active:
                continue
            quest["claimed"] = True
            quest["claimable"] = False
            quest["action"] = "done"

    def _orbs_value(self, balance: Any) -> int | None:
        if not isinstance(balance, int) or isinstance(balance, bool):
            return None
        with self._run_lock:
            bonus = self._orbs_bonus
            base = self._orbs_base
            if bonus and base is not None and balance != base:
                self._orbs_bonus = 0
                self._orbs_base = None
                bonus = 0
        return balance + bonus

    def list_quests(self, force: bool = False) -> dict[str, Any]:
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
        live = self._live_values(time.monotonic())
        for quest in quests:
            quest_id = quest.get("id")
            quest["queued"] = quest_id in queued_set
            if quest_id == playing or quest_id == watching:
                quest["state"] = "running"
                quest["action"] = "stop"
            credited = live.get(quest_id)
            if credited is None:
                continue

            quest["progress_seconds"] = max(
                int(quest.get("progress_seconds") or 0), int(credited)
            )
            target = int(quest.get("target_seconds") or 0)
            if target > 0:
                quest["progress"] = round(
                    min(1.0, quest["progress_seconds"] / target), 4
                )
        self._claim_overlay(quests)
        quests.sort(key=_sort_key)
        self._announce_completed(quests)

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
            "orbs": self._orbs_value(payload.get("orbs")),
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
        except Exception:
            return {}

    @staticmethod
    def _safe(call, default):
        try:
            return call()
        except Exception:
            return default

    def _decorate(
        self, quest: dict[str, Any], game, library_ids: set[int]
    ) -> dict[str, Any]:
        app_id = _application_id(quest.get("applicationId"))
        game_name = str(quest.get("gameName") or "Unknown game")
        kind = str(quest.get("kind") or "play")
        playable = kind == "play"
        watchable = kind in ("watch", "watch_mobile")

        executables: list[dict[str, Any]] = []
        icon_hash: str | None = None
        if game is not None and playable:
            icon_hash = game.icon_hash
            try:
                executables = self.manager.api.get_best_win32_executables(
                    game.executables
                )
            except Exception:
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
        claimed = bool(quest.get("claimedAt"))
        claimable = completed and not claimed

        enrolled = bool(quest.get("enrolledAt"))

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

        if completed and not claimed:
            action = "claim"
        elif completed or expired:
            action = "done"
        elif not playable and not watchable:
            action = "mobile"
        elif playable and app_id is None:
            action = "unsupported"
        else:
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
            "claimed": claimed,
            "claimable": claimable,
        }

    def quest_labels(self, quest_id: str) -> tuple[str, str]:
        quest = self._find(quest_id)
        if quest is None:
            return "", ""
        return str(quest.get("name") or ""), str(quest.get("game_name") or "")

    def _find(self, quest_id: str) -> dict[str, Any] | None:
        wanted = str(quest_id)
        for quest in self.list_quests().get("quests", []):
            if quest.get("id") == wanted:
                return quest
        for quest in self.list_quests(force=True).get("quests", []):
            if quest.get("id") == wanted:
                return quest
        return None

    def start_quest(self, quest_id: str) -> tuple[bool, str]:
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
            self._skipped.discard(quest_id)
            self._failures.pop(quest_id, None)
            playing = self._playing
        if playing == quest_id:
            return True, "That quest is already running"
        if playing is not None:
            added = self._enqueue(quest_id)
            self._start_monitor()
            if not added:
                return True, "That quest is already in the queue"
            return True, "Queued behind the running quest"

        if not quest.get("enrolled"):
            try:
                self.native.accept_quest(quest_id)
            except (DiscordNativeError, OSError) as exc:
                return False, f"Discord would not accept that quest: {exc}"
            quest["enrolled"] = True
            self.invalidate()

        return self._begin_play(quest, app_id)

    def accept_quest(self, quest_id: str) -> tuple[bool, str]:
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

    def claim_reward(self, quest_id: str) -> tuple[bool, str, bool]:
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list", False
        if quest.get("claimed"):
            return True, "That reward is already claimed", False
        if not quest.get("claimable"):
            return False, "That quest is not finished yet", False
        try:
            self.native.claim_quest_reward(quest_id)
        except QuestApiError as exc:
            if getattr(exc, "captcha", False):
                return (
                    False,
                    "Discord wants a captcha. Solve it in the Discord window.",
                    True,
                )
            detail = str(exc)
            code = getattr(exc, "code", None)
            if code:
                detail += f", code {code}"
            self._log(
                "warning",
                f"Discord refused the claim for {quest.get('name')!r}: {detail}",
            )
            return (
                False,
                (
                    f"Discord refused the claim ({detail}). "
                    "Claim it from Discord's Quests page."
                ),
                True,
            )
        except (DiscordNativeError, OSError) as exc:
            self._log(
                "warning",
                f"Could not reach Discord to claim {quest.get('name')!r}: {exc}",
            )
            return (
                False,
                f"Could not reach Discord ({exc}). Claim it in the Discord window.",
                True,
            )
        self._remember_claim(quest)
        self.invalidate()
        self._log("info", f"Claimed the reward for {quest.get('name')!r}")
        self._changed()
        return True, "Reward claimed", False

    def stop_quest(self, quest_id: str) -> tuple[bool, str]:
        with self._run_lock:
            watching = self._watching
            playing = self._playing
        if watching is not None and quest_id == watching:
            self._stop_watching(quest_id, "Stopped watching the video")
            return True, "Stopped watching the video"
        if playing is not None and quest_id == playing:
            self._stop_playing("Stopped the quest session", tail=False)
            return True, "Stopped the quest session"
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        return False, "That quest is not running"

    def prefs(self) -> dict[str, Any]:
        return quest_prefs.load(self.prefs_path)

    def update_prefs(self, values: dict[str, Any]) -> dict[str, Any]:
        return quest_prefs.save(values, self.prefs_path)

    def shutdown(self) -> None:
        with self._run_lock:
            self._live.clear()
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
        self._monitor_wake.set()
        with self._run_lock:
            self._playing = None
            self._playing_app = None
            self._playing_exe = ""
            self._playing_name = ""
            self._playing_reward = None
            self._activity_shown = False
            self._watching = None
            self._watching_name = ""
            self._watching_reward = None
            self._queue.clear()
            self._play_ready_at = 0.0
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0

    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        try:
            getattr(self.logger, level)(message)
        except (AttributeError, OSError):
            pass

    def _changed(self) -> None:
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception as exc:
            self._log("warning", f"Could not push the quest change: {exc}")

    @staticmethod
    def _reward_label(quest: dict[str, Any]) -> str | None:
        reward = quest.get("reward") or {}
        orbs = reward.get("orbs")
        if isinstance(orbs, int) and not isinstance(orbs, bool) and orbs > 0:
            return f"{orbs:,} Orbs"
        label = reward.get("label")
        return str(label) if label else None

    def _notify_finished(
        self, name: str, reward: str | None, quest_id: str | None = None
    ) -> None:
        key = str(quest_id) if quest_id else None
        if key is not None:
            with self._run_lock:
                if key in self._notified:
                    return
                self._notified.add(key)
        if self.notifier is None:
            return
        try:
            self.notifier.quest_finished(name, reward)
        except Exception as exc:
            self._log("warning", f"Could not announce the finished quest: {exc}")

    def _announce_completed(self, quests: list[dict[str, Any]]) -> None:
        for quest in quests:
            if quest.get("state") != "completed" or quest.get("claimed"):
                continue
            quest_id = quest.get("id")
            if not quest_id:
                continue
            reward = self._reward_label(quest)
            self._notify_finished(str(quest.get("name") or ""), reward, quest_id)

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

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from launcher.api import DiscordAPIError
from launcher.discord_native import DiscordNative, DiscordNativeError
from launcher.game_manager import GameManager

# How long a quest payload is reused before the client is asked again. The
# client only refreshes quests on its own schedule, so a shorter window would
# just cost a DevTools round-trip per repaint.
CACHE_TTL_SECONDS = 20.0

# Quest asset paths are relative to the media CDN root.
ASSET_BASE = "https://cdn.discordapp.com/"


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

    def __init__(
        self,
        game_manager: GameManager,
        native: DiscordNative | None = None,
        logger=None,
        ttl: float = CACHE_TTL_SECONDS,
    ):
        self.manager = game_manager
        self.native = native or DiscordNative(logger=logger)
        self.logger = logger
        self.ttl = ttl
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._fetched_at = 0.0

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
        for quest in quests:
            app = quest.get("application_id")
            quest["shares_game_with"] = max(0, shared[app] - 1) if app else 0
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
                "orbs": quest.get("rewardOrbs"),
                "premium_orbs": quest.get("rewardPremiumOrbs"),
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
            return False, (
                "Accept the quest in Discord first. Discord only counts "
                "play time for quests you have started there."
            )

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
        return ok, message

    def stop_quest(self, quest_id: str) -> tuple[bool, str]:
        quest = self._find(quest_id)
        if quest is None:
            return False, "That quest is no longer in Discord's list"
        app_id = _application_id(quest.get("application_id"))
        if app_id is None:
            return False, "Discord did not send an application id for that quest"
        return self.manager.stop_game(app_id)

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

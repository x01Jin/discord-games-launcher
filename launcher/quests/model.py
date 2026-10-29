from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

CACHE_TTL_SECONDS = 20.0
ASSET_BASE = "https://cdn.discordapp.com/"
WATCH_TIMEOUT_SECONDS = 1800.0
WATCH_REFRESH_SECONDS = 15.0
PLAY_BEAT_SECONDS = 20.0
PLAY_TIMEOUT_SECONDS = 4 * 3600.0

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

_STATE_ORDER = {
    "running": 0,
    "ready": 1,
    "expired": 2,
    "unresolved": 3,
    "completed": 4,
}

_KIND_ORDER = {"play": 0, "watch": 1, "watch_mobile": 2}


def _sort_key(quest: dict[str, Any]) -> tuple[int, int, float, str]:
    state = _STATE_ORDER.get(str(quest.get("state")), 5)
    kind = _KIND_ORDER.get(str(quest.get("kind")), 3)
    left = quest.get("seconds_left")
    horizon = float(left) if isinstance(left, int) else float("inf")
    return (state, kind, horizon, str(quest.get("name") or "").lower())

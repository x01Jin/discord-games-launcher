"""Quest run options the user can change from the app.

Their own small JSON file, not the SQLite database: two scalars read on every
quest start do not need a schema, and keeping the file next to the database
means a backup of the data directory carries them along.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

HIDE_ACTIVITY = "hide_activity"
PLAY_SESSION_TAIL_MIN = "play_session_tail_min"

# Discord's own default for showCurrentGame is on, and Orion ships the tail
# off-on-by-default debate settled at 2 minutes. Both match what the reference
# userscript calls its defaults.
DEFAULTS: dict[str, Any] = {
    HIDE_ACTIVITY: False,
    PLAY_SESSION_TAIL_MIN: 2,
}

MAX_TAIL_MINUTES = 30

_lock = threading.Lock()


def default_path() -> Path:
    """Where the settings file lives, overridable for tests."""
    override = os.environ.get("DCGL_DATA_DIR")
    base = Path(override) if override else Path(user_data_dir("discord-games-launcher", appauthor=False))
    return base / "settings.json"


def _clean(values: Any, base: dict[str, Any]) -> dict[str, Any]:
    """Return a full, valid settings dict built from *values* over *base*."""
    result = dict(base)
    if not isinstance(values, dict):
        return result

    hide = values.get(HIDE_ACTIVITY, result[HIDE_ACTIVITY])
    if isinstance(hide, bool):
        result[HIDE_ACTIVITY] = hide

    tail = values.get(PLAY_SESSION_TAIL_MIN, result[PLAY_SESSION_TAIL_MIN])
    if isinstance(tail, bool):
        pass
    elif isinstance(tail, int):
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, tail))
    elif isinstance(tail, float) and tail.is_integer():
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, int(tail)))
    elif isinstance(tail, str) and tail.strip().isdigit():
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, int(tail.strip())))
    return result


def load(path: Path | None = None) -> dict[str, Any]:
    """Current settings. A missing or corrupt file means the defaults."""
    target = path or default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return _clean(raw, dict(DEFAULTS))


def save(values: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Merge *values* into the stored settings and return the result."""
    target = path or default_path()
    with _lock:
        merged = _clean(values, load(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        return merged


def update(path: Path | None = None, **changes: Any) -> dict[str, Any]:
    return save(changes, path)


__all__ = [
    "DEFAULTS",
    "HIDE_ACTIVITY",
    "MAX_TAIL_MINUTES",
    "PLAY_SESSION_TAIL_MIN",
    "default_path",
    "load",
    "save",
    "update",
]

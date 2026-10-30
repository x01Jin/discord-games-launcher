from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

PLAY_SESSION_TAIL_MIN = "play_session_tail_min"
RUN_MODE = "run_mode"
TEST_MODE = "test_mode"

MODE_ACTIVITY = "activity"
MODE_SILENT = "silent"
RUN_MODES = (MODE_ACTIVITY, MODE_SILENT)

DEFAULTS: dict[str, Any] = {
    PLAY_SESSION_TAIL_MIN: 2,
    RUN_MODE: MODE_ACTIVITY,
    TEST_MODE: False,
}

MAX_TAIL_MINUTES = 30

_lock = threading.Lock()


def default_path() -> Path:
    override = os.environ.get("DCGL_DATA_DIR")
    base = Path(override) if override else Path(user_data_dir("discord-games-launcher", appauthor=False))
    return base / "settings.json"


def _clean(values: Any, base: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    if not isinstance(values, dict):
        return result

    tail = values.get(PLAY_SESSION_TAIL_MIN, result[PLAY_SESSION_TAIL_MIN])
    if isinstance(tail, bool):
        pass
    elif isinstance(tail, int):
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, tail))
    elif isinstance(tail, float) and tail.is_integer():
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, int(tail)))
    elif isinstance(tail, str) and tail.strip().isdigit():
        result[PLAY_SESSION_TAIL_MIN] = max(0, min(MAX_TAIL_MINUTES, int(tail.strip())))

    mode = values.get(RUN_MODE, result[RUN_MODE])
    if isinstance(mode, str) and mode.strip().lower() in RUN_MODES:
        result[RUN_MODE] = mode.strip().lower()

    test_mode = values.get(TEST_MODE, result[TEST_MODE])
    if isinstance(test_mode, bool):
        result[TEST_MODE] = test_mode
    return result


def load(path: Path | None = None) -> dict[str, Any]:
    target = path or default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return _clean(raw, dict(DEFAULTS))


def save(values: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
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
    "MAX_TAIL_MINUTES",
    "MODE_ACTIVITY",
    "MODE_SILENT",
    "PLAY_SESSION_TAIL_MIN",
    "RUN_MODE",
    "RUN_MODES",
    "TEST_MODE",
    "default_path",
    "load",
    "save",
    "update",
]

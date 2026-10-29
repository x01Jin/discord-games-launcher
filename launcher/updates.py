from __future__ import annotations

import re
import threading
import time
from typing import Any

import httpx

from launcher import __version__

REPO_URL = "https://github.com/x01Jin/discord-games-launcher"
RELEASES_URL = REPO_URL + "/releases/latest"
RELEASE_API = (
    "https://api.github.com/repos/x01Jin/discord-games-launcher/releases/latest"
)
CACHE_SECONDS = 60 * 60

_lock = threading.Lock()
_cache: tuple[float, dict[str, Any]] | None = None


def version_parts(value: str) -> tuple[int, ...]:
    match = re.match(r"^[vV]?(\d+(?:\.\d+)*)", value.strip())
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    left = version_parts(latest)
    right = version_parts(current)
    if not left or not right:
        return False
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)) > right + (0,) * (width - len(right))


def app_info() -> dict[str, Any]:
    return {
        "version": __version__,
        "repo_url": REPO_URL,
        "release_url": RELEASES_URL,
    }


def _fetch(timeout: float) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"DiscordGamesLauncher/{__version__}",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(RELEASE_API, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an unexpected release payload")
    return payload


def check(force: bool = False, timeout: float = 5.0) -> dict[str, Any]:
    global _cache
    now = time.monotonic()
    with _lock:
        if not force and _cache is not None and now - _cache[0] < CACHE_SECONDS:
            return dict(_cache[1])

    result = {
        **app_info(),
        "latest": None,
        "update_available": False,
        "error": None,
    }
    try:
        payload = _fetch(timeout)
        tag = str(payload.get("tag_name") or "").strip()
        if not tag:
            raise ValueError("GitHub returned no release tag")
        latest = tag.lstrip("vV")
        result["latest"] = latest
        result["release_url"] = str(payload.get("html_url") or RELEASES_URL)
        result["update_available"] = is_newer(latest, __version__)
    except (httpx.HTTPError, ValueError) as exc:
        result["error"] = str(exc)

    with _lock:
        _cache = (time.monotonic(), dict(result))
    return result

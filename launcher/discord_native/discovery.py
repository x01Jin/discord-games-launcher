from __future__ import annotations

import http.client
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psutil

from .errors import DiscordNativeError

_CHANNELS: tuple[tuple[str, str, str], ...] = (
    ("stable", "discord", "Discord"),
    ("ptb", "discordptb", "DiscordPTB"),
    ("canary", "discordcanary", "DiscordCanary"),
)

_DEFAULT_PORTS: tuple[int, ...] = (9222, 9223, 9224, 9229)

_DISCORD_HOSTS = ("discord.com", "canary.discord.com", "ptb.discord.com")


def _is_discord_page(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in _DISCORD_HOSTS or host.endswith(".discord.com")


@dataclass(frozen=True)
class DiscordInstall:
    channel: str
    user_data_dir: Path
    app_dir: Path | None
    exe_path: Path | None
    version: str | None


@dataclass(frozen=True)
class CdpTarget:
    port: int
    title: str
    url: str
    ws_url: str


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def _newest_app_dir(channel_dir: Path) -> tuple[Path | None, str | None]:
    if not channel_dir.is_dir():
        return None, None
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for entry in channel_dir.glob("app-*"):
        if not entry.is_dir():
            continue
        parts = entry.name[len("app-") :].split(".")
        try:
            key = tuple(int(p) for p in parts)
        except ValueError:
            continue
        candidates.append((key, entry))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0])
    key, path = candidates[-1]
    return path, ".".join(str(p) for p in key)


def find_installs() -> list[DiscordInstall]:
    installs: list[DiscordInstall] = []
    for channel, roam_name, exe_stem in _CHANNELS:
        user_data = _appdata() / roam_name
        channel_dir = _localappdata() / exe_stem
        app_dir, version = _newest_app_dir(channel_dir)
        exe_path = None
        if app_dir is not None:
            candidate = app_dir / f"{exe_stem}.exe"
            if candidate.is_file():
                exe_path = candidate
        if user_data.is_dir() or app_dir is not None:
            installs.append(
                DiscordInstall(
                    channel=channel,
                    user_data_dir=user_data,
                    app_dir=app_dir,
                    exe_path=exe_path,
                    version=version,
                )
            )
    return installs


def running_processes() -> list[psutil.Process]:
    found: list[psutil.Process] = []
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if not name.startswith("discord"):
            continue
        if name in ("discordcrashhandler.exe", "discordcrashpad.exe"):
            continue
        found.append(proc)
    return found


def is_running() -> bool:
    return bool(running_processes())


def _listening_ports(pids: Iterable[int]) -> list[int]:
    wanted = set(pids)
    ports: list[int] = []
    for proc in psutil.process_iter(["pid"]):
        if proc.info.get("pid") not in wanted:
            continue
        try:
            connections = proc.net_connections(kind="tcp")
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
        for conn in connections:
            if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                continue
            port = conn.laddr.port
            if port not in ports:
                ports.append(port)
    return ports


def _http_json(port: int, path: str = "/json/list", timeout: float = 1.0) -> Any:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read()
        if response.status != 200:
            raise DiscordNativeError(f"HTTP {response.status} from port {port}")
        return json.loads(body.decode("utf-8", "replace"))
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise DiscordNativeError(str(exc)) from exc
    finally:
        conn.close()

_MAIN_ROUTES = ("/channels", "/quest-home", "/store", "/library", "/login")
_AUXILIARY_ROUTES = ("/popout", "/overlay", "/ptt", "/devtools")


def _route_rank(url: str) -> int:
    path = urlsplit(url).path or "/"
    if path.startswith(_AUXILIARY_ROUTES):
        return 2
    if path.startswith(_MAIN_ROUTES):
        return 0
    return 1


def find_targets(ports: Iterable[int]) -> tuple[list[CdpTarget], str | None]:
    found: list[CdpTarget] = []
    last_error: str | None = None
    for port in ports:
        try:
            targets = _http_json(port)
        except DiscordNativeError as exc:
            last_error = f"port {port}: {exc}"
            continue
        if not isinstance(targets, list):
            continue
        answered = False
        for entry in targets:
            if not isinstance(entry, dict) or entry.get("type") != "page":
                continue
            if not entry.get("webSocketDebuggerUrl"):
                continue
            url = str(entry.get("url") or "")
            if not _is_discord_page(url):
                continue
            answered = True
            found.append(
                CdpTarget(
                    port=port,
                    title=str(entry.get("title") or ""),
                    url=url,
                    ws_url=str(entry.get("webSocketDebuggerUrl")),
                )
            )
        if answered:
            break
        last_error = f"port {port}: endpoint answered but has no Discord renderer"
    found.sort(key=lambda target: (_route_rank(target.url), target.port))
    return found, (last_error if not found else None)


def find_target(ports: Iterable[int]) -> tuple[CdpTarget | None, str | None]:
    targets, error = find_targets(ports)
    return (targets[0] if targets else None), error

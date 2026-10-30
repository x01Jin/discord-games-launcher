from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import winreg
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SILENT_PORT = 9223
SWITCH = "--remote-debugging-port="
_PROCESS_START = "--processStart"
_START_ARGS = "--process-start-args"
_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "Discord"
_CACHE_TTL = 20.0
_REAPPLY_INTERVAL = 120.0

_NO_WINDOW = 0x08000000

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"at": 0.0, "launchers": []}
_LAST_REAPPLY = 0.0


@dataclass(frozen=True)
class Launcher:
    kind: str
    location: str
    target: str
    arguments: str

    @property
    def patched(self) -> bool:
        return _port_of(self.arguments) is not None

    @property
    def label(self) -> str:
        return f"{self.kind}: {self.location}"


def _port_of(arguments: str) -> int | None:
    for token in (arguments or "").replace('"', " ").split():
        if token.startswith(SWITCH):
            raw = token[len(SWITCH):].strip('"')
            if raw.isdigit():
                return int(raw)
    return None


def _strip_switch(arguments: str) -> str:
    return " ".join(
        token
        for token in (arguments or "").replace('"', " ").split()
        if not token.startswith(SWITCH)
    ).strip()


def _is_launcher(target: str, arguments: str) -> bool:
    if _PROCESS_START in (arguments or ""):
        return True
    name = Path(target).name.lower() if target else ""
    return name in {"update.exe", "discord.exe"} and Path(target).parent.name.lower() == "discord"


def with_switch(arguments: str, target: str = "", port: int = SILENT_PORT) -> str:
    args = (arguments or "").strip()
    existing = _port_of(args)
    if existing == port:
        return args
    if existing is not None:
        args = _strip_switch(args)

    if _START_ARGS in args:
        head, tail = args.split(_START_ARGS, 1)
        inner = _strip_switch(tail.strip().strip('"'))
        combined = f"{inner} {SWITCH}{port}".strip()
        return f'{head.strip()} {_START_ARGS} "{combined}"'

    if _is_launcher(target, args):
        if _PROCESS_START not in args:
            args = f"{args} {_PROCESS_START} Discord.exe".strip()
        return f'{args} {_START_ARGS} "{SWITCH}{port}"'

    return f"{args} {SWITCH}{port}".strip()


def without_switch(arguments: str) -> str:
    args = (arguments or "").strip()
    if _port_of(args) is None:
        return args
    if _START_ARGS in args:
        head, tail = args.split(_START_ARGS, 1)
        inner = _strip_switch(tail.strip().strip('"'))
        if inner:
            return f'{head.strip()} {_START_ARGS} "{inner}"'
        return head.strip()
    return _strip_switch(args)


def shortcut_path() -> str | None:
    launchers = discover()
    for kind in ("Start menu", "Taskbar", "Desktop"):
        for launcher in launchers:
            if launcher.kind != kind or not launcher.location:
                continue
            if Path(launcher.location).is_file():
                return launcher.location
    return None


def _shortcut_paths() -> list[tuple[str, Path]]:
    appdata = Path(os.environ.get("APPDATA") or "")
    user = Path(os.environ.get("USERPROFILE") or Path.home())
    public = Path(os.environ.get("PUBLIC") or "C:/Users/Public")
    found: list[tuple[str, Path]] = []

    programs = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if programs.is_dir():
        for path in sorted(programs.rglob("Discord.lnk")):
            found.append(("Start menu", path))

    startup = programs / "Startup"
    if startup.is_dir():
        for path in sorted(startup.glob("Discord*.lnk")):
            found.append(("Startup", path))

    desktop = user / "Desktop" / "Discord.lnk"
    if desktop.is_file():
        found.append(("Desktop", desktop))
    shared = public / "Desktop" / "Discord.lnk"
    if shared.is_file():
        found.append(("Desktop", shared))

    pinned = (
        appdata
        / "Microsoft"
        / "Internet Explorer"
        / "Quick Launch"
        / "User Pinned"
        / "TaskBar"
        / "Discord.lnk"
    )
    if pinned.is_file():
        found.append(("Taskbar", pinned))

    seen: set[str] = set()
    unique: list[tuple[str, Path]] = []
    for kind, path in found:
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append((kind, path))
    return unique

_READ_SHORTCUTS = r'''
$paths = @()
foreach ($item in ($env:DCGL_LNK_PATHS | ConvertFrom-Json)) { $paths += $item }
$shell = New-Object -ComObject WScript.Shell
$rows = @()
foreach ($path in $paths) {
  if (-not (Test-Path -LiteralPath $path)) { continue }
  try {
    $lnk = $shell.CreateShortcut($path)
    $rows += [pscustomobject]@{
      path      = [string]$path
      target    = [string]$lnk.TargetPath
      arguments = [string]$lnk.Arguments
    }
  } catch { }
}
if ($rows.Count -eq 0) { Write-Output "[]"; exit 0 }
$parts = foreach ($row in $rows) { $row | ConvertTo-Json -Compress -Depth 4 }
Write-Output ("[" + ($parts -join ",") + "]")
'''

_WRITE_SHORTCUTS = r'''
$patches = @()
foreach ($item in ($env:DCGL_LNK_PATCH | ConvertFrom-Json)) { $patches += $item }
$shell = New-Object -ComObject WScript.Shell
$rows = @()
foreach ($patch in $patches) {
  try {
    $lnk = $shell.CreateShortcut([string]$patch.path)
    $lnk.Arguments = [string]$patch.arguments
    $lnk.Save()
    $rows += [pscustomobject]@{ path = [string]$patch.path; ok = $true; error = "" }
  } catch {
    $rows += [pscustomobject]@{
      path  = [string]$patch.path
      ok    = $false
      error = $_.Exception.Message
    }
  }
}
if ($rows.Count -eq 0) { Write-Output "[]"; exit 0 }
$parts = foreach ($row in $rows) { $row | ConvertTo-Json -Compress -Depth 4 }
Write-Output ("[" + ($parts -join ",") + "]")
'''


def _powershell(script: str, extra_env: dict[str, str] | None = None, timeout: float = 30.0) -> str:
    if sys.platform != "win32":
        raise OSError("Discord launcher setup is Windows only")
    env = os.environ.copy()
    env.update(extra_env or {})
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            creationflags=_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError(f"Could not run the shortcut helper: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise OSError(detail or "PowerShell failed")
    return completed.stdout


def _read_shortcuts(paths: list[Path]) -> list[dict[str, str]]:
    if not paths:
        return []
    raw = _powershell(
        _READ_SHORTCUTS,
        {"DCGL_LNK_PATHS": json.dumps([str(path) for path in paths])},
    )
    try:
        rows = json.loads(raw or "[]")
    except ValueError as exc:
        raise OSError("Could not read the Discord shortcuts") from exc
    return [row for row in rows if isinstance(row, dict)]


def _read_run_key() -> Launcher | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH) as key:
            value, _kind = winreg.QueryValueEx(key, _RUN_VALUE)
    except OSError:
        return None
    if not isinstance(value, str) or "discord" not in value.lower():
        return None
    arguments = value.strip()
    target = ""
    if arguments.startswith('"'):
        closing = arguments.find('"', 1)
        if closing > 0:
            target = arguments[1:closing]
            arguments = arguments[closing + 1:].strip()
    else:
        parts = arguments.split(" ", 1)
        target = parts[0]
        arguments = parts[1].strip() if len(parts) > 1 else ""
    return Launcher("Start with Windows", "HKCU Run", target, arguments)


def _write_run_key(launcher: Launcher) -> None:
    command = f'"{launcher.target}" {launcher.arguments}'.strip()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, command)


def discover() -> list[Launcher]:
    with _LOCK:
        cached = _CACHE["launchers"]
        if cached and time.monotonic() - _CACHE["at"] < _CACHE_TTL:
            return list(cached)

    launchers: list[Launcher] = []
    run_key = _read_run_key()
    if run_key is not None:
        launchers.append(run_key)

    paths = _shortcut_paths()
    if paths:
        rows = _read_shortcuts([path for _kind, path in paths])
        by_path = {os.path.normcase(str(row.get("path") or "")): row for row in rows}
        for kind, path in paths:
            row = by_path.get(os.path.normcase(str(path)))
            if row is None:
                continue
            launchers.append(
                Launcher(
                    kind,
                    str(path),
                    str(row.get("target") or ""),
                    str(row.get("arguments") or ""),
                )
            )

    with _LOCK:
        _CACHE["launchers"] = list(launchers)
        _CACHE["at"] = time.monotonic()
    return list(launchers)


def _invalidate_cache() -> None:
    with _LOCK:
        _CACHE["launchers"] = []
        _CACHE["at"] = 0.0


def _marker_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "discord-games-launcher" / "silent_mode.json"


def _read_marker() -> dict[str, Any]:
    try:
        with _marker_path().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_marker(data: dict[str, Any]) -> None:
    path = _marker_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
    except OSError:
        pass


def _apply(launchers: list[Launcher], port: int) -> tuple[list[str], list[str]]:
    updates: list[tuple[Launcher, str]] = []
    for launcher in launchers:
        wanted = with_switch(launcher.arguments, launcher.target, port)
        if wanted != (launcher.arguments or "").strip():
            updates.append((launcher, wanted))

    if not updates:
        return [], []

    updated: list[str] = []
    failures: list[str] = []

    for launcher, wanted in updates:
        if launcher.kind != "Start with Windows":
            continue
        try:
            _write_run_key(
                Launcher(launcher.kind, launcher.location, launcher.target, wanted)
            )
            updated.append(launcher.label)
        except OSError as exc:
            failures.append(f"{launcher.label} ({exc})")

    shortcuts = [
        (launcher, wanted)
        for launcher, wanted in updates
        if launcher.kind != "Start with Windows"
    ]
    if shortcuts:
        payload = json.dumps(
            [{"path": launcher.location, "arguments": wanted} for launcher, wanted in shortcuts]
        )
        try:
            rows = json.loads(_powershell(_WRITE_SHORTCUTS, {"DCGL_LNK_PATCH": payload}) or "[]")
        except (OSError, ValueError) as exc:
            failures.append(f"shortcuts ({exc})")
            rows = []
        results = {
            os.path.normcase(str(row.get("path") or "")): row
            for row in rows
            if isinstance(row, dict)
        }
        for launcher, _wanted in shortcuts:
            row = results.get(os.path.normcase(launcher.location))
            if row is None:
                failures.append(f"{launcher.label} (no result)")
            elif row.get("ok"):
                updated.append(launcher.label)
            else:
                failures.append(f"{launcher.label} ({row.get('error') or 'failed'})")

    _invalidate_cache()
    return updated, failures


def enable(port: int = SILENT_PORT) -> dict[str, Any]:
    launchers = discover()
    if not launchers:
        return {
            "ok": False,
            "message": "No Discord shortcut or startup entry was found to update.",
            "updated": [],
            "failed": [],
        }

    updated, failures = _apply(launchers, port)
    _write_marker({"enabled": True, "port": port, "at": time.time()})
    state = summary(port)
    if failures and not state["enabled"]:
        return {
            "ok": False,
            "message": "Some launchers could not be updated: " + "; ".join(failures),
            "updated": updated,
            "failed": failures,
        }
    message = (
        "Every Discord launcher now starts the client with the endpoint."
        if not failures
        else "Updated what Windows allowed; some launchers were left alone."
    )
    return {"ok": True, "message": message, "updated": updated, "failed": failures}


def disable() -> dict[str, Any]:
    launchers = discover()
    restored: list[str] = []
    failures: list[str] = []

    for launcher in launchers:
        if not launcher.patched:
            continue
        wanted = without_switch(launcher.arguments)
        if launcher.kind == "Start with Windows":
            try:
                _write_run_key(
                    Launcher(launcher.kind, launcher.location, launcher.target, wanted)
                )
                restored.append(launcher.label)
            except OSError as exc:
                failures.append(f"{launcher.label} ({exc})")

    shortcuts = [
        launcher
        for launcher in launchers
        if launcher.patched and launcher.kind != "Start with Windows"
    ]
    if shortcuts:
        payload = json.dumps(
            [
                {"path": launcher.location, "arguments": without_switch(launcher.arguments)}
                for launcher in shortcuts
            ]
        )
        try:
            rows = json.loads(_powershell(_WRITE_SHORTCUTS, {"DCGL_LNK_PATCH": payload}) or "[]")
        except (OSError, ValueError) as exc:
            failures.append(f"shortcuts ({exc})")
            rows = []
        for row in rows:
            if isinstance(row, dict) and not row.get("ok"):
                failures.append(f"{row.get('path')} ({row.get('error') or 'failed'})")
            elif isinstance(row, dict):
                restored.append("Start menu: " + str(row.get("path")))

    previous = _read_marker()
    remembered = previous.get("port")
    port = remembered if isinstance(remembered, int) else SILENT_PORT
    _write_marker({"enabled": False, "port": port, "at": time.time()})
    _invalidate_cache()
    return {"ok": not failures, "restored": restored, "failed": failures}


def summary(port: int = SILENT_PORT) -> dict[str, Any]:
    launchers = discover()
    patched = [launcher for launcher in launchers if launcher.patched]
    patched_ports = {
        found for found in (_port_of(launcher.arguments) for launcher in patched) if found is not None
    }
    marker = _read_marker()
    remembered = marker.get("port")
    fallback = remembered if isinstance(remembered, int) else port
    active_port = (
        next(iter(patched_ports))
        if patched
        and len(patched) == len(launchers)
        and len(patched_ports) == 1
        else fallback
    )
    return {
        "port": active_port,
        "enabled": bool(launchers) and len(patched) == len(launchers),
        "wanted": bool(marker.get("enabled")),
        "patched": len(patched),
        "total": len(launchers),
        "launchers": [
            {
                "kind": launcher.kind,
                "location": launcher.location,
                "target": launcher.target,
                "arguments": launcher.arguments,
                "patched": launcher.patched,
            }
            for launcher in launchers
        ],
    }


def heal(port: int = SILENT_PORT) -> bool:
    global _LAST_REAPPLY
    if sys.platform != "win32":
        return False
    if not _read_marker().get("enabled"):
        return False
    now = time.monotonic()
    if now - _LAST_REAPPLY < _REAPPLY_INTERVAL:
        return False

    launchers = discover()
    if not launchers or all(launcher.patched for launcher in launchers):
        return False

    _LAST_REAPPLY = now
    updated, _failures = _apply(launchers, port)
    return bool(updated)

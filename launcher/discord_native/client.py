from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psutil

from launcher import discord_setup

from .cdp import CdpConnection
from .discovery import (
    _DEFAULT_PORTS,
    CdpTarget,
    DiscordInstall,
    _listening_ports,
    find_installs,
    find_target,
    find_targets,
    is_running,
    running_processes,
)
from .errors import DiscordNativeError, QuestApiError
from .renderer import (
    ACTIVITY_EXPRESSION,
    ACTIVITY_STATE_EXPRESSION,
    CLAIM_CLICK_EXPRESSION,
    NAVIGATE_QUESTS_EXPRESSION,
    QUEST_API_EXPRESSION,
    QUESTS_EXPRESSION,
    parse_quest_payload,
)


class DiscordNative:
    def __init__(self, logger=None, port: int | None = None):
        self.logger = logger
        self.port = port or int(os.environ.get("DCGL_DISCORD_CDP_PORT") or 0) or None
        self._last_error: str | None = None
        self._last_target: CdpTarget | None = None

    def install(self) -> DiscordInstall | None:
        installs = find_installs()
        if not installs:
            return None
        for install in installs:
            if install.channel == "stable":
                return install
        return installs[0]

    def candidate_ports(self) -> Iterator[int]:
        seen: set[int] = set()

        def fresh(port: int) -> bool:
            if port in seen:
                return False
            seen.add(port)
            return True

        if self.port and fresh(self.port):
            yield self.port
        if self._last_target and fresh(self._last_target.port):
            yield self._last_target.port

        processes = running_processes()
        for proc in processes:
            try:
                argv = proc.cmdline()
            except (psutil.Error, OSError):
                continue
            for argument in argv:
                if not argument.startswith("--remote-debugging-port="):
                    continue
                raw = argument.split("=", 1)[1]
                if raw.isdigit() and fresh(int(raw)):
                    yield int(raw)

        for port in _DEFAULT_PORTS:
            if fresh(port):
                yield port

        for port in _listening_ports(proc.pid for proc in processes):
            if fresh(port):
                yield port

    def target(self) -> CdpTarget | None:
        target, error = find_target(self.candidate_ports())
        self._last_target = target
        self._last_error = error if target is None else None
        return target

    def status(self) -> dict[str, Any]:
        install = self.install()
        running = is_running()
        target = self.target() if running else None
        silent = discord_setup.summary()
        if running and target is None:
            discord_setup.heal(self.port or silent["port"])
        return {
            "installed": install is not None,
            "running": running,
            "connected": target is not None,
            "channel": install.channel if install else None,
            "version": install.version if install else None,
            "exe_path": str(install.exe_path) if install and install.exe_path else None,
            "debug_port": target.port if target else None,
            "title": target.title if target else None,
            "url": target.url if target else None,
            "error": self._last_error,
            "silent": silent["enabled"],
            "silent_wanted": silent["wanted"],
            "silent_port": silent["port"],
            "hint": self._hint(install, running, target, silent["enabled"]),
        }

    @staticmethod
    def _hint(
        install: DiscordInstall | None,
        running: bool,
        target: CdpTarget | None,
        silent: bool = False,
    ) -> str:
        if install is None:
            return "Discord is not installed for this user."
        if not running:
            return "Open Discord to read your quests."
        if target is None:
            if silent:
                return (
                    "The endpoint is on every Discord launcher. Close and reopen "
                    "Discord once."
                )
            return (
                "Discord is running without the endpoint. Patching the launch "
                "entries and restarting Discord once turns it on."
            )
        return "Connected to the running Discord client."

    def read_quests(self) -> dict[str, Any]:
        targets, error = find_targets(self.candidate_ports())
        if not targets:
            self._last_error = error
            raise DiscordNativeError(
                "Discord's endpoint is closed. Patch the launch entries and "
                "restart Discord once to open it."
            )

        last_error: str | None = None
        for target in targets[:4]:
            try:
                with CdpConnection(target.ws_url) as connection:
                    value = connection.evaluate(QUESTS_EXPRESSION, timeout=12.0)
                payload = parse_quest_payload(value)
            except DiscordNativeError as exc:
                last_error = str(exc)
                continue
            self._last_target = target
            self._last_error = None
            payload["port"] = target.port
            payload["title"] = target.title
            return payload

        self._last_error = last_error
        raise DiscordNativeError(last_error or "Discord did not return a quest list")

    def show_game_activity(
        self, application_id: int | str, name: str
    ) -> dict[str, Any]:
        expression = (
            ACTIVITY_EXPRESSION.replace("__DCGL_ACTION__", json.dumps("show"))
            .replace("__DCGL_APP_ID__", json.dumps(str(application_id)))
            .replace("__DCGL_GAME_NAME__", json.dumps(str(name)))
        )
        return self._activity(expression)

    def clear_game_activity(self) -> None:
        expression = (
            ACTIVITY_EXPRESSION.replace("__DCGL_ACTION__", json.dumps("clear"))
            .replace("__DCGL_APP_ID__", json.dumps(""))
            .replace("__DCGL_GAME_NAME__", json.dumps(""))
        )
        self._activity(expression)

    def activity_state(self, application_id: int | str) -> dict[str, Any] | None:
        expression = ACTIVITY_STATE_EXPRESSION.replace(
            "__DCGL_APP_ID__", json.dumps(str(application_id))
        )
        try:
            value = self._evaluate_on_client(expression, timeout=8.0)
        except (DiscordNativeError, OSError):
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return None
        if not isinstance(value, dict) or not value.get("ok", True):
            return None
        return {"shown": value.get("shown")}

    def _activity(self, expression: str, timeout: float = 10.0) -> dict[str, Any]:
        value = self._evaluate_on_client(expression, timeout=timeout)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError as exc:
                raise DiscordNativeError(
                    "Discord returned an unreadable activity answer"
                ) from exc
        if not isinstance(value, dict):
            raise DiscordNativeError("Discord returned an unexpected activity answer")
        if not value.get("ok"):
            raise DiscordNativeError(
                str(value.get("error") or "Discord refused the game activity")
            )
        return value

    def _evaluate_on_client(self, expression: str, timeout: float = 8.0) -> Any:
        targets, error = find_targets(self.candidate_ports())
        if not targets:
            raise DiscordNativeError(
                error or "Discord's local DevTools endpoint is not open"
            )
        last_error: str | None = None
        for target in targets[:4]:
            try:
                with CdpConnection(target.ws_url) as connection:
                    value = connection.evaluate(expression, timeout=timeout)
            except DiscordNativeError as exc:
                last_error = str(exc)
                continue
            self._last_target = target
            self._last_error = None
            return value
        self._last_error = last_error
        raise DiscordNativeError(last_error or "Discord did not answer")

    def _quest_api(self, op: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
        expression = QUEST_API_EXPRESSION.replace("__DCGL_OP__", json.dumps(op))
        value = self._evaluate_on_client(expression, timeout=timeout)
        if isinstance(value, str):
            try:
                payload = json.loads(value)
            except ValueError as exc:
                raise DiscordNativeError(
                    "Discord returned an unreadable quest answer"
                ) from exc
        elif isinstance(value, dict):
            payload = value
        else:
            raise DiscordNativeError("Discord returned an unexpected quest answer")
        if not payload.get("ok"):
            raise QuestApiError(
                str(payload.get("error") or "Discord refused the quest request"),
                captcha=bool(payload.get("captcha")),
                code=payload.get("code"),
                status=payload.get("status"),
            )
        return payload

    def accept_quest(self, quest_id: str) -> dict[str, Any]:
        return self._quest_api({"kind": "enroll", "questId": str(quest_id)})

    def send_video_progress(
        self, quest_id: str, timestamp: float, task_key: str | None = None
    ) -> dict[str, Any]:
        return self._quest_api(
            {
                "kind": "video",
                "questId": str(quest_id),
                "timestamp": round(float(timestamp), 6),
                "taskKey": str(task_key or ""),
            }
        )

    def send_heartbeat(
        self,
        quest_id: str,
        application_id: int | str,
        executable_path: str,
        terminal: bool = False,
        task_key: str | None = None,
    ) -> dict[str, Any]:
        return self._quest_api(
            {
                "kind": "heartbeat",
                "questId": str(quest_id),
                "applicationId": str(application_id),
                "executablePath": str(executable_path),
                "terminal": bool(terminal),
                "taskKey": str(task_key or ""),
            }
        )

    def claim_quest_reward(self, quest_id: str) -> dict[str, Any]:
        return self._quest_api({"kind": "claim", "questId": str(quest_id)})

    def open_quest_page(self) -> bool:
        value = self._evaluate_on_client(NAVIGATE_QUESTS_EXPRESSION, timeout=8.0)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return False
        return bool(isinstance(value, dict) and value.get("ok"))

    def click_claim_reward(
        self, quest_id: str, name: str, alt_name: str = ""
    ) -> dict[str, Any]:
        names = []
        for candidate in (name, alt_name):
            text = str(candidate or "")
            if text and text not in names:
                names.append(text)
        expression = (
            CLAIM_CLICK_EXPRESSION.replace(
                "__DCGL_QUEST_NAMES__", json.dumps(names)
            ).replace("__DCGL_QUEST_ID__", json.dumps(str(quest_id)))
        )
        value = self._evaluate_on_client(expression, timeout=10.0)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return {"ok": False, "reason": "unreadable"}
        if not isinstance(value, dict):
            return {"ok": False, "reason": "unexpected"}
        return value

    def endpoint_port(self) -> int:
        if self.port:
            return self.port
        target = self.target()
        if target is not None:
            return target.port
        try:
            state = discord_setup.summary()
        except (OSError, ValueError):
            return discord_setup.SILENT_PORT
        port = state.get("port")
        return int(port) if isinstance(port, int) else discord_setup.SILENT_PORT

    def start(self, wait_seconds: float = 45.0) -> tuple[bool, str]:
        target = self.target()
        if target is not None:
            return True, f"Already connected to Discord on port {target.port}"

        install = self.install()
        if install is None or install.exe_path is None:
            return False, "Discord is not installed for this user."
        if is_running():
            return False, "Discord is already running."

        try:
            self._launch(install)
        except OSError as exc:
            return False, f"Could not start Discord: {exc}"
        return self._await_connection(wait_seconds, "started")

    def restart(self, wait_seconds: float = 30.0) -> tuple[bool, str]:
        target = self.target()
        if target is not None:
            return True, f"Already connected to Discord on port {target.port}"

        install = self.install()
        if install is None or install.exe_path is None:
            return False, "Discord is not installed for this user."
        if not is_running():
            return self.start(wait_seconds=wait_seconds)

        try:
            self._stop_client(install)
        except (psutil.Error, OSError) as exc:
            if self.logger:
                self.logger.warning(f"Could not close Discord cleanly: {exc}")

        try:
            self._launch(install)
        except OSError as exc:
            return False, f"Could not start Discord: {exc}"

        return self._await_connection(wait_seconds, "restarted")

    def restart_without_endpoint(self) -> tuple[bool, str]:
        install = self.install()
        if install is None or install.exe_path is None:
            return False, "Discord is not installed for this user."
        if not is_running():
            return True, "Discord is not running."

        try:
            self._stop_client(install)
        except (psutil.Error, OSError) as exc:
            return False, f"Could not close Discord: {exc}"

        try:
            self._launch(install)
        except OSError as exc:
            return False, f"Could not start Discord: {exc}"

        if self._await_process():
            return True, "Discord restarted."
        return False, "Discord did not start again after the restart."

    def _await_process(self, timeout: float = 20.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if is_running():
                return True
            time.sleep(0.5)
        return False

    def _await_connection(self, wait_seconds: float, closing: str) -> tuple[bool, str]:
        deadline = time.monotonic() + wait_seconds
        missing = 0
        while time.monotonic() < deadline:
            target = self.target()
            if target is not None:
                return self._await_quests(target.port, wait_seconds, closing=closing)
            if is_running():
                missing = 0
            else:
                missing += 1
                if missing >= 4:
                    return False, f"Discord {closing} and then exited."
            time.sleep(0.5)
        if is_running():
            return True, (
                f"Discord {closing}, but it has no endpoint. The launch patch is "
                "off or its entries were not updated."
            )
        return False, f"Discord {closing} and then exited."

    def _await_quests(
        self,
        port: int,
        wait_seconds: float,
        closing: str = "started",
    ) -> tuple[bool, str]:
        deadline = time.monotonic() + wait_seconds
        opened = False
        missing = 0
        while time.monotonic() < deadline:
            target, _error = find_target([port])
            if target is not None:
                self.port = port
                opened = True
                break

            if is_running():
                missing = 0
            else:
                missing += 1
                if missing >= 4:
                    break
            time.sleep(0.5)
        if not opened:
            if not is_running():
                return False, (
                    f"Discord {closing} and then exited. A stale instance or a "
                    "pending update is the usual cause; try Connect again."
                )
            return False, (
                f"Discord {closing} but did not open a DevTools endpoint. "
                "Check that no other process is holding the port."
            )

        answered: float | None = None
        while time.monotonic() < deadline:
            try:
                payload = self.read_quests()
            except DiscordNativeError:
                time.sleep(0.75)
                continue
            if int(payload.get("questCount") or 0) > 0:
                return True, f"Connected to Discord on port {port}"
            if answered is None:
                answered = time.monotonic()
            if time.monotonic() - answered > 8.0:
                return True, f"Connected to Discord on port {port}"
            time.sleep(0.75)
        return True, (
            f"Discord is on port {port} but has not listed quests yet. "
            "Refresh in a few seconds."
        )

    def _stop_client(self, install: DiscordInstall) -> None:
        root = install.app_dir.parent if install.app_dir is not None else None
        victims: list[psutil.Process] = []
        for proc in running_processes():
            try:
                exe = proc.exe()
            except (psutil.Error, OSError):
                exe = ""
            if root is not None and exe:
                try:
                    Path(exe).relative_to(root)
                except ValueError:
                    continue
            victims.append(proc)

        self._request_close(victims)
        try:
            _gone, alive = psutil.wait_procs(victims, timeout=8)
        except (psutil.Error, OSError):
            alive = victims

        for proc in alive:
            try:
                proc.terminate()
            except (psutil.Error, OSError):
                continue

        try:
            alive = psutil.wait_procs(alive, timeout=5)[1]
        except (psutil.Error, OSError):
            pass

        for proc in alive:
            try:
                if proc.is_running():
                    proc.kill()
            except (psutil.Error, OSError):
                continue
        time.sleep(1.0)

        if self.logger:
            self.logger.info(f"Stopped {len(victims)} Discord process(es)")

    @staticmethod
    def _request_close(victims: list[psutil.Process]) -> None:
        if sys.platform != "win32" or not victims:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
        except (ImportError, OSError, AttributeError):
            return
        try:
            user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.DWORD),
            ]
            user32.PostMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
        except (AttributeError, OSError):
            return

        pids = {proc.pid for proc in victims}
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _lparam):
            pid = wintypes.DWORD()
            try:
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pids:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
            except (OSError, AttributeError, ValueError):
                return True
            return True

        try:
            user32.EnumWindows(callback_type(visit), 0)
        except (OSError, AttributeError, ValueError):
            pass

    def _launch(self, install: DiscordInstall) -> None:
        shortcut = None
        if sys.platform == "win32":
            try:
                shortcut = discord_setup.shortcut_path()
            except (OSError, ValueError):
                shortcut = None
        if shortcut is not None:
            os.startfile(shortcut)
            if self.logger:
                self.logger.info(f"Opened Discord from {shortcut}")
            return

        if install.exe_path is None or install.app_dir is None:
            raise OSError("Discord executable not found")
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        updater = install.app_dir.parent / "Update.exe"
        if updater.is_file():
            command = [str(updater), "--processStart", install.exe_path.name]
            cwd = str(updater.parent)
        else:
            command = [str(install.exe_path)]
            cwd = str(install.exe_path.parent)
        subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        if self.logger:
            self.logger.info(f"Started Discord ({Path(command[0]).name})")

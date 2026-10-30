from __future__ import annotations

import os
import sys
import time

from launcher import discord_native
from launcher.discord_native import DiscordNativeError


def _focus_discord() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]

        pids = {proc.pid for proc in discord_native.running_processes()}
        if not pids:
            return False

        found: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if (
                pid.value in pids
                and user32.IsWindowVisible(hwnd)
                and user32.GetWindowTextLengthW(hwnd) > 0
            ):
                found.append(hwnd)
            return True

        user32.EnumWindows(callback_type(visit), 0)
        if not found:
            return False
        if user32.IsIconic(found[0]):
            user32.ShowWindow(found[0], 9)
        user32.SetForegroundWindow(found[0])
        return True
    except (OSError, AttributeError, ValueError) as exc:
        print(f"[dcgl] Could not focus Discord: {exc}", file=sys.stderr)
        return False


def claim_in_client(service, quest_id: str, message: str, emit) -> bool:
    native = getattr(service, "native", None) if service is not None else None
    pressed = False
    if native is not None:
        try:
            native.open_quest_page()
        except (DiscordNativeError, OSError):
            pass
        try:
            name, game_name = service.quest_labels(quest_id)
        except (DiscordNativeError, OSError, ValueError):
            name, game_name = "", ""
        for _attempt in range(14):
            if not name and not game_name:
                break
            try:
                result = native.click_claim_reward(quest_id, name, game_name)
            except (DiscordNativeError, OSError):
                break
            if result.get("ok"):
                pressed = True
                service.invalidate()
                emit({"type": "quests_changed"})
                break
            if result.get("reason") == "ambiguous":
                break
            time.sleep(0.75)
    _focus_discord()
    if pressed:
        return True
    notifier = getattr(service, "notifier", None)
    if notifier is not None:
        try:
            notifier.claim_needs_action(message)
        except (AttributeError, OSError):
            pass
    return False

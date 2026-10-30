from __future__ import annotations

import ctypes
import json
import os
import struct
import time
from ctypes import wintypes
from typing import Any

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_INVALID_HANDLE = wintypes.HANDLE(-1).value
_PIPE_PREFIX = "\\\\.\\pipe\\discord-ipc-"
_MAX_INSTANCES = 10
_HANDSHAKE_TIMEOUT = 2.0
_OP_HANDSHAKE = 0
_OP_FRAME = 1


class RpcError(Exception):
    pass

if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    _kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    _kernel32.PeekNamedPipe.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
else:
    _kernel32 = None


class DiscordRpcActivity:
    def __init__(self, logger: Any | None = None) -> None:
        self.logger = logger
        self._handle: int | None = None

    def show(self, application_id: int | str, name: str) -> None:
        if _kernel32 is None:
            raise RpcError("Discord activity needs Windows")
        self.hide()
        handle = self._connect()
        try:
            self._handshake(handle, str(application_id))
            self._send(
                handle,
                _OP_FRAME,
                {
                    "cmd": "SET_ACTIVITY",
                    "args": {
                        "pid": os.getpid(),
                        "activity": {
                            "details": name,
                            "timestamps": {"start": int(time.time() * 1000)},
                        },
                    },
                    "nonce": f"dcgl-{int(time.time() * 1000)}",
                },
            )
        except RpcError:
            self._close(handle)
            raise
        self._handle = handle

    def hide(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            self._close(handle)

    def _connect(self) -> int:
        last = 0
        for index in range(_MAX_INSTANCES):
            handle = _kernel32.CreateFileW(
                f"{_PIPE_PREFIX}{index}",
                _GENERIC_READ | _GENERIC_WRITE,
                0,
                None,
                _OPEN_EXISTING,
                0,
                None,
            )
            if handle != _INVALID_HANDLE:
                return handle
            last = ctypes.get_last_error()
        raise RpcError(
            "Discord is not listening for game activity "
            f"(last error {last}); open the Discord client first"
        )

    def _handshake(self, handle: int, client_id: str) -> None:
        self._send(handle, _OP_HANDSHAKE, {"v": 1, "client_id": client_id})
        reply = self._read(handle, _HANDSHAKE_TIMEOUT)
        if reply is None:
            raise RpcError("Discord did not answer the activity handshake")
        event = reply.get("evt") or reply.get("cmd")
        if event != "READY":
            raise RpcError(f"Discord refused the activity handshake: {reply}")

    def _send(self, handle: int, opcode: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        frame = struct.pack("<II", opcode, len(body)) + body
        written = wintypes.DWORD(0)
        ok = _kernel32.WriteFile(
            handle, frame, len(frame), ctypes.byref(written), None
        )
        if not ok or written.value != len(frame):
            raise RpcError(
                "Discord closed the activity pipe "
                f"(error {ctypes.get_last_error()})"
            )

    def _read(self, handle: int, timeout: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            available = wintypes.DWORD(0)
            _kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(available), None
            )
            if available.value >= 8:
                buffer = ctypes.create_string_buffer(available.value)
                read = wintypes.DWORD(0)
                _kernel32.ReadFile(
                    handle, buffer, available.value, ctypes.byref(read), None
                )
                raw = buffer.raw[: read.value]
                if len(raw) < 8:
                    continue
                _opcode, length = struct.unpack("<II", raw[:8])
                body = raw[8 : 8 + length]
                if len(body) < length:
                    time.sleep(0.02)
                    continue
                try:
                    return json.loads(body.decode("utf-8", "replace"))
                except ValueError:
                    return None
            time.sleep(0.02)
        return None

    def _close(self, handle: int) -> None:
        try:
            _kernel32.CloseHandle(handle)
        except OSError:
            pass

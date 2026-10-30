from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time
from typing import Any, Self

from .errors import DiscordNativeError


def _mask_frame(opcode: int, payload: bytes) -> bytes:
    key = os.urandom(4)
    length = len(payload)
    header = bytearray([0x80 | opcode])
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += struct.pack("!H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack("!Q", length)
    header += key
    masked = bytes(byte ^ key[index & 3] for index, byte in enumerate(payload))
    return bytes(header) + masked


def _read_exact(read, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = read(count - len(chunks))
        if not chunk:
            raise DiscordNativeError("CDP connection closed")
        chunks += chunk
    return bytes(chunks)


def _read_frame(read) -> tuple[bool, int, bytes]:
    first, second = _read_exact(read, 2)
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _read_exact(read, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _read_exact(read, 8))[0]
    mask = _read_exact(read, 4) if masked else None
    data = _read_exact(read, length) if length else b""
    if mask is not None:
        data = bytes(byte ^ mask[index & 3] for index, byte in enumerate(data))
    return fin, opcode, data


class CdpConnection:
    def __init__(self, ws_url: str, timeout: float = 10.0):
        if not ws_url.startswith("ws://"):
            raise DiscordNativeError(f"Unsupported DevTools URL: {ws_url}")
        rest = ws_url[len("ws://") :]
        host_port, _, path = rest.partition("/")
        path = "/" + path
        host, _, port_text = host_port.partition(":")
        port = int(port_text or "80")
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise DiscordNativeError(f"Could not reach {host_port}: {exc}") from exc
        self._sock.settimeout(timeout)
        self._counter = 0
        self._pending = b""
        self._handshake(host_port, path)

    def _handshake(self, host_port: str, path: str) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self._sock.sendall(request.encode("ascii"))
        raw = bytearray()
        while b"\r\n\r\n" not in raw:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise DiscordNativeError("CDP closed during the websocket handshake")
            raw += chunk
            if len(raw) > 65536:
                raise DiscordNativeError("Oversized websocket handshake response")
        head_raw, _, leftover = bytes(raw).partition(b"\r\n\r\n")
        self._pending = leftover
        head = head_raw.decode("latin-1")
        status = head.split("\r\n", 1)[0]
        if "101" not in status:
            raise DiscordNativeError(f"DevTools rejected the websocket: {status}")

    def _read(self, count: int) -> bytes:
        if self._pending:
            chunk = self._pending[:count]
            self._pending = self._pending[len(chunk) :]
            return chunk
        return self._sock.recv(count)

    def command(self, method: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> dict[str, Any]:
        self._counter += 1
        message_id = self._counter
        payload = json.dumps(
            {"id": message_id, "method": method, "params": params or {}},
            separators=(",", ":"),
        ).encode("utf-8")
        self._sock.sendall(_mask_frame(0x1, payload))

        deadline = time.monotonic() + timeout
        fragments = bytearray()
        while time.monotonic() < deadline:
            self._sock.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                fin, opcode, data = _read_frame(self._read)
            except TimeoutError as exc:
                raise DiscordNativeError(
                    "Discord did not answer the DevTools call in time"
                ) from exc
            if opcode == 0x9:
                self._sock.sendall(_mask_frame(0xA, data))
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x8:
                raise DiscordNativeError("Discord closed the DevTools connection")
            if opcode == 0x0:
                fragments += data
                if not fin:
                    continue
                data = bytes(fragments)
                fragments = bytearray()
            elif opcode != 0x1:
                continue
            if not fin:
                fragments += data
                continue
            try:
                message = json.loads(data.decode("utf-8", "replace"))
            except ValueError:
                continue
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise DiscordNativeError(f"DevTools error: {message['error']}")
            return message.get("result") or {}
        raise DiscordNativeError("Timed out waiting for the DevTools response")

    def evaluate(self, expression: str, timeout: float = 15.0) -> Any:
        result = self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": False,
                "timeout": int(timeout * 1000),
            },
            timeout=timeout,
        )
        details = result.get("exceptionDetails")
        if details:
            text = details.get("exception", {}).get("description") or details.get(
                "text", "evaluation failed"
            )
            raise DiscordNativeError(str(text))
        remote = result.get("result") or {}
        return remote.get("value")

    def close(self) -> None:
        try:
            self._sock.sendall(_mask_frame(0x8, b""))
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

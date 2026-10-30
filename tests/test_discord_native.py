import json
import socket
import struct
import threading

import pytest

from launcher import discord_native, discord_setup
from launcher.discord_native import (
    CdpConnection,
    CdpTarget,
    DiscordInstall,
    DiscordNative,
    DiscordNativeError,
    _is_discord_page,
    _mask_frame,
    _newest_app_dir,
    _read_frame,
    find_installs,
    find_target,
    parse_quest_payload,
)


def test_newest_app_dir_picks_highest_version(temp_dir):
    for name in ("app-1.0.9", "app-1.0.9265", "app-1.0.99", "not-an-app"):
        (temp_dir / name).mkdir()
    path, version = _newest_app_dir(temp_dir)
    assert path is not None and path.name == "app-1.0.9265"
    assert version == "1.0.9265"


def test_newest_app_dir_ignores_non_numeric_suffix(temp_dir):
    (temp_dir / "app-latest").mkdir()
    (temp_dir / "app-1.0.5").mkdir()
    path, version = _newest_app_dir(temp_dir)
    assert path is not None and path.name == "app-1.0.5"
    assert version == "1.0.5"


def test_newest_app_dir_missing(temp_dir):
    assert _newest_app_dir(temp_dir / "nope") == (None, None)


def test_find_installs_reads_both_trees(temp_dir, monkeypatch):
    roam = temp_dir / "Roaming"
    local = temp_dir / "Local"
    app = local / "Discord" / "app-1.0.9265"
    app.mkdir(parents=True)
    (app / "Discord.exe").write_bytes(b"MZ")
    (roam / "discord").mkdir(parents=True)

    monkeypatch.setattr(discord_native.discovery, "_appdata", lambda: roam)
    monkeypatch.setattr(discord_native.discovery, "_localappdata", lambda: local)

    installs = find_installs()
    assert len(installs) == 1
    install = installs[0]
    assert install.channel == "stable"
    assert install.version == "1.0.9265"
    assert install.exe_path == app / "Discord.exe"


def test_find_installs_empty(temp_dir, monkeypatch):
    monkeypatch.setattr(discord_native.discovery, "_appdata", lambda: temp_dir / "Roaming")
    monkeypatch.setattr(discord_native.discovery, "_localappdata", lambda: temp_dir / "Local")
    assert find_installs() == []


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://discord.com/channels/@me", True),
        ("https://discord.com/quest-home", True),
        ("https://canary.discord.com/channels/@me/1", True),
        ("https://ptb.discord.com/login", True),
        ("https://discord.com.evil.test/", False),
        ("devtools://devtools/bundled/inspector.html", False),
        ("", False),
    ],
)
def test_is_discord_page(url, expected):
    assert _is_discord_page(url) is expected


def test_find_target_skips_non_discord_and_prefers_main_window(monkeypatch):
    pages = [
        {"type": "page", "url": "https://discord.com/popout", "webSocketDebuggerUrl": "ws://pop"},
        {"type": "worker", "url": "", "webSocketDebuggerUrl": "ws://b"},
        {"type": "page", "url": "https://discord.com/channels/@me", "webSocketDebuggerUrl": "ws://c"},
        {"type": "page", "url": "https://example.com/", "webSocketDebuggerUrl": "ws://d"},
    ]
    monkeypatch.setattr(discord_native.discovery, "_http_json", lambda port, *a, **k: pages)
    target, error = find_target([9222])
    assert error is None
    assert isinstance(target, CdpTarget)
    assert target.ws_url == "ws://c"
    assert target.url.endswith("/channels/@me")


def test_find_target_reports_endpoint_without_renderer(monkeypatch):
    monkeypatch.setattr(
        discord_native.discovery,
        "_http_json",
        lambda port, *a, **k: [{"type": "page", "url": "https://example.com", "webSocketDebuggerUrl": "ws://x"}],
    )
    target, error = find_target([9222])
    assert target is None
    assert "no Discord renderer" in str(error)


def test_find_targets_ranks_auxiliary_routes_last(monkeypatch):
    pages = [
        {"type": "page", "url": "https://discord.com/overlay", "webSocketDebuggerUrl": "ws://o"},
        {"type": "page", "url": "https://discord.com/popout", "webSocketDebuggerUrl": "ws://p"},
        {"type": "page", "url": "https://discord.com/quest-home", "webSocketDebuggerUrl": "ws://q"},
        {"type": "page", "url": "https://discord.com/some-new-route", "webSocketDebuggerUrl": "ws://n"},
    ]
    monkeypatch.setattr(discord_native.discovery, "_http_json", lambda port, *a, **k: pages)
    targets, error = discord_native.discovery.find_targets([9222])
    assert error is None
    assert [t.ws_url for t in targets] == ["ws://q", "ws://n", "ws://o", "ws://p"]


def test_find_targets_stops_after_first_answering_port(monkeypatch):
    calls = []

    def fake(port, *a, **k):
        calls.append(port)
        return [
            {
                "type": "page",
                "url": "https://discord.com/channels/@me",
                "webSocketDebuggerUrl": "ws://ok",
            }
        ]

    monkeypatch.setattr(discord_native.discovery, "_http_json", fake)
    discord_native.discovery.find_targets([9222, 9223, 9224])
    assert calls == [9222]


def test_find_target_survives_dead_ports(monkeypatch):
    calls = []

    def fake(port, *a, **k):
        calls.append(port)
        if port == 6463:
            raise DiscordNativeError("HTTP 404")
        return [{"type": "page", "url": "https://discord.com/channels/@me", "webSocketDebuggerUrl": "ws://ok"}]

    monkeypatch.setattr(discord_native.discovery, "_http_json", fake)
    target, error = find_target([6463, 9222])
    assert error is None and target is not None and target.port == 9222
    assert calls == [6463, 9222]


def test_mask_frame_and_read_back():
    left, right = socket.socketpair()
    try:
        payload = json.dumps({"hello": "world"}).encode()
        left.sendall(_mask_frame(0x1, payload))
        fin, opcode, data = _read_frame(right.recv)
        assert fin and opcode == 0x1
        assert data == payload
    finally:
        left.close()
        right.close()


def test_mask_frame_long_payload():
    left, right = socket.socketpair()
    try:
        payload = b"x" * 70000
        left.sendall(_mask_frame(0x1, payload))
        fin, opcode, data = _read_frame(right.recv)
        assert fin and opcode == 0x1 and data == payload
    finally:
        left.close()
        right.close()


def test_read_frame_handles_close_frame():
    left, right = socket.socketpair()
    try:
        left.sendall(_mask_frame(0x8, b""))
        _fin, opcode, data = _read_frame(right.recv)
        assert opcode == 0x8 and data == b""
    finally:
        left.close()
        right.close()


class _FakePeer(threading.Thread):
    def __init__(self, sock, reply_factory):
        super().__init__(daemon=True)
        self.sock = sock
        self.reply_factory = reply_factory
        self.error: Exception | None = None
        self.ping_sent = False

    def run(self):
        try:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = self.sock.recv(4096)
                if not chunk:
                    return
                request += chunk
            self.sock.sendall(
                b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Accept: fake\r\n\r\n"
            )
            self.sock.sendall(_server_frame(0x9, b"hi"))
            request_message = None
            while request_message is None or not self.ping_sent:
                _fin, opcode, data = _read_frame(self.sock.recv)
                if opcode == 0xA:
                    self.ping_sent = True
                elif opcode == 0x1:
                    request_message = json.loads(data)
                else:
                    raise AssertionError(f"unexpected opcode {opcode}")
            reply = self.reply_factory(request_message)
            self.sock.sendall(_server_frame(0x1, json.dumps(reply).encode()))
        except Exception as exc:
            self.error = exc
        finally:
            try:
                self.sock.close()
            except OSError:
                pass


def _server_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack("!H", length)
    else:
        header.append(127)
        header += struct.pack("!Q", length)
    return bytes(header) + payload


def _connect_to(monkeypatch, peer_sock):
    real = socket.create_connection

    def fake_create_connection(address, timeout=None, *a, **k):
        return peer_sock

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    try:
        return CdpConnection("ws://127.0.0.1:9222/devtools/page/abc")
    finally:
        monkeypatch.setattr(socket, "create_connection", real)


def test_cdp_evaluate_roundtrip(monkeypatch):
    client_sock, server_sock = socket.socketpair()

    def reply(message):
        assert message["method"] == "Runtime.evaluate"
        assert message["params"]["returnByValue"] is True
        return {
            "id": message["id"],
            "result": {"result": {"type": "string", "value": '{"ok": true}'}},
        }

    peer = _FakePeer(server_sock, reply)
    peer.start()
    connection = _connect_to(monkeypatch, client_sock)
    try:
        value = connection.evaluate("1 + 1", timeout=5.0)
        assert value == '{"ok": true}'
    finally:
        connection.close()
        server_sock.close()
    peer.join(timeout=5)
    assert peer.error is None
    assert peer.ping_sent is True


def test_cdp_evaluate_raises_on_exception_details(monkeypatch):
    client_sock, server_sock = socket.socketpair()

    def reply(message):
        return {
            "id": message["id"],
            "result": {
                "exceptionDetails": {"text": "Uncaught", "exception": {"description": "boom"}}
            },
        }

    peer = _FakePeer(server_sock, reply)
    peer.start()
    connection = _connect_to(monkeypatch, client_sock)
    try:
        with pytest.raises(DiscordNativeError, match="boom"):
            connection.evaluate("throw new Error('boom')", timeout=5.0)
    finally:
        connection.close()
        server_sock.close()
    peer.join(timeout=5)


def test_cdp_reads_frames_that_arrive_with_the_handshake(monkeypatch):
    client_sock, server_sock = socket.socketpair()

    def server():
        try:
            raw = b""
            while b"\r\n\r\n" not in raw:
                chunk = server_sock.recv(4096)
                if not chunk:
                    return
                raw += chunk
            reply = json.dumps(
                {"id": 1, "result": {"result": {"type": "number", "value": 42}}}
            ).encode()
            server_sock.sendall(
                b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Accept: fake\r\n\r\n"
                + _server_frame(0xA, b"")
                + _server_frame(0x1, reply)
            )
        except Exception as exc:
            server.error = exc

    peer = threading.Thread(target=server, daemon=True)
    peer.start()
    connection = _connect_to(monkeypatch, client_sock)
    try:
        assert connection.evaluate("6 * 7", timeout=5.0) == 42
    finally:
        connection.close()
        server_sock.close()
    peer.join(timeout=5)
    assert getattr(server, "error", None) is None


def test_cdp_rejects_non_ws_url():
    with pytest.raises(DiscordNativeError):
        CdpConnection("http://127.0.0.1:9222/")


def test_parse_quest_payload_accepts_json_string():
    envelope = {"ok": True, "quests": [{"id": "1"}]}
    assert parse_quest_payload(json.dumps(envelope))["quests"] == [{"id": "1"}]


def test_parse_quest_payload_rejects_failure():
    with pytest.raises(DiscordNativeError, match="store exploded"):
        parse_quest_payload({"ok": False, "error": "store exploded"})


def test_parse_quest_payload_rejects_garbage():
    with pytest.raises(DiscordNativeError):
        parse_quest_payload("{not json")


def test_parse_quest_payload_defaults_quests():
    assert parse_quest_payload({"ok": True})["quests"] == []


@pytest.fixture
def silent(monkeypatch):
    def pin(enabled: bool) -> None:
        state = {
            "port": 9223,
            "enabled": enabled,
            "wanted": enabled,
            "patched": 4 if enabled else 0,
            "total": 4,
            "launchers": [],
        }
        monkeypatch.setattr(discord_setup, "summary", lambda port=9223: dict(state))
        monkeypatch.setattr(discord_setup, "heal", lambda port=9223: False)

    return pin


def test_status_when_discord_not_installed(monkeypatch):
    monkeypatch.setattr(discord_native.client, "find_installs", list)
    monkeypatch.setattr(discord_native.client, "is_running", lambda: False)
    state = DiscordNative().status()
    assert state["installed"] is False
    assert state["connected"] is False
    assert "not installed" in state["hint"]


def test_status_when_running_without_debugger(monkeypatch, temp_dir, silent):
    install = discord_native.DiscordInstall(
        channel="stable",
        user_data_dir=temp_dir,
        app_dir=temp_dir,
        exe_path=temp_dir / "Discord.exe",
        version="1.0.9265",
    )
    monkeypatch.setattr(discord_native.client, "find_installs", lambda: [install])
    monkeypatch.setattr(discord_native.client, "is_running", lambda: True)
    monkeypatch.setattr(discord_native.client, "find_target", lambda ports: (None, "all dead"))
    silent(False)
    state = DiscordNative().status()
    assert state["installed"] is True
    assert state["running"] is True
    assert state["connected"] is False
    assert state["silent"] is False
    assert "without the endpoint" in state["hint"]


def test_status_hint_when_silent_mode_still_needs_a_restart(monkeypatch, temp_dir, silent):
    install = discord_native.DiscordInstall(
        channel="stable",
        user_data_dir=temp_dir,
        app_dir=temp_dir,
        exe_path=temp_dir / "Discord.exe",
        version="1.0.9265",
    )
    monkeypatch.setattr(discord_native.client, "find_installs", lambda: [install])
    monkeypatch.setattr(discord_native.client, "is_running", lambda: True)
    monkeypatch.setattr(discord_native.client, "find_target", lambda ports: (None, "all dead"))
    silent(True)
    state = DiscordNative().status()
    assert state["silent"] is True
    assert state["silent_wanted"] is True
    assert state["connected"] is False
    assert "Close and reopen Discord" in state["hint"]


def test_status_when_connected(monkeypatch, temp_dir):
    install = discord_native.DiscordInstall(
        channel="stable",
        user_data_dir=temp_dir,
        app_dir=temp_dir,
        exe_path=temp_dir / "Discord.exe",
        version="1.0.9265",
    )
    target = CdpTarget(
        port=9222,
        title="Friends",
        url="https://discord.com/channels/@me",
        ws_url="ws://127.0.0.1:9222/devtools/page/x",
    )
    monkeypatch.setattr(discord_native.client, "find_installs", lambda: [install])
    monkeypatch.setattr(discord_native.client, "is_running", lambda: True)
    monkeypatch.setattr(discord_native.client, "find_target", lambda ports: (target, None))
    state = DiscordNative().status()
    assert state["connected"] is True
    assert state["debug_port"] == 9222


def test_candidate_ports_prefers_explicit_port(monkeypatch):
    monkeypatch.setattr(discord_native.client, "running_processes", list)
    monkeypatch.setattr(discord_native.client, "_listening_ports", lambda pids: [])
    native = DiscordNative(port=9333)
    ports = list(native.candidate_ports())
    assert ports[0] == 9333
    assert 9222 in ports
    assert len(ports) == len(set(ports))


def test_candidate_ports_reads_the_debug_port_from_the_command_line(monkeypatch):
    class FakeProc:
        pid = 42

        def cmdline(self):
            return ["C:/Discord/Discord.exe", "--remote-debugging-port=9411"]

    monkeypatch.setattr(discord_native.client, "running_processes", lambda: [FakeProc()])
    monkeypatch.setattr(discord_native.client, "_listening_ports", lambda pids: [])
    ports = list(DiscordNative().candidate_ports())
    assert ports[0] == 9411


def test_candidate_ports_only_scans_sockets_as_a_last_resort(monkeypatch):
    scanned = []

    class FakeProc:
        pid = 7

        def cmdline(self):
            return ["C:/Discord/Discord.exe"]

    monkeypatch.setattr(discord_native.client, "running_processes", lambda: [FakeProc()])
    monkeypatch.setattr(
        discord_native.client,
        "_listening_ports",
        lambda pids: scanned.append(list(pids)) or [9555],
    )

    lazy = DiscordNative().candidate_ports()
    assert next(lazy) == 9222
    assert scanned == []


@pytest.mark.parametrize("value,expected", [(67080, 67080), (0, 0), (-5, None), (1.5, None), (True, None)])
def test_parse_quest_payload_normalises_orbs(value, expected):
    parsed = parse_quest_payload({"ok": True, "orbs": value, "quests": []})
    assert parsed["orbs"] == expected


def test_send_heartbeat_carries_the_task_key(monkeypatch):
    native = DiscordNative(port=9222)
    captured = {}

    def fake_api(op, timeout=20.0):
        captured.update(op)
        return {"ok": True}

    monkeypatch.setattr(native, "_quest_api", fake_api)
    native.send_heartbeat("1", 100, "game.exe", task_key="PLAY_ON_DESKTOP")

    assert captured["taskKey"] == "PLAY_ON_DESKTOP"


def test_send_video_progress_carries_the_task_key(monkeypatch):
    native = DiscordNative(port=9222)
    captured = {}

    def fake_api(op, timeout=20.0):
        captured.update(op)
        return {"ok": True}

    monkeypatch.setattr(native, "_quest_api", fake_api)
    native.send_video_progress("1", 12.5, task_key="WATCH_VIDEO")

    assert captured["taskKey"] == "WATCH_VIDEO"


def test_click_claim_reward_names_the_quest_and_its_card(monkeypatch):
    native = DiscordNative(port=9222)
    seen = {}

    def fake_eval(expression, timeout=8.0):
        seen["expression"] = expression
        return {"ok": True}

    monkeypatch.setattr(native, "_evaluate_on_client", fake_eval)
    native.click_claim_reward("12345", "Play Me", "Test Game")

    expression = seen["expression"]
    assert '"12345"' in expression
    assert "Play Me" in expression
    assert "Test Game" in expression
    assert "__DCGL_QUEST_NAMES__" not in expression
    assert "__DCGL_QUEST_ID__" not in expression


class _FakeProc:
    def __init__(self, pid, exe):
        self.pid = pid
        self._exe = exe
        self.terminated = False
        self.killed = False

    def exe(self):
        return self._exe

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def is_running(self):
        return True


def test_launch_opens_discord_from_its_shortcut(temp_dir, monkeypatch):
    exe = temp_dir / "app-1.0.1" / "Discord.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    install = DiscordInstall("stable", temp_dir / "roam", exe.parent, exe, "1.0.1")
    opened = []
    native = DiscordNative()

    class FakeOs:
        @staticmethod
        def startfile(path):
            opened.append(path)

    class FakeSys:
        platform = "win32"

    monkeypatch.setattr(discord_native.client, "os", FakeOs)
    monkeypatch.setattr(discord_native.client, "sys", FakeSys)
    monkeypatch.setattr(
        discord_native.client.discord_setup,
        "shortcut_path",
        lambda: "C:/Discord.lnk",
    )
    monkeypatch.setattr(
        discord_native.client.subprocess,
        "Popen",
        lambda *args, **kwargs: opened.append("popen"),
    )

    native._launch(install)

    assert opened == ["C:/Discord.lnk"]


def test_stop_client_stops_every_app_build_after_a_patch(temp_dir, monkeypatch):
    root = temp_dir / "Discord"
    old_exe = root / "app-1.0.9000" / "Discord.exe"
    new_exe = root / "app-1.0.9001" / "Discord.exe"
    other_channel = temp_dir / "DiscordPTB" / "app-1.0.1" / "DiscordPTB.exe"
    install = DiscordInstall(
        "stable", temp_dir / "roam", new_exe.parent, new_exe, "1.0.9001"
    )
    old_proc = _FakeProc(11, str(old_exe))
    new_proc = _FakeProc(12, str(new_exe))
    other_proc = _FakeProc(13, str(other_channel))

    monkeypatch.setattr(
        discord_native.client,
        "running_processes",
        lambda: [old_proc, new_proc, other_proc],
    )
    monkeypatch.setattr(
        DiscordNative, "_request_close", staticmethod(lambda victims: None)
    )
    waits = [[], []]

    def fake_wait(procs, timeout=None):
        return ([], procs if not waits.pop(0) else [])

    monkeypatch.setattr(discord_native.client.psutil, "wait_procs", fake_wait)

    DiscordNative()._stop_client(install)

    assert old_proc.terminated is True
    assert new_proc.terminated is True
    assert other_proc.terminated is False

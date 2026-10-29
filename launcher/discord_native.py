"""Discord desktop client integration.

Reads the quest list from the Discord client that is already running on this
machine, instead of calling Discord's REST API.

The client is an Electron app. The only supported door into its renderer from
another process is the Chrome DevTools Protocol endpoint that Electron opens
when the browser process starts with --remote-debugging-port. Plain Discord
refuses to forward that switch from elsewhere (its settings reader filters
every switch through a fixed allow-list), so a client that was already running
without the switch has to be restarted once, which DiscordNative.connect()
does on request.

Nothing here reads Discord credentials, tokens, or cookies, and nothing here
calls discord.com. The data comes out of the renderer's own in-memory stores,
which is the same data the Quests tab displays.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import struct
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

import psutil

from launcher import discord_setup

# Channels Windows Discord ships, with the folder names each uses.
_CHANNELS: tuple[tuple[str, str, str], ...] = (
    ("stable", "discord", "Discord"),
    ("ptb", "discordptb", "DiscordPTB"),
    ("canary", "discordcanary", "DiscordCanary"),
)

# Ports tried when the client was started with a debugger we can guess at.
_DEFAULT_PORTS: tuple[int, ...] = (9222, 9223, 9224, 9229)

# The desktop client is a single page app, so the renderer can sit on any
# route: /channels/..., /quest-home, /store, /login. Host is the stable part.
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


class DiscordNativeError(Exception):
    """Raised when the Discord client cannot be reached or answers badly."""


class QuestApiError(DiscordNativeError):
    """A quest request Discord refused, with the reason it gave.

    `captcha` marks the one refusal the app cannot act on by itself: Discord
    wants a challenge solved in its own window before the request goes through.
    """

    def __init__(self, message: str, captcha: bool = False):
        super().__init__(message)
        self.captcha = bool(captcha)


@dataclass(frozen=True)
class DiscordInstall:
    """One Discord channel found on disk."""

    channel: str
    user_data_dir: Path
    app_dir: Path | None
    exe_path: Path | None
    version: str | None


@dataclass(frozen=True)
class CdpTarget:
    """A page target advertised by the DevTools endpoint."""

    port: int
    title: str
    url: str
    ws_url: str


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def _newest_app_dir(channel_dir: Path) -> tuple[Path | None, str | None]:
    """Highest app-<version> directory, compared numerically."""
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
    """Every Discord channel installed for the current user."""
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
    """Discord processes owned by the current user."""
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
    """Localhost ports the given processes listen on (debugger candidates)."""
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
    """GET a DevTools HTTP endpoint on loopback, bypassing any proxy."""
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


# Routes that carry the app's module registry. Discord opens extra windows
# (a popout, the overlay, push-to-talk) that are real Discord pages but are
# separate renderers without the stores we read.
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
    """Every Discord renderer target, most likely to hold the stores first."""
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
            # Window targets of one client all live on one port; stop probing
            # the rest instead of paying a timeout per dead candidate.
            break
        last_error = f"port {port}: endpoint answered but has no Discord renderer"
    found.sort(key=lambda target: (_route_rank(target.url), target.port))
    return found, (last_error if not found else None)


def find_target(ports: Iterable[int]) -> tuple[CdpTarget | None, str | None]:
    """Best renderer target on any candidate port, or the last error."""
    targets, error = find_targets(ports)
    return (targets[0] if targets else None), error


# ---------------------------------------------------------------------------
# minimal RFC 6455 client (loopback, text frames only)
# ---------------------------------------------------------------------------


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
    """Read exactly count bytes from a read callable."""
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
    """One websocket to one renderer, enough for Runtime.evaluate."""

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
        # Bytes that arrived with the handshake reply belong to the frame
        # stream; dropping them would lose whatever the peer sent right after.
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
        """Send one DevTools command and return its result object."""
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
            if opcode == 0x9:  # ping
                self._sock.sendall(_mask_frame(0xA, data))
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode == 0x8:
                raise DiscordNativeError("Discord closed the DevTools connection")
            if opcode == 0x0:  # continuation
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
        """Evaluate an expression in the page and return its value."""
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


# ---------------------------------------------------------------------------
# quest reader (runs inside the renderer)
# ---------------------------------------------------------------------------

# Returns a JSON string on purpose: the payload is a few hundred kilobytes and
# one more JSON round-trip keeps returnByValue predictable.
QUESTS_EXPRESSION = r"""
(() => {
  const out = {
    ok: false,
    error: null,
    quests: [],
    questCount: 0,
    account: null,
    suspendedUntil: null,
    enrollmentBlockedUntil: null,
    storeFound: false,
    orbs: null
  };
  try {
    const wc = window.webpackChunkdiscord_app;
    if (!wc) throw new Error("Discord's module registry (webpackChunkdiscord_app) is not reachable");
    const req = wc.push([[Symbol()], {}, (r) => r]);
    wc.pop();
    const mods = (req && req.c) || {};

    const nameOf = (candidate) => {
      if (!candidate || (typeof candidate !== "object" && typeof candidate !== "function")) return null;
      try {
        if (typeof candidate.getName === "function") return candidate.getName();
      } catch (e) { /* stores are not all well behaved */ }
      try {
        if (typeof candidate.displayName === "string") return candidate.displayName;
      } catch (e) { /* ignore */ }
      return null;
    };

    let questStore = null;
    let userStore = null;
    let orbStore = null;
    for (const id in mods) {
      const record = mods[id];
      if (!record || !record.exports) continue;
      const exported = record.exports;
      const candidates = [exported, exported.default, exported.A, exported.Z];
      for (const candidate of candidates) {
        const name = nameOf(candidate);
        if (!name) continue;
        if (!questStore && (name === "QuestStore" || name === "QuestsStore")) questStore = candidate;
        else if (!userStore && name === "UserStore") userStore = candidate;
        else if (!orbStore && name === "VirtualCurrencyStore") orbStore = candidate;
      }
      if (questStore && userStore && orbStore) break;
    }

    if (!questStore) {
      // Duck-typed fallback for builds that rename the store.
      for (const id in mods) {
        const record = mods[id];
        if (!record || !record.exports) continue;
        for (const candidate of [record.exports, record.exports.default, record.exports.A]) {
          if (!candidate || typeof candidate !== "object") continue;
          try {
            if (candidate.quests && typeof candidate.getQuest === "function") { questStore = candidate; break; }
          } catch (e) { /* ignore */ }
        }
        if (questStore) break;
      }
    }

    if (!questStore) throw new Error("Discord's QuestStore was not found; the client may still be loading");
    out.storeFound = true;

    try {
      const user = typeof userStore?.getCurrentUser === "function" ? userStore.getCurrentUser() : null;
      if (user) out.account = { id: String(user.id || ""), username: user.username || null };
    } catch (e) { /* the account is decoration, not data */ }

    // The Orb pill on Discord's own quest page. Null until the client has
    // fetched it once this session (opening the quest page does that), which
    // the UI has to say rather than showing a wrong zero.
    try {
      if (orbStore && typeof orbStore.getCurrentBalance === "function") {
        const balance = orbStore.getCurrentBalance();
        if (typeof balance === "number" && Number.isInteger(balance) && balance >= 0) {
          out.orbs = balance;
        }
      }
    } catch (e) { /* the balance is decoration, not data */ }

    const future = (raw) => {
      if (!raw) return null;
      const when = new Date(raw);
      return Number.isNaN(when.getTime()) || when.getTime() <= Date.now() ? null : when.toISOString();
    };
    try { out.suspendedUntil = future(questStore.questAccessSuspendedUntil) || (questStore.isQuestAccessSuspended === true ? "suspended" : null); } catch (e) { /* ignore */ }
    try { out.enrollmentBlockedUntil = future(questStore.questEnrollmentBlockedUntil); } catch (e) { /* ignore */ }

    const raw = questStore.quests;
    let list = [];
    if (raw) {
      if (typeof raw.values === "function") list = Array.from(raw.values());
      else if (Array.isArray(raw)) list = raw;
      else list = Object.values(raw);
    }
    out.questCount = list.length;

    const entries = (tasks) => {
      if (!tasks) return [];
      if (typeof tasks.entries === "function" && typeof tasks.get === "function") return Array.from(tasks.entries());
      return Object.entries(tasks);
    };

    // Task keys this app can act on, best first. Play on desktop is something a
    // fake process can finish; a watch quest still has to be watched in the
    // client, but listing it is the difference between "no quests" and "here is
    // what you have".
    const ACTIONABLE = ["PLAY_ON_DESKTOP", "WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"];
    const KIND = {
      PLAY_ON_DESKTOP: "play",
      WATCH_VIDEO: "watch",
      WATCH_VIDEO_ON_MOBILE: "watch_mobile"
    };

    for (const quest of list) {
      if (!quest || !quest.id) continue;
      const config = quest.config || {};
      const v2 = config.taskConfigV2 && config.taskConfigV2.tasks;
      const legacy = config.taskConfig && config.taskConfig.tasks;
      const v2Entries = entries(v2);
      const tasks = v2Entries.length ? v2Entries : entries(legacy);
      if (!tasks.length) continue;

      const byKey = {};
      for (const [key, task] of tasks) byKey[key] = task;

      let chosenKey = null;
      for (const key of ACTIONABLE) {
        if (byKey[key]) { chosenKey = key; break; }
      }
      if (!chosenKey) continue;
      const chosen = byKey[chosenKey];
      const kind = KIND[chosenKey];

      const applications = Array.isArray(chosen.applications) ? chosen.applications : [];
      const appId = applications.length && applications[0] && applications[0].id
        ? String(applications[0].id)
        : (config.application && config.application.id ? String(config.application.id) : null);

      const status = quest.userStatus || {};
      const progress = status.progress && status.progress[chosenKey];
      const assets = config.assets || {};
      const rewards = Array.isArray(config.rewardsConfig && config.rewardsConfig.rewards)
        ? config.rewardsConfig.rewards
        : [];
      // Every entry matters: a quest can list an in-game item first and Orbs
      // second, so reading rewards[0] reports no Orbs for a quest that pays
      // them. Discord's own card sums the entries the same way.
      let rewardOrbs = 0;
      let rewardPremiumOrbs = 0;
      let rewardAvatarDecoration = false;
      let rewardInGame = false;
      const rewardNames = [];
      for (const entry of rewards) {
        const base = Number(entry && entry.orbQuantity);
        if (base > 0) {
          rewardOrbs += base;
          const premium = Number(entry.premiumOrbQuantity);
          rewardPremiumOrbs += premium > 0 ? premium : base;
        }
        const rewardType = entry && entry.type;
        if (rewardType === 3) rewardAvatarDecoration = true;
        else if (rewardType === 1) rewardInGame = true;
        const label = entry && entry.messages && entry.messages.name;
        if (label) rewardNames.push(String(label));
      }
      const reward = rewards.length ? rewards[0] : null;
      const video = (chosen.assets && chosen.assets.video) || null;

      out.quests.push({
        id: String(quest.id),
        kind: kind,
        taskKey: chosenKey,
        name: (config.messages && config.messages.questName) || (config.messages && config.messages.gameTitle) || "Quest",
        gameName: (config.messages && config.messages.gameTitle) || (config.messages && config.messages.questName) || "Unknown game",
        publisher: (config.messages && config.messages.gamePublisher) || null,
        applicationId: appId,
        taskKeys: tasks.map((entry) => entry[0]),
        target: Number(chosen.target) || 0,
        progress: Number(progress && progress.value) || 0,
        enrolledAt: status.enrolledAt || null,
        completedAt: status.completedAt || null,
        claimedAt: status.claimedAt || null,
        dismissedAt: status.dismissedAt || null,
        expiresAt: config.expiresAt || null,
        startsAt: config.startsAt || null,
        tile: assets.gameTileLight || assets.gameTileDark || assets.gameTile || null,
        hero: assets.hero || null,
        logotype: assets.logotypeLight || assets.logotypeDark || null,
        video: video ? {
          url: video.url || null,
          thumbnail: video.thumbnail || null,
          width: Number(video.width) || null,
          height: Number(video.height) || null
        } : null,
        accent: (config.colors && config.colors.primary) || null,
        rewardType: reward ? reward.type : null,
        rewardName: rewardNames.length ? rewardNames[0] : null,
        rewardNames: rewardNames,
        rewardOrbs: rewardOrbs > 0 ? rewardOrbs : null,
        rewardPremiumOrbs: rewardOrbs > 0 ? rewardPremiumOrbs : null,
        rewardAvatarDecoration: rewardAvatarDecoration,
        rewardInGame: rewardInGame
      });
    }

    out.ok = true;
  } catch (error) {
    out.error = String((error && error.message) || error);
  }
  return JSON.stringify(out);
})()
"""




QUEST_API_EXPRESSION = r"""
(async () => {
  const op = __DCGL_OP__;
  const fail = (error, extra) => JSON.stringify(Object.assign({ ok: false, error: String(error) }, extra || {}));
  try {
    const wc = window.webpackChunkdiscord_app;
    if (!wc) return fail("Discord's module registry is not reachable");
    const req = wc.push([[Symbol()], {}, (r) => r]);
    wc.pop();
    const mods = (req && req.c) || {};

    const nameOf = (candidate) => {
      if (!candidate || (typeof candidate !== "object" && typeof candidate !== "function")) return null;
      try {
        if (typeof candidate.getName === "function") return candidate.getName();
      } catch (e) { /* stores are not all well behaved */ }
      try {
        if (typeof candidate.displayName === "string") return candidate.displayName;
      } catch (e) { /* ignore */ }
      return null;
    };

    // Same discovery as the quest reader: named stores first, because the
    // duck-typed matcher can land on an unrelated cache in this build.
    let questStore = null;
    let api = null;
    for (const id in mods) {
      const record = mods[id];
      if (!record || !record.exports) continue;
      const exported = record.exports;
      for (const candidate of [exported, exported.default, exported.A, exported.Z]) {
        const name = nameOf(candidate);
        if (!questStore && (name === "QuestStore" || name === "QuestsStore")) questStore = candidate;
      }
      for (const key of Object.keys(exported)) {
        // Some modules export the global object, whose numeric keys are
        // cross-origin iframes. Reading a property off one throws, and that
        // error used to abort the whole scan before the HTTP client was found.
        let value;
        try {
          value = exported[key];
          if (
            !api &&
            value &&
            typeof value.get === "function" &&
            typeof value.post === "function" &&
            typeof value.del === "function" &&
            !value._dispatcher
          ) {
            api = value;
          }
        } catch (e) { /* frames from another origin are not candidates */ }
      }
    }
    if (!questStore) return fail("Discord's QuestStore was not found");
    if (!api) return fail("Discord's HTTP client was not found");

    const raw = questStore.quests;
    let list = [];
    if (raw) {
      if (typeof raw.values === "function") list = Array.from(raw.values());
      else if (Array.isArray(raw)) list = raw;
      else list = Object.values(raw);
    }
    const quest = list.find((q) => q && String(q.id) === String(op.questId)) || null;
    const sealed = quest ? (quest.trafficMetadataSealed ?? null) : null;

    const post = async (url, body) => {
      const response = await api.post({ url: url, body: body });
      return {
        ok: response ? response.ok !== false : false,
        status: response ? response.status ?? null : null,
        body: response ? response.body ?? null : null,
      };
    };

    let result;
    if (op.kind === "enroll") {
      result = await post("/quests/" + op.questId + "/enroll", {
        location: 11,
        is_targeted: false,
        metadata_sealed: null,
        traffic_metadata_sealed: sealed,
      });
    } else if (op.kind === "video") {
      result = await post("/quests/" + op.questId + "/video-progress", {
        timestamp: op.timestamp,
      });
    } else if (op.kind === "heartbeat") {
      // Discord's own game client posts this every twenty seconds; the server
      // credits play time per beat, so nothing has to run on the machine.
      result = await post("/quests/" + op.questId + "/heartbeat", {
        application_id: op.applicationId,
        terminal: Boolean(op.terminal),
        executable_path: op.executablePath,
      });
    } else if (op.kind === "claim") {
      result = await post("/quests/" + op.questId + "/claim-reward", {
        platform: 0,
        location: 11,
        is_targeted: false,
        metadata_sealed: null,
        traffic_metadata_sealed: sealed,
      });
    } else {
      return fail("Unknown quest operation");
    }

    const body = result.body || {};
    if (!result.ok) {
      return fail(body.message || "Discord refused the quest request", {
        status: result.status,
        code: body.code ?? null,
        // A claim that needs a challenge comes back with one of these keys.
        captcha: Boolean(body.captcha_key || body.captcha_sitekey),
      });
    }
    // One beat answers with the running total for the quest's task, which is
    // how the caller knows the target was reached without another full read.
    let credited = null;
    if (body.progress && typeof body.progress === "object") {
      for (const key of Object.keys(body.progress)) {
        const entry = body.progress[key];
        if (entry && typeof entry.value === "number") {
          credited = Math.max(credited === null ? 0 : credited, entry.value);
        }
      }
    }
    return JSON.stringify({
      ok: true,
      status: result.status,
      enrolled: Boolean(body.enrolled_at),
      completed: Boolean(body.completed_at),
      progress: body.progress ?? null,
      credited: credited,
    });
  } catch (error) {
    const body = (error && error.body) || {};
    return fail((body && body.message) || (error && error.message) || error, {
      status: (error && error.status) || null,
      code: body.code ?? null,
    });
  }
})()
"""


def parse_quest_payload(value: Any) -> dict[str, Any]:
    """Decode whatever the renderer handed back into the quest envelope."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise DiscordNativeError("Discord returned an unreadable quest payload") from exc
    if not isinstance(value, dict):
        raise DiscordNativeError("Discord returned an unexpected quest payload")
    if not value.get("ok"):
        raise DiscordNativeError(str(value.get("error") or "Discord could not list quests"))
    if not isinstance(value.get("quests"), list):
        value["quests"] = []
    orbs = value.get("orbs")
    if isinstance(orbs, bool) or not isinstance(orbs, int) or orbs < 0:
        value["orbs"] = None
    return value


# ---------------------------------------------------------------------------
# facade
# ---------------------------------------------------------------------------


class DiscordNative:
    """Discovery, reads, and the one-shot restart that enables the debugger."""

    def __init__(self, logger=None, port: int | None = None):
        self.logger = logger
        self.port = port or int(os.environ.get("DCGL_DISCORD_CDP_PORT") or 0) or None
        self._last_error: str | None = None
        self._last_target: CdpTarget | None = None

    # -- status -----------------------------------------------------------
    def install(self) -> DiscordInstall | None:
        """The installed channel, stable preferred."""
        installs = find_installs()
        if not installs:
            return None
        for install in installs:
            if install.channel == "stable":
                return install
        return installs[0]

    def candidate_ports(self) -> Iterator[int]:
        """Ports worth asking, cheapest answer first.

        A generator on purpose: the last step enumerates every socket the
        Discord process tree owns, which costs seconds on Windows, so it only
        runs when nothing cheaper answered.
        """
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
            # A Discord update rewrites the Run value and drops the switch.
            # Restoring it is what the user asked for once, so do it quietly;
            # it only changes the next launch, never the running client.
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
                    "Every Discord launcher now carries the endpoint. "
                    "Close and reopen Discord once to pick it up."
                )
            return (
                "Discord is running without a DevTools endpoint. "
                "Connect turns on silent connection and restarts it once."
            )
        return "Connected to the running Discord client."

    # -- reads ------------------------------------------------------------
    def read_quests(self) -> dict[str, Any]:
        """Ask the running client for its quest list.

        Tries the ranked renderers in turn: a popout or overlay window is a
        valid Discord page whose module registry is empty, so attaching to the
        wrong one is not an error the user can act on.
        """
        targets, error = find_targets(self.candidate_ports())
        if not targets:
            self._last_error = error
            raise DiscordNativeError(
                "Discord is running but its local DevTools endpoint is not open. "
                "Connecting restarts it once with the endpoint enabled."
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

    def _evaluate_on_client(self, expression: str, timeout: float = 8.0) -> Any:
        """Run one expression in the first renderer that answers.

        Same target ranking as read_quests: a popout or overlay page answers
        the DevTools handshake but has no module registry, so the wrong target
        looks like a failed call rather than a wrong window.
        """
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


    # -- quest actions -----------------------------------------------------
    # These go through Discord's own HTTP client inside the renderer, the same
    # way the client enrolls and reports video progress. No user token is ever
    # read or stored: the request is signed by the running client.
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
            )
        return payload

    def accept_quest(self, quest_id: str) -> dict[str, Any]:
        """Accept (enroll in) a quest from the running client."""
        return self._quest_api({"kind": "enroll", "questId": str(quest_id)})

    def send_video_progress(self, quest_id: str, timestamp: float) -> dict[str, Any]:
        """Report how many seconds of a video quest have been watched."""
        return self._quest_api(
            {
                "kind": "video",
                "questId": str(quest_id),
                "timestamp": round(float(timestamp), 6),
            }
        )

    def send_heartbeat(
        self,
        quest_id: str,
        application_id: int | str,
        executable_path: str,
        terminal: bool = False,
    ) -> dict[str, Any]:
        """Post one play-time heartbeat for a quest.

        This is the same request Discord's client sends while a game is open.
        The server credits the time that passed since the previous beat, so a
        quest finishes without any game process being launched.
        """
        return self._quest_api(
            {
                "kind": "heartbeat",
                "questId": str(quest_id),
                "applicationId": str(application_id),
                "executablePath": str(executable_path),
                "terminal": bool(terminal),
            }
        )

    def claim_quest_reward(self, quest_id: str) -> dict[str, Any]:
        """Claim the reward of a finished quest."""
        return self._quest_api({"kind": "claim", "questId": str(quest_id)})

    # -- control ----------------------------------------------------------
    def start(self, wait_seconds: float = 45.0) -> tuple[bool, str]:
        """Launch Discord with the endpoint when it is not running.

        This is the no-restart path: nothing is closed, because nothing is
        open yet.
        """
        target = self.target()
        if target is not None:
            return True, f"Already connected to Discord on port {target.port}"

        install = self.install()
        if install is None or install.exe_path is None:
            return False, "Discord is not installed for this user."
        if is_running():
            return False, (
                "Discord is already running without a DevTools endpoint. "
                "It has to be restarted once to enable it."
            )

        port = self.port or self._free_port()
        if port is None:
            return False, "Could not find a free local port for the DevTools endpoint."
        self._enable_silent(port)
        try:
            self._launch(install, port)
        except OSError as exc:
            return False, f"Could not start Discord: {exc}"
        return self._await_quests(port, wait_seconds)

    def connect(self, wait_seconds: float = 30.0) -> tuple[bool, str]:
        """Make sure a DevTools endpoint exists, restarting Discord if needed."""
        target = self.target()
        if target is not None:
            return True, f"Already connected to Discord on port {target.port}"

        install = self.install()
        if install is None or install.exe_path is None:
            return False, "Discord is not installed for this user."
        if not is_running():
            # Nothing to restart: start it with the endpoint instead.
            return self.start(wait_seconds=wait_seconds)

        port = self.port or self._free_port()
        if port is None:
            return False, "Could not find a free local port for the DevTools endpoint."

        # Do this before the restart: if it fails the restart still helps, and
        # if it works this is the last restart the user ever needs.
        self._enable_silent(port)

        try:
            self._stop_client(install)
        except (psutil.Error, OSError) as exc:
            if self.logger:
                self.logger.warning(f"Could not close Discord cleanly: {exc}")

        try:
            self._launch(install, port)
        except OSError as exc:
            return False, f"Could not start Discord: {exc}"

        return self._await_quests(port, wait_seconds, closing="restarted")

    def _enable_silent(self, port: int) -> bool:
        """Put the debug switch into every launcher that starts Discord."""
        try:
            result = discord_setup.enable(port)
        except (OSError, ValueError) as exc:
            if self.logger:
                self.logger.warning(f"Could not update the Discord launchers: {exc}")
            return False
        if self.logger:
            state = "on" if result.get("ok") else "partial"
            self.logger.info(f"Silent connection {state}: {result.get('message')}")
        return bool(result.get("ok"))

    def _await_quests(
        self,
        port: int,
        wait_seconds: float,
        closing: str = "started",
    ) -> tuple[bool, str]:
        """Wait until the endpoint is open and the client has quests to show."""
        deadline = time.monotonic() + wait_seconds
        opened = False
        while time.monotonic() < deadline:
            target, _error = find_target([port])
            if target is not None:
                self.port = port
                opened = True
                break
            time.sleep(0.5)
        if not opened:
            return False, (
                f"Discord {closing} but did not open a DevTools endpoint. "
                "Check that no other process is holding the port."
            )

        # The endpoint answers HTTP before the renderer has loaded its own
        # JavaScript, and the store stays empty until the client finishes its
        # first quest fetch. Report success only once a read returns data.
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
            # An account can genuinely have no quests, so a short grace period
            # rather than an indefinite wait.
            if time.monotonic() - answered > 8.0:
                return True, f"Connected to Discord on port {port}"
            time.sleep(0.75)
        return True, (
            f"Discord is on port {port} but has not listed quests yet. "
            "Press Refresh in a few seconds."
        )

    @staticmethod
    def _free_port() -> int | None:
        for port in _DEFAULT_PORTS:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        return None

    def _stop_client(self, install: DiscordInstall) -> None:
        """Close the running client so the switch takes effect.

        Every call here is best-effort: Discord spawns helpers this process
        may not be allowed to open a handle to, and an AccessDenied on one of
        them must not abort the restart.
        """
        victims: list[psutil.Process] = []
        for proc in running_processes():
            try:
                exe = proc.exe()
            except (psutil.Error, OSError):
                exe = ""
            if install.app_dir is not None and exe:
                try:
                    Path(exe).relative_to(install.app_dir)
                except ValueError:
                    continue
            victims.append(proc)

        for proc in victims:
            try:
                proc.terminate()
            except (psutil.Error, OSError):
                continue

        # psutil.wait_procs raises PermissionError on a process it cannot open
        # on Windows, so it cannot be the authority on what is still alive.
        try:
            psutil.wait_procs(victims, timeout=10)
        except (psutil.Error, OSError):
            pass

        for proc in victims:
            try:
                if proc.is_running():
                    proc.kill()
            except (psutil.Error, OSError):
                continue
        time.sleep(1.0)

        if self.logger:
            self.logger.info(f"Stopped {len(victims)} Discord process(es)")

    def _launch(self, install: DiscordInstall, port: int) -> None:
        if install.exe_path is None:
            raise OSError("Discord executable not found")
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        subprocess.Popen(
            [str(install.exe_path), f"--remote-debugging-port={port}"],
            cwd=str(install.exe_path.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        if self.logger:
            self.logger.info(f"Started Discord with --remote-debugging-port={port}")

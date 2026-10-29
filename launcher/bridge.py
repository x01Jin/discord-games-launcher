"""Discord Games Launcher - pywebview JS bridge.

Exposes GameManager operations to the React frontend as JSON-only
methods on ``window.pywebview.api``. State changes push through
``dcgl`` CustomEvents.
"""

import os
import sqlite3
import sys
from collections.abc import Callable
from typing import Any

from launcher import discord_native, discord_setup
from launcher import prefs as quest_prefs
from launcher.discord_native import DiscordNativeError
from launcher.game_manager import GameManager, GameManagerError


def _focus_discord() -> bool:
    """Bring the Discord window to the front.

    A captcha can only be solved inside Discord, so a claim that needs one ends
    with the user looking at the client instead of at a toast telling them to
    go find it. Windows refuses foreground changes from a background process
    without an input edge, so the restore is best effort.
    """
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
        # The first visible titled window is the main client, not a popout.
        user32.ShowWindow(found[0], 9)  # SW_RESTORE
        user32.SetForegroundWindow(found[0])
        return True
    except (OSError, AttributeError, ValueError) as exc:
        print(f"[dcgl] Could not focus Discord: {exc}", file=sys.stderr)
        return False


class Bridge:
    """JS API for the webview frontend. All returns must be JSON-serializable."""

    def __init__(self, game_manager: GameManager, quest_service=None):
        self.game_manager = game_manager
        self.quest_service = quest_service
        self.push: Callable[[dict[str, Any]], None] | None = None
        if quest_service is not None:
            # A run starting or finishing repaints the quest page at once
            # instead of waiting for its next twenty-second poll.
            quest_service.on_change = lambda: self._emit({"type": "quests_changed"})

    # -- internal helpers ------------------------------------------------
    def _emit(self, event: dict[str, Any]) -> None:
        if self.push is not None:
            try:
                self.push(event)
            except Exception:  # noqa: BLE001, S110 - push must never break calls
                pass

    @staticmethod
    def _parse_game_id(raw: int | str) -> int | None:
        """Strictly parse a frontend game ID; None when invalid.

        Rejects bools, floats, and non-numeric strings (int() would silently
        truncate or coerce those), plus out-of-range values that SQLite
        cannot bind. Digit strings ("007") are accepted deterministically.
        """
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            value = raw
        elif isinstance(raw, str):
            text = raw.strip()
            if not text or not text.isascii() or not text.isdigit():
                return None
            try:
                value = int(text)
            except ValueError:
                return None
        else:
            return None
        if value <= 0 or value > 2**63 - 1:
            return None
        return value

    def _serialize_game(self, game, in_library: bool) -> dict[str, Any]:
        try:
            win_exes = self.game_manager.api.get_best_win32_executables(
                game.executables
            )
        except Exception:  # noqa: BLE001 - scoring failure means unplayable card
            win_exes = []
        return {
            # IDs cross to JS as strings: snowflake-scale ints lose
            # precision as JSON numbers (IEEE-754 doubles).
            "id": str(game.id),
            "name": game.name,
            "icon_hash": game.icon_hash,
            "win_exes": [e.get("name", "") for e in win_exes if e.get("name")],
            "in_library": in_library,
        }

    # -- catalogue -------------------------------------------------------
    def list_games(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        try:
            limit = max(1, min(int(limit), 500))
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            limit, offset = 200, 0
        try:
            # Filtering and pagination both happen in SQL; the catalogue only
            # ever holds Windows-playable games.
            games = self.game_manager.get_games_page(limit=limit, offset=offset)
            # Raw IDs (not the cache-JOINed view): dangling rows must still
            # read as in-library so add/remove stay consistent.
            library_ids = self.game_manager.db.get_library_ids()
            return {
                "games": [
                    self._serialize_game(g, g.id in library_ids) for g in games
                ],
                "total": self.game_manager.count_playable_games(),
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"games": [], "total": 0, "error": str(e)}

    def search_games(self, query: str, limit: int = 50) -> dict[str, Any]:
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50
        try:
            games = self.game_manager.search_games(str(query), limit=limit)
            library_ids = self.game_manager.db.get_library_ids()
            return {
                "games": [
                    self._serialize_game(g, g.id in library_ids) for g in games
                ]
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"games": [], "error": str(e)}

    def sync_catalogue(self) -> dict[str, Any]:
        try:
            synced, count, skipped = self.game_manager.sync_games(force=True)
            self._emit({"type": "library_changed"})
            notice = self.game_manager.note_api_version(
                self.game_manager.api.last_fetch_version
            )
            if synced:
                message = f"Synced {count:,} games from Discord"
                if skipped:
                    message += f" ({skipped:,} skipped)"
                message += notice
            else:
                message = "Cache is up to date" + notice
            return {
                "synced": synced,
                "count": count,
                "skipped": skipped,
                "message": message,
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {
                "synced": False,
                "count": 0,
                "skipped": 0,
                "message": f"Sync failed: {e}",
            }

    # -- library ---------------------------------------------------------
    def add_to_library(self, game_id: int | str) -> dict[str, Any]:
        parsed = self._parse_game_id(game_id)
        if parsed is None:
            return {"ok": False, "message": "Invalid game id"}
        try:
            ok, message = self.game_manager.add_to_library(parsed)
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to add game: {e}"}
        if ok:
            self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def add_many(self, game_ids: list[int | str]) -> dict[str, Any]:
        added, failed, skipped = 0, 0, 0
        ids: list[int] = []
        for g in game_ids or []:
            parsed = self._parse_game_id(g)
            if parsed is None:
                failed += 1
            else:
                ids.append(parsed)
        for gid in ids:
            try:
                if self.game_manager.is_in_library(gid):
                    skipped += 1
                    continue
                ok, _message = self.game_manager.add_to_library(gid)
            except (GameManagerError, sqlite3.Error, OSError, ValueError):
                failed += 1
                continue
            if ok:
                added += 1
            else:
                failed += 1
        if added:
            self._emit({"type": "library_changed"})
        parts = [f"Added {added} game(s)"]
        if skipped:
            parts.append(f"{skipped} already in library")
        if failed:
            parts.append(f"{failed} failed")
        return {"added": added, "failed": failed, "message": ", ".join(parts)}

    def get_library(self) -> dict[str, Any]:
        try:
            games = []
            for entry in self.game_manager.get_library():
                games.append(
                    {
                        "game_id": str(entry["game_id"]),
                        "name": entry["name"],
                        "icon_hash": entry.get("icon_hash"),
                        "process_name": entry["process_name"],
                        "is_running": entry.get("is_running", False),
                    }
                )
            return {"games": games}
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"games": [], "error": str(e)}

    def remove_from_library(self, game_id: int | str) -> dict[str, Any]:
        parsed = self._parse_game_id(game_id)
        if parsed is None:
            return {"ok": False, "message": "Invalid game id"}
        try:
            ok, message = self.game_manager.remove_from_library(parsed)
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to remove game: {e}"}
        if ok:
            self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def remove_many(self, game_ids: list[int | str]) -> dict[str, Any]:
        removed, failed = 0, 0
        ids: list[int] = []
        for g in game_ids or []:
            parsed = self._parse_game_id(g)
            if parsed is None:
                failed += 1
            else:
                ids.append(parsed)
        for gid in ids:
            try:
                ok, _message = self.game_manager.remove_from_library(gid)
            except (GameManagerError, sqlite3.Error, OSError, ValueError):
                failed += 1
                continue
            if ok:
                removed += 1
            else:
                failed += 1
        if removed:
            self._emit({"type": "library_changed"})
        parts = [f"Removed {removed} game(s)"]
        if failed:
            parts.append(f"{failed} failed")
        return {"removed": removed, "failed": failed, "message": ", ".join(parts)}

    def repair_library(self) -> dict[str, Any]:
        try:
            summary = self.game_manager.repair_library()
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Repair failed: {e}", "summary": {}}
        self._emit({"type": "library_changed"})
        message = (
            f"Repair complete: {summary.get('dangling_removed', 0)} dangling "
            f"removed, {summary.get('exes_recreated', 0)} exes recreated, "
            f"{summary.get('refresh_refreshed', 0)} updated, "
            f"{summary.get('warnings', 0)} warnings."
        )
        return {"ok": True, "message": message, "summary": summary}

    # -- processes -------------------------------------------------------
    def start_game(self, game_id: int | str) -> dict[str, Any]:
        parsed = self._parse_game_id(game_id)
        if parsed is None:
            return {"ok": False, "message": "Invalid game id"}
        try:
            ok, message = self.game_manager.start_game(parsed)
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to start game: {e}"}
        if ok:
            self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def stop_game(self, game_id: int | str) -> dict[str, Any]:
        parsed = self._parse_game_id(game_id)
        if parsed is None:
            return {"ok": False, "message": "Invalid game id"}
        try:
            ok, message = self.game_manager.stop_game(parsed)
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to stop game: {e}"}
        if ok:
            self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def stop_all_games(self) -> dict[str, int]:
        stopped = self.game_manager.stop_all_games()
        self._emit({"type": "library_changed"})
        return {"stopped": stopped}

    # -- quests ----------------------------------------------------------
    # Everything below reads the running Discord client, never the REST API.
    def discord_status(self) -> dict[str, Any]:
        if self.quest_service is None:
            return {
                "installed": False,
                "running": False,
                "connected": False,
                "hint": "Quest support is unavailable in this build.",
            }
        try:
            return self.quest_service.status()
        except (DiscordNativeError, OSError, ValueError) as e:
            return {
                "installed": False,
                "running": False,
                "connected": False,
                "hint": str(e),
            }

    def get_quests(self, force: bool = False) -> dict[str, Any]:
        if self.quest_service is None:
            return {
                "connected": False,
                "quests": [],
                "error": "Quest support is unavailable in this build.",
            }
        try:
            return self.quest_service.list_quests(force=bool(force))
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"connected": False, "quests": [], "error": str(e)}

    def connect_discord(self) -> dict[str, Any]:
        """Enable quest reading, restarting Discord only if it is already open."""
        if self.quest_service is None:
            return {
                "ok": False,
                "message": "Quest support is unavailable in this build.",
            }
        try:
            ok, message = self.quest_service.native.connect()
        except (DiscordNativeError, OSError) as e:
            return {"ok": False, "message": str(e)}
        if ok:
            self.quest_service.invalidate()
        return {"ok": ok, "message": message}

    def open_quest_in_discord(self, quest_id: str = "") -> dict[str, Any]:
        """Bring Discord's quest page forward so a quest can be accepted."""
        if not isinstance(quest_id, str):
            quest_id = ""
        try:
            os.startfile("discord://-/quest-home")
        except (OSError, AttributeError) as e:
            return {"ok": False, "message": f"Could not open Discord: {e}"}
        _focus_discord()
        return {"ok": True, "message": "Opened Discord on the quest page"}

    def claim_quest_reward(self, quest_id: str) -> dict[str, Any]:
        """Claim a finished quest, handing a captcha to the Discord window."""
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(quest_id, str) or not quest_id.strip():
            return {"ok": False, "message": "Invalid quest id"}
        try:
            ok, message, captcha = self.quest_service.claim_reward(quest_id.strip())
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to claim the reward: {e}"}
        if captcha:
            # Discord's own claim button carries the challenge, so put the user
            # in front of it rather than leaving them to find the page.
            try:
                os.startfile("discord://-/quest-home")
            except (OSError, AttributeError):
                pass
            _focus_discord()
        if ok:
            self._emit({"type": "quests_changed"})
        return {"ok": ok, "message": message, "needs_captcha": captcha}

    def start_discord(self) -> dict[str, Any]:
        """Launch Discord with quest reading enabled; never restarts it."""
        if self.quest_service is None:
            return {
                "ok": False,
                "message": "Quest support is unavailable in this build.",
            }
        try:
            ok, message = self.quest_service.native.start()
        except (DiscordNativeError, OSError) as e:
            return {"ok": False, "message": str(e)}
        if ok:
            self.quest_service.invalidate()
        return {"ok": ok, "message": message}

    # -- silent connection -------------------------------------------------
    # One-time change to the Windows launch entries, so every Discord start
    # carries the debug switch and quest reads never need a restart again.
    def silent_mode_status(self) -> dict[str, Any]:
        try:
            return discord_setup.summary()
        except (OSError, ValueError) as e:
            return {"enabled": False, "wanted": False, "launchers": [], "error": str(e)}

    def enable_silent_mode(self) -> dict[str, Any]:
        try:
            result = discord_setup.enable()
        except (OSError, ValueError) as e:
            return {"ok": False, "message": str(e), "updated": [], "failed": []}
        if self.quest_service is not None:
            self.quest_service.invalidate()
        return result

    def disable_silent_mode(self) -> dict[str, Any]:
        try:
            result = discord_setup.disable()
        except (OSError, ValueError) as e:
            return {"ok": False, "message": str(e), "restored": [], "failed": []}
        if result.get("ok"):
            return {**result, "message": "Silent connection is off. Discord starts normally again."}
        return {
            **result,
            "message": "Some launch entries could not be restored: "
            + "; ".join(result.get("failed") or []),
        }

    def start_quest(self, quest_id: str) -> dict[str, Any]:
        if self.quest_service is None:
            return {
                "ok": False,
                "message": "Quest support is unavailable in this build.",
            }
        if not isinstance(quest_id, str) or not quest_id.strip():
            return {"ok": False, "message": "Invalid quest id"}
        try:
            ok, message = self.quest_service.start_quest(quest_id.strip())
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to start quest: {e}"}
        self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def accept_quest(self, quest_id: str) -> dict[str, Any]:
        """Accept a quest through the running client, no window opened."""
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(quest_id, str) or not quest_id.strip():
            return {"ok": False, "message": "Invalid quest id"}
        try:
            ok, message = self.quest_service.accept_quest(quest_id.strip())
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to accept the quest: {e}"}
        return {"ok": ok, "message": message}

    def start_quest_queue(self, quest_ids: list[str] | None = None) -> dict[str, Any]:
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(quest_ids, (list, tuple)):
            return {"ok": False, "message": "Select the quests to start"}
        try:
            ok, message = self.quest_service.start_queue(list(quest_ids))
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to queue quests: {e}"}
        if ok:
            self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    def clear_quest_queue(self) -> dict[str, Any]:
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        try:
            count = self.quest_service.clear_queue()
        except (OSError, ValueError) as e:
            return {"ok": False, "message": f"Could not clear the queue: {e}"}
        return {"ok": True, "cleared": count, "message": f"Cleared {count} queued quest(s)"}

    def skip_quest_watch(self) -> dict[str, Any]:
        """Stop waiting for the video the queue opened in Discord."""
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        try:
            ok, message = self.quest_service.skip_watch()
        except (OSError, ValueError) as e:
            return {"ok": False, "message": f"Could not skip the video: {e}"}
        return {"ok": ok, "message": message}

    def reorder_quest_queue(self, quest_ids: list[str] | None = None) -> dict[str, Any]:
        """Put the pending queue in the order the user dragged it into."""
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(quest_ids, (list, tuple)):
            return {"ok": False, "message": "Invalid queue order"}
        try:
            ok, message = self.quest_service.reorder_queue(list(quest_ids))
        except (OSError, ValueError, TypeError) as e:
            return {"ok": False, "message": f"Could not reorder the queue: {e}"}
        return {"ok": ok, "message": message}

    def remove_from_quest_queue(self, quest_id: str) -> dict[str, Any]:
        """Drop one quest from the pending queue."""
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(quest_id, str) or not quest_id.strip():
            return {"ok": False, "message": "Invalid quest id"}
        try:
            ok, message = self.quest_service.drop_queue_item(quest_id.strip())
        except (OSError, ValueError, TypeError) as e:
            return {"ok": False, "message": f"Could not update the queue: {e}"}
        return {"ok": ok, "message": message}

    def get_quest_prefs(self) -> dict[str, Any]:
        if self.quest_service is None:
            return {"ok": False, "prefs": quest_prefs.DEFAULTS}
        try:
            return {"ok": True, "prefs": self.quest_service.prefs()}
        except (OSError, ValueError) as e:
            return {"ok": False, "prefs": quest_prefs.DEFAULTS, "message": str(e)}

    def set_quest_prefs(self, values: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.quest_service is None:
            return {"ok": False, "message": "Quest support is unavailable in this build."}
        if not isinstance(values, dict):
            return {"ok": False, "message": "Invalid quest settings"}
        try:
            updated = self.quest_service.update_prefs(values)
        except (OSError, ValueError, TypeError) as e:
            return {"ok": False, "message": f"Could not save quest settings: {e}"}
        return {"ok": True, "prefs": updated, "message": "Quest settings saved"}

    def stop_quest(self, quest_id: str) -> dict[str, Any]:
        if self.quest_service is None:
            return {
                "ok": False,
                "message": "Quest support is unavailable in this build.",
            }
        if not isinstance(quest_id, str) or not quest_id.strip():
            return {"ok": False, "message": "Invalid quest id"}
        try:
            ok, message = self.quest_service.stop_quest(quest_id.strip())
        except (DiscordNativeError, sqlite3.Error, OSError, ValueError) as e:
            return {"ok": False, "message": f"Failed to stop quest: {e}"}
        self._emit({"type": "library_changed"})
        return {"ok": ok, "message": message}

    # -- stats -----------------------------------------------------------
    def get_stats(self) -> dict[str, int]:
        try:
            return self.game_manager.get_cache_stats()
        except (GameManagerError, sqlite3.Error, OSError, ValueError):
            return {"cached_games": 0, "library_games": 0, "running_processes": 0}

    def get_running(self) -> dict[str, list[str]]:
        try:
            return {"running": [str(g) for g in self.game_manager.get_running_games()]}
        except (GameManagerError, sqlite3.Error, OSError, ValueError):
            return {"running": []}

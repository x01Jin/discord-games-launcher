"""Discord Games Launcher - pywebview JS bridge.

Exposes GameManager operations to the React frontend as JSON-only
methods on ``window.pywebview.api``. State changes push through
``dcgl`` CustomEvents.
"""

import sqlite3
from collections.abc import Callable
from typing import Any

from launcher.game_manager import GameManager, GameManagerError


class Bridge:
    """JS API for the webview frontend. All returns must be JSON-serializable."""

    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager
        self.push: Callable[[dict[str, Any]], None] | None = None

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
            games = self.game_manager.get_all_games(limit=limit + offset)[offset:]
            # Filter: only games with at least one win32 executable
            playable = [
                g for g in games if any(e.get("os") == "win32" for e in g.executables)
            ]
            # Raw IDs (not the cache-JOINed view): dangling rows must still
            # read as in-library so add/remove stay consistent.
            library_ids = self.game_manager.db.get_library_ids()
            return {
                "games": [
                    self._serialize_game(g, g.id in library_ids) for g in playable
                ],
                "total": self.game_manager.get_cache_stats()["cached_games"],
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"games": [], "total": 0, "error": str(e)}

    def search_games(self, query: str, limit: int = 50) -> dict[str, Any]:
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50
        try:
            # Fetch extra to account for non-Win games being filtered out
            games = self.game_manager.search_games(str(query), limit=limit * 3)
            playable = [
                g for g in games if any(e.get("os") == "win32" for e in g.executables)
            ]
            library_ids = self.game_manager.db.get_library_ids()
            return {
                "games": [
                    self._serialize_game(g, g.id in library_ids)
                    for g in playable[:limit]
                ]
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"games": [], "error": str(e)}

    def sync_catalogue(self) -> dict[str, Any]:
        try:
            synced, count = self.game_manager.sync_games(force=True)
            self._emit({"type": "library_changed"})
            return {
                "synced": synced,
                "count": count,
                "message": (
                    f"Synced {count:,} games from Discord"
                    if synced
                    else "Cache is up to date"
                ),
            }
        except (GameManagerError, sqlite3.Error, OSError, ValueError) as e:
            return {"synced": False, "count": 0, "message": f"Sync failed: {e}"}

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

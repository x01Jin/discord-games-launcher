import json
import sqlite3
import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from launcher.database_schema import SchemaMixin
from launcher.models import Game, LibraryGame

_WIN32_PREDICATE = (
    "EXISTS (SELECT 1 FROM json_each(games_cache.executables) "
    "WHERE json_extract(value, '$.os') = 'win32')"
)


class Database(SchemaMixin):
    EXPECTED_SCHEMA_VERSION = 2

    _STATS_TTL_SECONDS = 3.0

    def __init__(self, db_path: Path, logger=None):
        self.db_path = db_path
        self.logger = logger
        self._stats_cache: tuple[float, dict[str, int]] | None = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_last_sync(self) -> datetime | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'last_sync'"
            ).fetchone()
            if row:
                last_sync = datetime.fromisoformat(row[0])
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)
                return last_sync
            return None

    def set_last_sync(self, timestamp: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO cache_metadata (key, value, updated_at)
                    VALUES ('last_sync', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP""",
                (timestamp.isoformat(),),
            )

    def needs_sync(self, max_age_days: int = 7) -> bool:
        last_sync = self.get_last_sync()
        if not last_sync:
            return True
        return datetime.now(timezone.utc) - last_sync > timedelta(days=max_age_days)

    def get_metadata_value(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    def set_metadata_value(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO cache_metadata (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP""",
                (key, value),
            )

    def save_games(self, games: list[dict[str, Any]]) -> int:
        skipped = 0
        with self._connect() as conn:
            for game in games:
                if not isinstance(game, dict) or game.get("id") is None:
                    skipped += 1
                    continue
                try:
                    conn.execute(
                        """INSERT INTO games_cache
                        (id, name, aliases, executables, icon_hash, themes, is_published, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        aliases = excluded.aliases,
                        executables = excluded.executables,
                        icon_hash = excluded.icon_hash,
                        themes = excluded.themes,
                        is_published = excluded.is_published,
                        cached_at = CURRENT_TIMESTAMP""",
                        (
                            game.get("id"),
                            game.get("name", ""),
                            json.dumps(game.get("aliases", [])),
                            json.dumps(game.get("executables", [])),
                            game.get("icon_hash"),
                            json.dumps(game.get("themes", [])),
                            1 if game.get("isPublished", True) else 0,
                        ),
                    )
                except (sqlite3.Error, TypeError, ValueError):
                    skipped += 1
        if games:
            self._invalidate_stats()
        return skipped

    def get_game(self, game_id: int) -> Optional["Game"]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM games_cache WHERE id = ?", (game_id,)
            ).fetchone()
            if row:
                return self._row_to_game(row)
            return None

    def get_all_games(self, limit: int | None = None) -> list["Game"]:
        with self._connect() as conn:
            query = "SELECT * FROM games_cache ORDER BY name"
            if limit:
                query += f" LIMIT {limit}"
            rows = conn.execute(query).fetchall()
            return [self._row_to_game(row) for row in rows]

    def get_games_page(
        self, limit: int = 200, offset: int = 0, win32_only: bool = True
    ) -> list["Game"]:
        where = f"WHERE {_WIN32_PREDICATE}" if win32_only else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM games_cache {where}
                    ORDER BY name
                    LIMIT ? OFFSET ?""",
                (max(1, int(limit)), max(0, int(offset))),
            ).fetchall()
            return [self._row_to_game(row) for row in rows]

    def get_games(self, game_ids: Iterable[int]) -> dict[int, "Game"]:
        wanted = sorted({int(gid) for gid in game_ids})
        found: dict[int, Game] = {}
        if not wanted:
            return found
        with self._connect() as conn:
            for start in range(0, len(wanted), 500):
                chunk = wanted[start : start + 500]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT * FROM games_cache WHERE id IN ({placeholders})",
                    chunk,
                ).fetchall()
                for row in rows:
                    game = self._row_to_game(row)
                    found[game.id] = game
        return found

    def ensure_game_row(
        self,
        game_id: int,
        name: str,
        icon_hash: str | None,
        executables: list[dict[str, Any]],
    ) -> bool:
        try:
            payload = json.dumps(executables)
        except (TypeError, ValueError):
            return False
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO games_cache
                       (id, name, aliases, executables, icon_hash, themes, is_published, cached_at)
                       VALUES (?, ?, '[]', ?, ?, '[]', 1, CURRENT_TIMESTAMP)
                       ON CONFLICT(id) DO NOTHING""",
                    (game_id, name, payload, icon_hash),
                )
        except (sqlite3.Error, TypeError, ValueError):
            return False
        self._invalidate_stats()
        return True

    def search_games(
        self, query: str, limit: int = 100, win32_only: bool = True
    ) -> list["Game"]:
        conditions = ["name LIKE ?"]
        if win32_only:
            conditions.append(_WIN32_PREDICATE)
        where = " AND ".join(conditions)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM games_cache
                    WHERE {where}
                    ORDER BY name
                    LIMIT ?""",
                (f"%{query}%", max(1, int(limit))),
            ).fetchall()
            return [self._row_to_game(row) for row in rows]

    def _row_to_game(self, row: sqlite3.Row) -> "Game":
        return Game(
            id=row["id"],
            name=row["name"],
            aliases=json.loads(row["aliases"] or "[]"),
            executables=json.loads(row["executables"] or "[]"),
            icon_hash=row["icon_hash"],
            themes=json.loads(row["themes"] or "[]"),
            is_published=bool(row["is_published"]),
            cached_at=datetime.fromisoformat(row["cached_at"]),
        )

    def add_to_library(
        self,
        game_id: int,
        executable_path: str,
        process_name: str,
        normalized_process_name: str,
        executables: list[dict[str, Any]],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO user_library (game_id, executable_path, process_name, normalized_process_name, executables, added_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(game_id) DO UPDATE SET
                    executable_path = excluded.executable_path,
                    process_name = excluded.process_name,
                    normalized_process_name = excluded.normalized_process_name,
                    executables = excluded.executables""",
                (
                    game_id,
                    executable_path,
                    process_name,
                    normalized_process_name,
                    json.dumps(executables),
                ),
            )
        self._invalidate_stats()

    def remove_from_library(self, game_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM running_processes WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM executable_history WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM user_library WHERE game_id = ?", (game_id,))
        self._invalidate_stats()

    def get_library_ids(self) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT game_id FROM user_library").fetchall()
            return {row["game_id"] for row in rows}

    def get_cached_game_ids(self) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM games_cache").fetchall()
            return {row["id"] for row in rows}

    def get_library(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT l.*, g.name, g.aliases, g.icon_hash, g.executables as game_executables
                FROM user_library l
                JOIN games_cache g ON l.game_id = g.id
                ORDER BY l.added_at DESC
            """).fetchall()

            result = []
            for row in rows:
                result.append(
                    {
                        "game_id": row["game_id"],
                        "name": row["name"],
                        "aliases": json.loads(row["aliases"] or "[]"),
                        "icon_hash": row["icon_hash"],
                        "executable_path": row["executable_path"],
                        "process_name": row["process_name"],
                        "normalized_process_name": row["normalized_process_name"],
                        "added_at": row["added_at"],
                        "executables": json.loads(row["executables"] or "[]"),
                        "game_executables": json.loads(row["game_executables"] or "[]"),
                    }
                )
            return result

    def is_in_library(self, game_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM user_library WHERE game_id = ?", (game_id,)
            ).fetchone()
            return row is not None

    def get_library_game(self, game_id: int) -> Optional["LibraryGame"]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_library WHERE game_id = ?", (game_id,)
            ).fetchone()
            if row:
                return LibraryGame(
                    game_id=row["game_id"],
                    executable_path=row["executable_path"],
                    process_name=row["process_name"],
                    normalized_process_name=row["normalized_process_name"],
                    executables=json.loads(row["executables"] or "[]"),
                    added_at=datetime.fromisoformat(row["added_at"]),
                )
            return None

    def get_preferred_executable(
        self, game_id: int
    ) -> tuple[dict[str, Any], int] | None:
        with self._connect() as conn:
            history_rows = conn.execute(
                """SELECT executable_name, success_count, failure_count
                   FROM executable_history
                   WHERE game_id = ?""",
                (game_id,),
            ).fetchall()

            history_map = {}
            for row in history_rows:
                exe_name = row["executable_name"]
                success_count = row["success_count"]
                failure_count = row["failure_count"]
                score = (success_count * 20) - failure_count
                history_map[exe_name] = score

            lib_game = self.get_library_game(game_id)
            if not lib_game:
                return None

            best_exe = None
            best_score = 0

            for exe in lib_game.executables:
                exe_name = exe.get("name", "")
                score = history_map.get(exe_name, 0)

                if score > best_score:
                    best_score = score
                    best_exe = exe

            return (best_exe, best_score) if best_exe else None

    def record_executable_attempt(
        self, game_id: int, executable_name: str, success: bool
    ) -> None:
        with self._connect() as conn:
            if success:
                conn.execute(
                    """INSERT INTO executable_history (game_id, executable_name, success_count, failure_count, last_attempt_at, last_success_at)
                        VALUES (?, ?, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(game_id, executable_name) DO UPDATE SET
                        success_count = success_count + 1,
                        last_attempt_at = CURRENT_TIMESTAMP,
                        last_success_at = CURRENT_TIMESTAMP""",
                    (game_id, executable_name),
                )
            else:
                conn.execute(
                    """INSERT INTO executable_history (game_id, executable_name, success_count, failure_count, last_attempt_at)
                        VALUES (?, ?, 0, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT(game_id, executable_name) DO UPDATE SET
                        failure_count = failure_count + 1,
                        last_attempt_at = CURRENT_TIMESTAMP""",
                    (game_id, executable_name),
                )

    def set_process_running(self, game_id: int, pid: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO running_processes (game_id, pid, started_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(game_id) DO UPDATE SET
                    pid = excluded.pid,
                    started_at = CURRENT_TIMESTAMP""",
                (game_id, pid),
            )
        self._invalidate_stats()

    def set_process_stopped(self, game_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM running_processes WHERE game_id = ?", (game_id,))
        self._invalidate_stats()

    def get_running_processes(self) -> dict[int, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT game_id, pid FROM running_processes").fetchall()
            return {row["game_id"]: row["pid"] for row in rows}

    def is_process_running(self, game_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM running_processes WHERE game_id = ?", (game_id,)
            ).fetchone()
            return row is not None

    def clear_cache(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM games_cache")
            conn.execute("DELETE FROM cache_metadata WHERE key = 'last_sync'")
        self._invalidate_stats()

    def _invalidate_stats(self) -> None:
        self._stats_cache = None

    def get_cache_stats(self) -> dict[str, int]:
        cached = self._stats_cache
        if cached is not None:
            stamp, value = cached
            if time.monotonic() - stamp < self._STATS_TTL_SECONDS:
                return dict(value)
        stats = self._compute_stats()
        self._stats_cache = (time.monotonic(), stats)
        return dict(stats)

    def _compute_stats(self) -> dict[str, int]:
        with self._connect() as conn:
            games_count = conn.execute("SELECT COUNT(*) FROM games_cache").fetchone()[0]
            library_count = conn.execute(
                "SELECT COUNT(*) FROM user_library"
            ).fetchone()[0]
            running_count = conn.execute(
                "SELECT COUNT(*) FROM running_processes"
            ).fetchone()[0]
            history_count = conn.execute(
                "SELECT COUNT(*) FROM executable_history"
            ).fetchone()[0]

            no_win_count = conn.execute(
                """SELECT COUNT(*) FROM games_cache
                   WHERE NOT EXISTS (
                       SELECT 1 FROM json_each(executables)
                       WHERE json_extract(value, '$.os') = 'win32'
                   )"""
            ).fetchone()[0]

            return {
                "cached_games": games_count,
                "library_games": library_count,
                "running_processes": running_count,
                "executable_history": history_count,
                "games_no_win_exes": no_win_count,
            }

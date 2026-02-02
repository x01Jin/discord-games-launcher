"""Discord Games Launcher - Database module.

Handles all SQLite operations for caching Discord API data and user library.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class Game:
    """Represents a Discord-supported game."""

    id: int
    name: str
    aliases: List[str]
    executables: List[Dict[str, Any]]
    icon_hash: Optional[str]
    themes: List[str]
    is_published: bool
    cached_at: datetime


@dataclass
class LibraryGame:
    """Represents a game in the user's library."""

    game_id: int
    executable_path: Optional[str]
    process_name: str
    normalized_process_name: str
    executables: List[Dict[str, Any]]
    added_at: datetime


@dataclass
class ExecutableHistory:
    """Represents executable attempt history."""

    id: int
    game_id: int
    executable_name: str
    success_count: int
    failure_count: int
    last_attempt_at: datetime
    last_success_at: Optional[datetime]


class Database:
    """SQLite database manager for Discord Games Launcher."""

    EXPECTED_SCHEMA_VERSION = 2

    def __init__(self, db_path: Path, logger=None):
        self.db_path = db_path
        self.logger = logger
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _validate_schema(self) -> bool:
        """Check if current schema matches expected version.

        Returns True if schema is valid, False otherwise.
        """
        try:
            with self._connect() as conn:
                # Check schema_version table
                row = conn.execute(
                    "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
                ).fetchone()
                if not row:
                    return False

                current_version = int(row[0])
                if current_version != self.EXPECTED_SCHEMA_VERSION:
                    return False

                # Check if all required tables exist
                required_tables = [
                    "games_cache",
                    "user_library",
                    "executable_history",
                    "running_processes",
                    "cache_metadata",
                ]

                for table_name in required_tables:
                    result = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,),
                    ).fetchone()
                    if not result:
                        return False

                # Check if user_library has executables and normalized_process_name columns
                result = conn.execute("PRAGMA table_info(user_library)").fetchall()
                columns = [row["name"] for row in result]
                if "executables" not in columns:
                    return False
                if "normalized_process_name" not in columns:
                    return False

            return True

        except Exception:
            return False

    def _init_db(self) -> None:
        """Initialize database schema with validation and auto-recreate."""
        schema_valid = self._validate_schema()

        if not schema_valid:
            if self.logger:
                self.logger.database_recreate()
            if self.db_path.exists():
                self.db_path.unlink()

        with self._connect() as conn:
            # Games cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS games_cache (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    aliases TEXT,
                    executables TEXT,
                    icon_hash TEXT,
                    themes TEXT,
                    is_published INTEGER DEFAULT 1,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User library table with executables and normalized_process_name columns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_library (
                    game_id INTEGER PRIMARY KEY,
                    executable_path TEXT,
                    process_name TEXT NOT NULL,
                    normalized_process_name TEXT,
                    executables TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games_cache(id)
                )
            """)

            # Executable history table for smart selection
            conn.execute("""
                CREATE TABLE IF NOT EXISTS executable_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    executable_name TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_success_at TIMESTAMP,
                    UNIQUE(game_id, executable_name),
                    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
                )
            """)

            # Running processes tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS running_processes (
                    game_id INTEGER PRIMARY KEY,
                    pid INTEGER,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
                )
            """)

            # Cache metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Set schema version
            conn.execute(
                """
                INSERT INTO cache_metadata (key, value, updated_at)
                VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
                (str(self.EXPECTED_SCHEMA_VERSION),),
            )

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_name ON games_cache(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_cached_at ON games_cache(cached_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exec_history_game ON executable_history(game_id)
            """)

    def get_last_sync(self) -> Optional[datetime]:
        """Get timestamp of last API sync."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'last_sync'"
            ).fetchone()
            if row:
                return datetime.fromisoformat(row[0])
            return None

    def set_last_sync(self, timestamp: datetime) -> None:
        """Set timestamp of last API sync."""
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
        """Check if cache needs to be synced with API."""
        last_sync = self.get_last_sync()
        if not last_sync:
            return True
        return datetime.now() - last_sync > timedelta(days=max_age_days)

    def save_games(self, games: List[Dict[str, Any]]) -> None:
        """Save or update games from API to cache."""
        with self._connect() as conn:
            for game in games:
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
                        game.get("icon"),
                        json.dumps(game.get("themes", [])),
                        1 if game.get("isPublished", True) else 0,
                    ),
                )

    def get_game(self, game_id: int) -> Optional["Game"]:
        """Get a single game by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM games_cache WHERE id = ?", (game_id,)
            ).fetchone()
            if row:
                return self._row_to_game(row)
            return None

    def get_all_games(self, limit: Optional[int] = None) -> List["Game"]:
        """Get all cached games."""
        with self._connect() as conn:
            query = "SELECT * FROM games_cache ORDER BY name"
            if limit:
                query += f" LIMIT {limit}"
            rows = conn.execute(query).fetchall()
            return [self._row_to_game(row) for row in rows]

    def search_games(self, query: str, limit: int = 100) -> List["Game"]:
        """Search games by name or alias."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM games_cache
                   WHERE name LIKE ?
                   ORDER BY name
                   LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
            return [self._row_to_game(row) for row in rows]

    def _row_to_game(self, row: sqlite3.Row) -> "Game":
        """Convert database row to Game dataclass."""
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
        executables: List[Dict[str, Any]],
    ) -> None:
        """Add a game to user's library with all executable candidates."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO user_library (game_id, executable_path, process_name, normalized_process_name, executables, added_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(game_id) DO UPDATE SET
                    executable_path = excluded.executable_path,
                    process_name = excluded.process_name,
                    normalized_process_name = excluded.normalized_process_name,
                    executables = excluded.executables""",
                (game_id, executable_path, process_name, normalized_process_name, json.dumps(executables)),
            )

    def remove_from_library(self, game_id: int) -> None:
        """Remove a game from user's library."""
        with self._connect() as conn:
            conn.execute("DELETE FROM running_processes WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM executable_history WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM user_library WHERE game_id = ?", (game_id,))

    def get_library(self) -> List[Dict[str, Any]]:
        """Get all games in user's library with full game info."""
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
        """Check if a game is in user's library."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM user_library WHERE game_id = ?", (game_id,)
            ).fetchone()
            return row is not None

    def get_library_game(self, game_id: int) -> Optional["LibraryGame"]:
        """Get a library game by ID."""
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
    ) -> Optional[Tuple[Dict[str, Any], int]]:
        """Get the best executable for a game based on history.

        Returns:
            Tuple of (executable_data, score) or None
        """
        with self._connect() as conn:
            # Get all executable history for this game
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
                # Score formula: (success_count * 20) - failure_count
                score = (success_count * 20) - failure_count
                history_map[exe_name] = score

            # Get library game to check executables
            lib_game = self.get_library_game(game_id)
            if not lib_game:
                return None

            # Find best executable from library executables
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
        """Record an executable attempt result.

        Args:
            game_id: The Discord game ID
            executable_name: Name of the executable (e.g., "bg3.exe")
            success: Whether the detection was successful
        """
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
        """Track a running dummy process."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO running_processes (game_id, pid, started_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(game_id) DO UPDATE SET
                    pid = excluded.pid,
                    started_at = CURRENT_TIMESTAMP""",
                (game_id, pid),
            )

    def set_process_stopped(self, game_id: int) -> None:
        """Remove process tracking when stopped."""
        with self._connect() as conn:
            conn.execute("DELETE FROM running_processes WHERE game_id = ?", (game_id,))

    def get_running_processes(self) -> Dict[int, int]:
        """Get all running processes as {game_id: pid}."""
        with self._connect() as conn:
            rows = conn.execute("SELECT game_id, pid FROM running_processes").fetchall()
            return {row["game_id"]: row["pid"] for row in rows}

    def is_process_running(self, game_id: int) -> bool:
        """Check if a process is marked as running for this game."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM running_processes WHERE game_id = ?", (game_id,)
            ).fetchone()
            return row is not None

    def clear_cache(self) -> None:
        """Clear all cached games (use with caution)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM games_cache")
            conn.execute("DELETE FROM cache_metadata WHERE key = 'last_sync'")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
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

            return {
                "cached_games": games_count,
                "library_games": library_count,
                "running_processes": running_count,
                "executable_history": history_count,
            }

from __future__ import annotations

import sqlite3


class SchemaMixin:
    def _validate_schema(self) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
                ).fetchone()
                if not row:
                    return False

                try:
                    current_version = int(str(row[0]).strip())
                except (ValueError, TypeError):
                    return False
                if current_version != self.EXPECTED_SCHEMA_VERSION:
                    return False

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

                result = conn.execute("PRAGMA table_info(user_library)").fetchall()
                columns = [row["name"] for row in result]
                if "executables" not in columns:
                    return False
                if "normalized_process_name" not in columns:
                    return False

            return True

        except (sqlite3.Error, OSError, ValueError, TypeError):
            return False

    def _migrate_schema(self) -> bool:
        try:
            with self._connect() as conn:
                try:
                    row = conn.execute(
                        "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
                    ).fetchone()
                except sqlite3.Error:
                    row = None
                current: int | None = None
                if row is not None:
                    try:
                        current = int(str(row[0]).strip())
                    except (ValueError, TypeError):
                        current = None
                if current is not None and current > self.EXPECTED_SCHEMA_VERSION:
                    return False

                try:
                    cols = [
                        r["name"]
                        for r in conn.execute(
                            "PRAGMA table_info(user_library)"
                        ).fetchall()
                    ]
                except sqlite3.Error:
                    cols = []
                if cols:
                    for column in ("executables", "normalized_process_name"):
                        if column in cols:
                            continue
                        try:
                            conn.execute(
                                f"ALTER TABLE user_library ADD COLUMN {column} TEXT"
                            )
                        except sqlite3.OperationalError as e:
                            if "duplicate column" not in str(e).lower():
                                raise
                return True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return False

    def _init_db(self) -> None:
        if not self._validate_schema() and not self._migrate_schema():
            if self.logger:
                self.logger.database_recreate()
            if self.db_path.exists():
                self.db_path.unlink()

        with self._connect() as conn:
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS running_processes (
                    game_id INTEGER PRIMARY KEY,
                    pid INTEGER,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES user_library(game_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute(
                """
                INSERT INTO cache_metadata (key, value, updated_at)
                VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
                (str(self.EXPECTED_SCHEMA_VERSION),),
            )

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_name ON games_cache(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_cached_at ON games_cache(cached_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exec_history_game ON executable_history(game_id)
            """)


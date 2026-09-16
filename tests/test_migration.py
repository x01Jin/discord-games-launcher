"""Tests for non-destructive schema migration.

Usage:
    pytest tests/test_migration.py -v
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.database import Database


def _write_v1_db(db_path: Path) -> None:
    """Create a v1-shaped database: no schema version, no new columns."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE games_cache (
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
        CREATE TABLE user_library (
            game_id INTEGER PRIMARY KEY,
            executable_path TEXT,
            process_name TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games_cache(id)
        )
    """)
    conn.execute("""
        CREATE TABLE executable_history (
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
        CREATE TABLE running_processes (
            game_id INTEGER PRIMARY KEY,
            pid INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES user_library(game_id)
        )
    """)
    conn.execute("""
        CREATE TABLE cache_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT INTO games_cache (id, name) VALUES (?, ?)", (4242, "Legacy Game")
    )
    conn.execute(
        "INSERT INTO user_library (game_id, executable_path, process_name)"
        " VALUES (?, ?, ?)",
        (4242, "C:/games/4242/legacy.exe", "legacy.exe"),
    )
    conn.commit()
    conn.close()


def test_v1_database_migrates_without_data_loss():
    """Opening a v1 database upgrades it in place, preserving rows."""
    print("Testing v1 migration...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy.db"
        _write_v1_db(db_path)

        db = Database(db_path)

        assert db.is_in_library(4242)
        lib = db.get_library_game(4242)
        assert lib is not None
        assert lib.process_name == "legacy.exe"
        with db._connect() as conn:
            cols = [
                r["name"]
                for r in conn.execute("PRAGMA table_info(user_library)").fetchall()
            ]
            assert "executables" in cols
            assert "normalized_process_name" in cols
            version = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
            assert int(version) == Database.EXPECTED_SCHEMA_VERSION

    print("  PASSED")


def test_migrated_row_converges_through_refresh():
    """Migrated NULL blobs cause no crash and refresh backfills them."""
    print("Testing migration/refresh convergence...")

    from launcher.api import DiscordAPIClient
    from launcher.dummy_generator import DummyGenerator
    from launcher.game_manager import GameManager
    from launcher.process_manager import ProcessManager

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "legacy.db"
        _write_v1_db(db_path)
        template = tmpdir / "DummyGame.exe"
        template.write_bytes(b"fake-exe")

        db = Database(db_path)
        lib = db.get_library_game(4242)
        assert lib is not None
        assert lib.executables == []

        db.save_games(
            [
                {
                    "id": 4242,
                    "name": "Legacy Game",
                    "aliases": [],
                    "executables": [{"os": "win32", "name": "legacy.exe"}],
                    "icon_hash": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )
        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
        proc = ProcessManager(db, dummy_gen)
        mgr = GameManager(db, api, dummy_gen, proc)

        summary = mgr.refresh_library_candidates()

        assert summary["refreshed"] == 1
        lib = db.get_library_game(4242)
        assert lib is not None
        assert [e["name"] for e in lib.executables] == ["legacy.exe"]

    print("  PASSED")


def test_future_schema_version_triggers_recreate():
    """An unrecognized newer version falls back to recreate (last resort)."""
    print("Testing future-version fallback...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "future.db"
        _write_v1_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO cache_metadata (key, value) VALUES ('schema_version', '99')"
        )
        conn.commit()
        conn.close()

        Database(db_path)

        conn = sqlite3.connect(db_path)
        version = conn.execute(
            "SELECT value FROM cache_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]
        rows = conn.execute("SELECT COUNT(*) FROM user_library").fetchone()[0]
        conn.close()
        assert int(version) == Database.EXPECTED_SCHEMA_VERSION
        assert rows == 0

    print("  PASSED")

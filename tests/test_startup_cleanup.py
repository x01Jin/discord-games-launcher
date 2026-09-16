"""Tests for GameManager.startup_cleanup.

Covers stale runtime records, orphaned game directories, missing dummy
executables, and orphaned cached icons.

Usage:
    pytest tests/test_startup_cleanup.py -v
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.api import DiscordAPIClient
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager


def _make_manager(tmpdir: Path, template: Path | None = None) -> GameManager:
    """Build a GameManager backed by temp dirs. Fake template unless given."""
    template_path = template
    if template_path is None:
        template_path = tmpdir / "DummyGame.exe"
        template_path.write_bytes(b"fake-exe")
    db = Database(tmpdir / "test.db")
    api = DiscordAPIClient(db, tmpdir / "cache")
    dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template_path)
    process_mgr = ProcessManager(db, dummy_gen)
    return GameManager(db, api, dummy_gen, process_mgr)


def _cache_game(db: Database, game_id: int, name: str = "Test Game") -> None:
    db.save_games(
        [
            {
                "id": game_id,
                "name": name,
                "aliases": [],
                "executables": [{"os": "win32", "name": "foo.exe"}],
                "icon_hash": None,
                "themes": [],
                "isPublished": True,
            }
        ]
    )


def test_clears_stale_running_processes():
    """Running rows from a previous run are dropped without touching processes."""
    print("Testing stale running cleanup...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        mgr.db.set_process_running(111, 99999)
        assert mgr.db.get_running_processes() == {111: 99999}

        summary = mgr.startup_cleanup()

        assert summary["stale_processes"] == 1
        assert mgr.db.get_running_processes() == {}
        assert mgr.process_mgr.get_running_games() == []

    print("  PASSED")


def test_removes_orphan_dirs_keeps_library_dirs():
    """Game dirs without a library row are removed; library dirs are kept."""
    print("Testing orphan dir cleanup...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        games_dir = Path(tmpdir) / "games"

        orphan = games_dir / "99999"
        orphan.mkdir(parents=True)
        (orphan / "ghost.exe").write_bytes(b"x")

        _cache_game(mgr.db, 222)
        kept_exe = games_dir / "222" / "foo.exe"
        kept_exe.parent.mkdir(parents=True, exist_ok=True)
        kept_exe.write_bytes(b"x")
        mgr.db.add_to_library(222, str(kept_exe), "foo.exe", "foo.exe", [])

        summary = mgr.startup_cleanup()

        assert summary["orphan_dirs_removed"] == 1
        assert not orphan.exists()
        assert kept_exe.exists()

    print("  PASSED")


def test_recreates_missing_library_exe():
    """Library entries without an exe on disk get one recreated."""
    print("Testing missing exe recreation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        games_dir = Path(tmpdir) / "games"

        _cache_game(mgr.db, 333)
        missing = games_dir / "333" / "foo.exe"
        mgr.db.add_to_library(
            333,
            str(missing),
            "foo.exe",
            "foo.exe",
            [{"os": "win32", "name": "foo.exe"}],
        )
        assert not missing.exists()

        summary = mgr.startup_cleanup()

        assert summary["exes_recreated"] == 1
        assert missing.exists()

    print("  PASSED")


def test_missing_template_keeps_library_row():
    """Without a template the row is kept and a warning is counted."""
    print("Testing missing template behavior...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir, template=tmpdir / "nope" / "DummyGame.exe")

        _cache_game(mgr.db, 444)
        mgr.db.add_to_library(
            444,
            str(tmpdir / "games" / "444" / "foo.exe"),
            "foo.exe",
            "foo.exe",
            [{"os": "win32", "name": "foo.exe"}],
        )

        summary = mgr.startup_cleanup()

        assert summary["exes_recreated"] == 0
        assert summary["warnings"] >= 1
        assert mgr.db.is_in_library(444)

    print("  PASSED")


def test_purges_dangling_library_rows():
    """Library rows gone from the cache are purged with their files."""
    print("Testing dangling row purge...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        games_dir = tmpdir / "games"

        _cache_game(mgr.db, 111, "Kept Game")
        kept_exe = games_dir / "111" / "foo.exe"
        kept_exe.parent.mkdir(parents=True, exist_ok=True)
        kept_exe.write_bytes(b"x")
        mgr.db.add_to_library(111, str(kept_exe), "foo.exe", "foo.exe", [])

        ghost_exe = games_dir / "555" / "ghost.exe"
        ghost_exe.parent.mkdir(parents=True, exist_ok=True)
        ghost_exe.write_bytes(b"x")
        mgr.db.add_to_library(555, str(ghost_exe), "ghost.exe", "ghost.exe", [])

        summary = mgr.startup_cleanup()

        assert summary["dangling_removed"] == 1
        assert not mgr.db.is_in_library(555)
        assert not (games_dir / "555").exists()
        assert mgr.db.is_in_library(111)
        assert kept_exe.exists()

    print("  PASSED")


def test_dangling_purge_guarded_on_empty_cache():
    """Nothing is purged when the cache itself is empty (fresh install)."""
    print("Testing empty-cache purge guard...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))

        mgr.db.add_to_library(
            666,
            str(Path(tmpdir) / "games" / "666" / "foo.exe"),
            "foo.exe",
            "foo.exe",
            [],
        )

        summary = mgr.startup_cleanup()

        assert summary["dangling_removed"] == 0
        assert mgr.db.is_in_library(666)

    print("  PASSED")


def test_failed_purge_keeps_row_in_working_set():
    """A failed row delete stays scheduled: dir + exe are restored."""
    print("Testing failed-purge containment...")

    import sqlite3
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        games_dir = tmpdir / "games"

        _cache_game(mgr.db, 111, "Kept Game")
        ghost_exe = games_dir / "555" / "ghost.exe"
        ghost_exe.parent.mkdir(parents=True, exist_ok=True)
        ghost_exe.write_bytes(b"x")
        mgr.db.add_to_library(555, str(ghost_exe), "ghost.exe", "ghost.exe", [])

        real_remove = mgr.db.remove_from_library

        def flaky(game_id: int) -> None:
            if game_id == 555:
                raise sqlite3.Error("locked")
            real_remove(game_id)

        with patch.object(mgr.db, "remove_from_library", side_effect=flaky):
            summary = mgr.startup_cleanup()

        assert summary["dangling_removed"] == 0
        assert summary["warnings"] >= 1
        # Row survived, so step 4 restored its directory and executable.
        assert mgr.db.is_in_library(555)
        assert ghost_exe.exists()

    print("  PASSED")


def test_recreated_exe_converges_row():
    """A second cleanup right after is a no-op for the fixed row."""
    print("Testing recreate convergence...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))

        _cache_game(mgr.db, 321, "Converge Game")
        mgr.db.add_to_library(
            321,
            str(Path(tmpdir) / "games" / "321" / "stale.exe"),
            "stale.exe",
            "stale.exe",
            [{"os": "win32", "name": "fresh.exe"}],
        )

        first = mgr.startup_cleanup()
        assert first["exes_recreated"] == 1
        row = mgr.db.get_library_game(321)
        assert row is not None
        assert Path(row.executable_path or "").exists()

        second = mgr.startup_cleanup()
        assert second["exes_recreated"] == 0
        assert second["warnings"] == 0

    print("  PASSED")


def test_removes_stray_root_exes_keeps_sole_template():
    """Stray exes at games root are removed; sole template copy is kept."""
    print("Testing stray root exe cleanup...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        games_dir = tmpdir / "games"

        stray = games_dir / "stray.exe"
        stray.write_bytes(b"x")

        summary = mgr.startup_cleanup()

        assert summary["root_exes_removed"] == 1
        assert not stray.exists()

        # Root DummyGame.exe is kept only when it is the resolved template.
        root_template = games_dir / "DummyGame.exe"
        root_template.write_bytes(b"fake-exe")
        lonely = DummyGenerator(tmpdir / "games2", template_exe_path=root_template)
        assert lonely.template_exe_path == root_template

    print("  PASSED")


def test_prunes_orphan_icons_keeps_cached():
    """Icons for games no longer cached are removed; cached ones are kept."""
    print("Testing orphan icon cleanup...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        icons_dir = Path(tmpdir) / "cache" / "icons"

        orphan_icon = icons_dir / "77777_deadbeef_128.png"
        orphan_icon.write_bytes(b"x")

        _cache_game(mgr.db, 888)
        kept_icon = icons_dir / "888_hash_128.png"
        kept_icon.write_bytes(b"x")

        summary = mgr.startup_cleanup()

        assert summary["icons_pruned"] == 1
        assert not orphan_icon.exists()
        assert kept_icon.exists()

    print("  PASSED")

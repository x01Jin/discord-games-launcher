import os
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.api import DiscordAPIClient
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager


def _make_manager(tmpdir: Path) -> GameManager:
    template = tmpdir / "DummyGame.exe"
    template.write_bytes(b"fake-exe")
    db = Database(tmpdir / "test.db")
    api = DiscordAPIClient(db, tmpdir / "cache")
    dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
    process_mgr = ProcessManager(db, dummy_gen)
    return GameManager(db, api, dummy_gen, process_mgr)


def _seed_library(
    mgr: GameManager,
    tmpdir: Path,
    game_id: int,
    cache_exes: list[dict],
    stored_exes: list[dict],
    stored_name: str = "old.exe",
) -> Path:
    mgr.db.save_games(
        [
            {
                "id": game_id,
                "name": f"Game {game_id}",
                "aliases": [],
                "executables": cache_exes,
                "icon_hash": None,
                "themes": [],
                "isPublished": True,
            }
        ]
    )
    old_exe = tmpdir / "games" / str(game_id) / stored_name
    old_exe.parent.mkdir(parents=True, exist_ok=True)
    old_exe.write_bytes(b"x")
    mgr.db.add_to_library(game_id, str(old_exe), stored_name, stored_name, stored_exes)
    return old_exe


def test_refresh_replaces_superseded_exe_and_drops_old_file():
    print("Testing candidate refresh with replacement...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        old_exe = _seed_library(
            mgr,
            tmpdir,
            777,
            [{"os": "win32", "name": "new.exe"}],
            [{"os": "win32", "name": "old.exe"}],
        )

        summary = mgr.refresh_library_candidates()

        assert summary["refreshed"] == 1
        assert summary["exes_replaced"] == 1
        assert not old_exe.exists()
        new_exe = tmpdir / "games" / "777" / "new.exe"
        assert new_exe.exists()
        lib = mgr.db.get_library_game(777)
        assert lib is not None
        assert lib.process_name == "new.exe"

    print("  PASSED")


def test_refresh_updates_blob_without_file_churn():
    print("Testing candidate refresh without replacement...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        old_exe = _seed_library(
            mgr,
            tmpdir,
            778,
            [
                {"os": "win32", "name": "a.exe"},
                {"os": "win32", "name": "b.exe"},
            ],
            [{"os": "win32", "name": "a.exe"}],
            stored_name="a.exe",
        )

        summary = mgr.refresh_library_candidates()

        assert summary["refreshed"] == 1
        assert summary["exes_replaced"] == 0
        assert old_exe.exists()
        lib = mgr.db.get_library_game(778)
        assert lib is not None
        assert [e["name"] for e in lib.executables] == ["a.exe", "b.exe"]

    print("  PASSED")


def test_refresh_skips_running_games():
    print("Testing refresh skip for running games...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        template = tmpdir / "DummyGame.exe"
        template.write_bytes(b"fake-exe")
        db = Database(tmpdir / "test.db")
        db.save_games(
            [
                {
                    "id": 779,
                    "name": "Running Game",
                    "aliases": [],
                    "executables": [{"os": "win32", "name": "new.exe"}],
                    "icon_hash": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )
        old_exe = tmpdir / "games" / "779" / "old.exe"
        old_exe.parent.mkdir(parents=True, exist_ok=True)
        old_exe.write_bytes(b"x")
        db.add_to_library(779, str(old_exe), "old.exe", "old.exe", [])
        db.set_process_running(779, os.getpid())

        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
        process_mgr = ProcessManager(db, dummy_gen)
        mgr = GameManager(db, api, dummy_gen, process_mgr)

        summary = mgr.refresh_library_candidates()

        assert summary["skipped_running"] == 1
        assert summary["refreshed"] == 0
        assert old_exe.exists()

    print("  PASSED")


def test_repair_merges_cleanup_and_refresh_summaries():
    print("Testing repair composition...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)

        ghost_dir = tmpdir / "games" / "555"
        ghost_dir.mkdir(parents=True)
        (ghost_dir / "ghost.exe").write_bytes(b"x")
        mgr.db.add_to_library(
            555, str(ghost_dir / "ghost.exe"), "ghost.exe", "ghost.exe", []
        )

        _seed_library(
            mgr,
            tmpdir,
            777,
            [{"os": "win32", "name": "new.exe"}],
            [{"os": "win32", "name": "old.exe"}],
        )

        summary = mgr.repair_library()

        assert summary["dangling_removed"] == 1
        assert summary["refresh_refreshed"] == 1
        assert summary["refresh_exes_replaced"] == 1
        assert not ghost_dir.exists()
        assert not mgr.db.is_in_library(555)

    print("  PASSED")


def test_repair_skips_live_dangling_game():
    print("Testing repair live-game guard...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        template = tmpdir / "DummyGame.exe"
        template.write_bytes(b"fake-exe")
        db = Database(tmpdir / "test.db")
        db.save_games(
            [
                {
                    "id": 111,
                    "name": "Anchor",
                    "aliases": [],
                    "executables": [],
                    "icon_hash": None,
                    "themes": [],
                    "isPublished": True,
                }
            ]
        )
        ghost_exe = tmpdir / "games" / "555" / "ghost.exe"
        ghost_exe.parent.mkdir(parents=True, exist_ok=True)
        ghost_exe.write_bytes(b"x")
        db.add_to_library(555, str(ghost_exe), "ghost.exe", "ghost.exe", [])
        db.set_process_running(555, os.getpid())

        api = DiscordAPIClient(db, tmpdir / "cache")
        dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
        process_mgr = ProcessManager(db, dummy_gen)
        mgr = GameManager(db, api, dummy_gen, process_mgr)

        summary = mgr.repair_library()

        assert summary["dangling_removed"] == 0
        assert summary["warnings"] >= 1
        assert db.is_in_library(555)
        assert ghost_exe.exists()
        assert db.get_running_processes() == {555: os.getpid()}

    print("  PASSED")


def test_verify_game_process_matches_path_segments():
    print("Testing process verification...")

    from unittest.mock import MagicMock, patch

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        fake = MagicMock()
        fake.exe.return_value = str(Path(tmpdir) / "games" / "222" / "game.exe")
        with patch("launcher.process_manager.psutil.Process", return_value=fake):
            assert mgr.process_mgr._verify_game_process(222, 1234) is True
            assert mgr.process_mgr._verify_game_process(22, 1234) is False
            assert mgr.process_mgr._verify_game_process(2, 1234) is False

    print("  PASSED")


def test_process_manager_requires_injected_generator():
    print("Testing generator ownership...")

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))

        assert mgr.process_mgr.dummy_gen is mgr.dummy_gen

        try:
            ProcessManager(mgr.db)
        except TypeError:
            pass
        else:
            raise AssertionError("ProcessManager must require dummy_generator")

    print("  PASSED")

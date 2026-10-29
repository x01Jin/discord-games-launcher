
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.api import DiscordAPIClient
from launcher.bridge import Bridge
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager

SNOWFLAKE = 1093489941847717184
assert SNOWFLAKE > 2**53 - 1
assert int(float(SNOWFLAKE)) != SNOWFLAKE


def _make_bridge(tmpdir: Path) -> Bridge:
    template = tmpdir / "DummyGame.exe"
    template.write_bytes(b"fake-exe")
    db = Database(tmpdir / "test.db")
    api = DiscordAPIClient(db, tmpdir / "cache")
    dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
    process_mgr = ProcessManager(db, dummy_gen)
    game_mgr = GameManager(db, api, dummy_gen, process_mgr)
    db.save_games(
        [
            {
                "id": SNOWFLAKE,
                "name": "Snowflake Game",
                "aliases": [],
                "executables": [{"os": "win32", "name": "snow.exe"}],
                "icon_hash": None,
                "themes": [],
                "isPublished": True,
            }
        ]
    )
    return Bridge(game_mgr)


def test_list_and_search_emit_string_ids():
    print("Testing catalogue ID serialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))

        listed = bridge.list_games(200, 0)["games"][0]
        found = bridge.search_games("snow", 50)["games"][0]
        for game in (listed, found):
            assert isinstance(game["id"], str), f"id wire type: {type(game['id'])}"
            assert game["id"] == str(SNOWFLAKE)
            assert int(game["id"]) == SNOWFLAKE

        payload = json.dumps({"games": [listed]})
        assert str(SNOWFLAKE) in payload

    print("  PASSED")


def test_library_mutations_round_trip_string_ids():
    print("Testing library ID round-trip...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))
        sid = str(SNOWFLAKE)

        added = bridge.add_to_library(sid)
        assert added["ok"], added

        library = bridge.get_library()["games"]
        assert len(library) == 1
        assert isinstance(library[0]["game_id"], str)
        assert library[0]["game_id"] == sid

        bridge.game_manager.db.set_process_running(SNOWFLAKE, os.getpid())
        bridge = _make_bridge(Path(tmpdir))
        running = bridge.get_running()["running"]
        assert running == [sid]
        assert all(isinstance(r, str) for r in running)

        bridge.game_manager.process_mgr.reset_runtime_state()

        removed = bridge.remove_from_library(sid)
        assert removed["ok"], removed
        assert bridge.get_library()["games"] == []

    print("  PASSED")


def test_remove_many_removes_selected_and_counts_failures():
    print("Testing batch library removal...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))
        sid = str(SNOWFLAKE)
        assert bridge.add_to_library(sid)["ok"]

        result = bridge.remove_many([sid, "nope", sid])
        assert result["removed"] == 1, result
        assert result["failed"] == 2, result
        assert result["message"] == "Removed 1 game(s), 2 failed"
        assert bridge.get_library()["games"] == []

        empty = bridge.remove_many([])
        assert empty == {"removed": 0, "failed": 0, "message": "Removed 0 game(s)"}

        absent = bridge.remove_many([sid])
        assert absent["removed"] == 0
        assert absent["failed"] == 1

    print("  PASSED")


def test_strict_id_parsing_rejects_coercible_junk():
    print("Testing strict ID parsing...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))

        for bad in ("abc", "1.9", "  ", "", True, False, 1.9, 0, -5, 2**63):
            assert bridge.add_to_library(bad)["ok"] is False
            assert bridge.start_game(bad)["ok"] is False
            assert bridge.stop_game(bad)["ok"] is False
            assert bridge.remove_from_library(bad)["ok"] is False

        missing = bridge.add_to_library("007")
        assert missing == {"ok": False, "message": "Game not found in cache"}

        mixed = bridge.add_many([str(SNOWFLAKE), "nope", 1.5])
        assert mixed["added"] == 1
        assert mixed["failed"] == 2

    print("  PASSED")


def test_start_returns_manager_result_directly():
    print("Testing direct bridge start...")

    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))
        sid = str(SNOWFLAKE)

        with patch.object(
            bridge.game_manager, "start_game", return_value=(True, "Snow started")
        ) as mock_start:
            started = bridge.start_game(sid)

        assert started == {"ok": True, "message": "Snow started"}
        mock_start.assert_called_once_with(SNOWFLAKE)

        with patch.object(
            bridge.game_manager,
            "start_game",
            return_value=(False, "Game is not in library"),
        ):
            stopped = bridge.start_game(sid)
        assert stopped == {"ok": False, "message": "Game is not in library"}

    print("  PASSED")


def test_backend_errors_return_dicts_never_raise():
    print("Testing bridge error wrapping...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))
        sid = str(SNOWFLAKE)
        assert bridge.add_to_library(sid)["ok"]

        with patch.object(
            bridge.game_manager.db, "get_game", side_effect=sqlite3.Error("boom")
        ):
            started = bridge.start_game(sid)
            assert started["ok"] is False
            assert "boom" in started["message"]

    print("  PASSED")

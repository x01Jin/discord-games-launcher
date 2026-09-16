"""Regression tests for snowflake-scale game IDs crossing the JS bridge.

Discord IDs are ~18-digit snowflakes. Emitted as JSON numbers they lose
precision in the webview (IEEE-754 doubles), so the bridge must serialize
every outbound ID as a string. Uses a real snowflake magnitude fixture.

Usage:
    pytest tests/test_bridge_ids.py -v
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.api import DiscordAPIClient
from launcher.bridge import Bridge
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager

# Real snowflake magnitude: beyond JS MAX_SAFE_INTEGER (2**53 - 1).
SNOWFLAKE = 1093489941847717184
assert SNOWFLAKE > 2**53 - 1
# Sanity: the old numeric wire format would have corrupted this ID.
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
    """Catalogue payloads carry exact string IDs, surviving a JS round-trip."""
    print("Testing catalogue ID serialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))

        listed = bridge.list_games(200, 0)["games"][0]
        found = bridge.search_games("snow", 50)["games"][0]
        for game in (listed, found):
            assert isinstance(game["id"], str), f"id wire type: {type(game['id'])}"
            assert game["id"] == str(SNOWFLAKE)
            assert int(game["id"]) == SNOWFLAKE

        # Emulate the webview: JSON numbers would round, strings do not.
        payload = json.dumps({"games": [listed]})
        assert str(SNOWFLAKE) in payload

    print("  PASSED")


def test_library_mutations_round_trip_string_ids():
    """Add/start/remove/get flows work with frontend-shaped string IDs."""
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

        # Seed the row before (re)building so the PID cache picks it up;
        # use a live PID or the stale-record cleanup drops it by design.
        bridge.game_manager.db.set_process_running(SNOWFLAKE, os.getpid())
        bridge = _make_bridge(Path(tmpdir))
        running = bridge.get_running()["running"]
        assert running == [sid]
        assert all(isinstance(r, str) for r in running)

        # Drop the row first: remove() stops live processes, and this PID
        # is the test runner itself.
        bridge.game_manager.process_mgr.reset_runtime_state()

        removed = bridge.remove_from_library(sid)
        assert removed["ok"], removed
        assert bridge.get_library()["games"] == []

    print("  PASSED")


def test_strict_id_parsing_rejects_coercible_junk():
    """Bools, floats, and non-numeric strings fail closed, never truncate."""
    print("Testing strict ID parsing...")

    with tempfile.TemporaryDirectory() as tmpdir:
        bridge = _make_bridge(Path(tmpdir))

        for bad in ("abc", "1.9", "  ", "", True, False, 1.9, 0, -5, 2**63):
            assert bridge.add_to_library(bad)["ok"] is False  # type: ignore[arg-type]
            assert bridge.start_game(bad)["ok"] is False  # type: ignore[arg-type]
            assert bridge.stop_game(bad)["ok"] is False  # type: ignore[arg-type]
            assert bridge.remove_from_library(bad)["ok"] is False  # type: ignore[arg-type]

        # Deterministic digit strings still work ("007" is game 7: absent).
        missing = bridge.add_to_library("007")
        assert missing == {"ok": False, "message": "Game not found in cache"}

        mixed = bridge.add_many([str(SNOWFLAKE), "nope", 1.5])  # type: ignore[list-item]
        assert mixed["added"] == 1
        assert mixed["failed"] == 2

    print("  PASSED")


def test_start_returns_manager_result_directly():
    """Start returns at once with the manager result (no detection step)."""
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
    """DB failures surface as error payloads, not rejected promises."""
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

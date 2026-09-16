"""Tests for Discord API version cascade, payload sanitizing, and sync reporting.

Covers: latest-first version fallback, malformed-record skip counting,
schema-drift warnings, fallback transition notices, and the extended
sync result shapes (synced, count, skipped).

Usage:
    pytest tests/test_api_versions.py -v
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx

from launcher.api import (
    API_VERSION_CANDIDATES,
    STABLE_API_VERSION,
    DiscordAPIClient,
    DiscordAPIError,
    detectable_url,
)
from launcher.bridge import Bridge
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.process_manager import ProcessManager


def _make_client(tmpdir: Path, logger=None) -> tuple[Database, DiscordAPIClient]:
    db = Database(tmpdir / "test.db")
    api = DiscordAPIClient(db, tmpdir / "cache", logger=logger)
    return db, api


def _mock_http(payload=None, fail_urls=()) -> MagicMock:
    """Build a mock httpx.Client class; URLs in fail_urls raise ConnectError."""
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    def _get(url, *args, **kwargs):
        if any(fail in str(url) for fail in fail_urls):
            raise httpx.ConnectError("connection failed")
        return mock_response

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)
    mock_client.get.side_effect = _get
    mock_class = MagicMock()
    mock_class.return_value = mock_client
    return mock_class


def _good_game(game_id=12345, **overrides):
    game = {
        "id": game_id,
        "name": f"Game {game_id}",
        "aliases": [],
        "executables": [{"os": "win32", "name": "game.exe"}],
        "icon_hash": None,
        "themes": [],
        "isPublished": True,
    }
    game.update(overrides)
    return game


def test_version_policy_defaults():
    """Stable default is v10 and candidates are latest-first."""
    print("Testing version policy defaults...")
    assert STABLE_API_VERSION == "v10"
    assert API_VERSION_CANDIDATES[0] == STABLE_API_VERSION
    assert detectable_url("v10").endswith("/v10/applications/detectable")
    print("  PASSED")


def test_sanitize_valid_payload():
    """Well-formed records pass through with normalized types."""
    print("Testing sanitize valid payload...")
    payload = [
        _good_game(1, id="777", extra_unknown_field="ignored"),
        _good_game(2, executables="not-a-list", aliases=None, themes="x"),
    ]
    clean, skipped, _missing = DiscordAPIClient.sanitize_games(payload)
    assert skipped == 0, f"Expected 0 skipped, got {skipped}"
    assert len(clean) == 2
    assert clean[0]["id"] == 777
    assert "extra_unknown_field" not in clean[0]
    assert clean[1]["executables"] == []
    assert clean[1]["aliases"] == []
    assert clean[1]["themes"] == []
    print("  PASSED")


def test_sanitize_skips_malformed():
    """Non-dict records and bad ids are skipped, never fatal."""
    print("Testing sanitize skips malformed...")
    payload = [
        _good_game(1),
        "not-a-dict",
        42,
        None,
        _good_game(2, id=True),  # bool id rejected
        _good_game(3, id="abc"),  # non-numeric id
        _good_game(4, id=0),  # non-positive id
        {"name": "missing id"},
    ]
    clean, skipped, missing = DiscordAPIClient.sanitize_games(payload)
    assert len(clean) == 1, f"Expected 1 clean, got {len(clean)}"
    assert skipped == 7, f"Expected 7 skipped, got {skipped}"
    assert missing["id"] >= 3
    print("  PASSED")


def test_sanitize_rejects_non_list_payload():
    """A non-list top-level payload raises instead of silently caching nothing."""
    print("Testing sanitize rejects non-list...")
    try:
        DiscordAPIClient.sanitize_games({"id": 1})
        assert False, "Should have raised DiscordAPIError"
    except DiscordAPIError:
        print("  Correctly raised for dict payload")
    print("  PASSED")


def test_cascade_falls_back_to_stable():
    """Latest-first cascade falls back when the newest version fails."""
    print("Testing version cascade fallback...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db, api = _make_client(tmpdir)
        payload = [_good_game(1)]
        with (
            patch("launcher.api.API_VERSION_CANDIDATES", ("v99", "v10")),
            patch(
                "launcher.api.httpx.Client",
                _mock_http(payload, fail_urls=("v99",)),
            ),
        ):
            games, skipped = api._fetch_all_games_cascade()
            assert len(games) == 1
            assert skipped == 0
            assert api.last_fetch_version == "v10"
            assert db.get_metadata_value("last_working_api_version") == "v10"
            print("  Fell back v99 -> v10 and persisted it")
    print("  PASSED")


def test_cascade_prefers_last_working():
    """Stored last-working version is tried first (fast path)."""
    print("Testing cascade prefers last working...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db, api = _make_client(tmpdir)
        db.set_metadata_value("last_working_api_version", "v10")
        seen: list[str] = []
        mock_response = MagicMock()
        mock_response.json.return_value = [_good_game(1)]
        mock_response.raise_for_status.return_value = None

        def _recording_get(url, *args, **kwargs):
            seen.append(str(url))
            return mock_response

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get.side_effect = _recording_get
        mock_class = MagicMock()
        mock_class.return_value = mock_client
        with (
            patch("launcher.api.API_VERSION_CANDIDATES", ("v99", "v10")),
            patch("launcher.api.httpx.Client", mock_class),
        ):
            api._fetch_all_games_cascade()
            assert "/v10/" in seen[0], f"Expected v10 first, got {seen}"
            print(f"  First attempt: {seen[0]}")
    print("  PASSED")


def test_cascade_all_fail():
    """Every candidate failing raises a single aggregated error."""
    print("Testing cascade total failure...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        _db, api = _make_client(tmpdir)
        with (
            patch("launcher.api.API_VERSION_CANDIDATES", ("v99", "v98")),
            patch("launcher.api.httpx.Client", _mock_http([], fail_urls=("v",))),
        ):
            try:
                api._fetch_all_games_cascade()
                assert False, "Should have raised DiscordAPIError"
            except DiscordAPIError as e:
                assert "v99" in str(e) and "v98" in str(e)
                print(f"  Aggregated error: {e}")
    print("  PASSED")


def test_sync_counts_skipped_end_to_end():
    """sync_cache saves clean records and reports skipped ones."""
    print("Testing sync skip counting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db, api = _make_client(tmpdir)
        payload = [_good_game(1), "garbage", _good_game(2, id="bad")]
        with patch("launcher.api.httpx.Client", _mock_http(payload)):
            was_synced, count, skipped = api.sync_cache(force=True)
            assert was_synced is True
            assert count == 1, f"Expected 1 saved, got {count}"
            assert skipped == 2, f"Expected 2 skipped, got {skipped}"
            assert len(db.get_all_games()) == 1
            print(f"  Saved {count}, skipped {skipped}")
    print("  PASSED")


def test_drift_warning_on_alien_payload():
    """Majority-missing executables triggers a drift warning."""
    print("Testing drift warning...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        logger = MagicMock()
        _db, api = _make_client(tmpdir, logger=logger)
        payload = [_good_game(1, executables="gone"), _good_game(2, executables=42)]
        with patch("launcher.api.httpx.Client", _mock_http(payload)):
            api.sync_cache(force=True)
            warnings = [str(c) for c in logger.warning.call_args_list]
            assert any("schema may have changed" in w for w in warnings), warnings
            print("  Drift warning logged")
    print("  PASSED")


def test_save_games_never_aborts():
    """Database layer skips garbage and reports the count."""
    print("Testing save_games guard...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        skipped = db.save_games([_good_game(1), None, "x", {"no": "id"}])  # type: ignore[list-item] - deliberately malformed input
        assert skipped == 3, f"Expected 3 skipped, got {skipped}"
        assert len(db.get_all_games()) == 1
    print("  PASSED")


def _make_manager(tmpdir: Path, logger=None) -> GameManager:
    template = tmpdir / "DummyGame.exe"
    template.write_bytes(b"fake-exe")
    db = Database(tmpdir / "test.db")
    api = DiscordAPIClient(db, tmpdir / "cache", logger=logger)
    dummy_gen = DummyGenerator(tmpdir / "games", template_exe_path=template)
    process_mgr = ProcessManager(db, dummy_gen)
    return GameManager(db, api, dummy_gen, process_mgr, logger=logger)


def test_note_api_version_transitions():
    """Fallback notices fire once per transition, never per sync."""
    print("Testing version notice transitions...")
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir), logger=MagicMock())
        # First run on newest: silent.
        assert mgr.note_api_version("v10") == ""
        # Steady state: silent.
        assert mgr.note_api_version("v10") == ""
        # Transition into fallback: notice.
        notice = mgr.note_api_version("v9")
        assert "fallback" in notice and "v9" in notice, notice
        # Steady fallback: silent.
        assert mgr.note_api_version("v9") == ""
        # Transition back: notice.
        notice = mgr.note_api_version("v10")
        assert "latest" in notice, notice
        print("  Transitions behave")
    print("  PASSED")


def test_bridge_sync_message_reports_skipped_and_fallback():
    """sync_catalogue message carries skipped counts and fallback notices."""
    print("Testing bridge sync message...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = _make_manager(tmpdir)
        bridge = Bridge(mgr)
        payload = [_good_game(1), "garbage"]
        with (
            patch("launcher.api.API_VERSION_CANDIDATES", ("v99", "v10")),
            patch(
                "launcher.api.httpx.Client",
                _mock_http(payload, fail_urls=("v99",)),
            ),
        ):
            result = bridge.sync_catalogue()
            assert result["synced"] is True
            assert result["count"] == 1
            assert result["skipped"] == 1
            assert "skipped" in result["message"], result["message"]
            assert "fallback API (v10)" in result["message"], result["message"]
            print(f"  Message: {result['message']}")
            # Second sync: steady state stays silent about fallback.
            result2 = bridge.sync_catalogue()
            assert "fallback" not in result2["message"], result2["message"]
            print("  Second sync silent")
    print("  PASSED")


def test_bridge_sync_error_shape():
    """Sync failure includes the skipped field for frontend safety."""
    print("Testing bridge sync error shape...")
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = _make_manager(Path(tmpdir))
        bridge = Bridge(mgr)
        with patch("launcher.api.httpx.Client", _mock_http([], fail_urls=("v",))):
            result = bridge.sync_catalogue()
            assert result["synced"] is False
            assert result["count"] == 0
            assert result["skipped"] == 0
            assert "Sync failed" in result["message"]
    print("  PASSED")


def run_all_tests():
    """Run all API version tests."""
    print("\n" + "=" * 50)
    print("API VERSION MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_version_policy_defaults,
        test_sanitize_valid_payload,
        test_sanitize_skips_malformed,
        test_sanitize_rejects_non_list_payload,
        test_cascade_falls_back_to_stable,
        test_cascade_prefers_last_working,
        test_cascade_all_fail,
        test_sync_counts_skipped_end_to_end,
        test_drift_warning_on_alien_payload,
        test_save_games_never_aborts,
        test_note_api_version_transitions,
        test_bridge_sync_message_reports_skipped_and_fallback,
        test_bridge_sync_error_shape,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:  # noqa: BLE001 - runner must continue past failures
            print(f"  FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed.append((test.__name__, e))
        print()

    print("=" * 50)
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name, error in failed:
            print(f"  - {name}: {error}")
    else:
        print(f"ALL TESTS PASSED: {len(tests)}/{len(tests)}")
    print("=" * 50 + "\n")

    return len(failed) == 0


if __name__ == "__main__":
    raise SystemExit(0 if run_all_tests() else 1)

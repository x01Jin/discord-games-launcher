"""Quest option storage: a small JSON file, not the SQLite database."""

import json

from launcher import prefs


def test_defaults_when_no_file(tmp_path):
    assert prefs.load(tmp_path / "missing.json") == {
        "play_session_tail_min": 2,
        "run_mode": "activity",
    }


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    prefs.save({"play_session_tail_min": 7}, path)
    assert prefs.load(path) == {"play_session_tail_min": 7, "run_mode": "activity"}
    assert json.loads(path.read_text(encoding="utf-8"))["play_session_tail_min"] == 7


def test_save_merges_into_existing_values(tmp_path):
    path = tmp_path / "settings.json"
    prefs.save({"play_session_tail_min": 7}, path)
    saved = prefs.save({"play_session_tail_min": 5}, path)
    assert saved == {"play_session_tail_min": 5, "run_mode": "activity"}


def test_unknown_keys_are_dropped(tmp_path):
    # A stale key from an older version is dropped, not carried in memory.
    assert prefs.save({"nonsense": 1, "hide_activity": True}, tmp_path / "s.json") == {
        "play_session_tail_min": 2,
        "run_mode": "activity",
    }


def test_tail_is_clamped_and_coerced(tmp_path):
    assert prefs.save({"play_session_tail_min": 500}, tmp_path / "s.json")[
        "play_session_tail_min"
    ] == prefs.MAX_TAIL_MINUTES
    assert prefs.save({"play_session_tail_min": -4}, tmp_path / "s2.json")[
        "play_session_tail_min"
    ] == 0
    assert prefs.save({"play_session_tail_min": "6"}, tmp_path / "s3.json")[
        "play_session_tail_min"
    ] == 6


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert prefs.load(path)["play_session_tail_min"] == 2


def test_update_only_touches_named_values(tmp_path):
    path = tmp_path / "settings.json"
    prefs.update(path, play_session_tail_min=9)
    assert prefs.update(path, play_session_tail_min=3) == {
        "play_session_tail_min": 3,
        "run_mode": "activity",
    }


def test_run_mode_keeps_known_values_and_drops_others(tmp_path):
    assert prefs.save({"run_mode": "silent"}, tmp_path / "a.json")["run_mode"] == "silent"
    assert prefs.save({"run_mode": "loud"}, tmp_path / "b.json")["run_mode"] == "activity"
    assert prefs.save({"run_mode": None}, tmp_path / "c.json")["run_mode"] == "activity"


def test_default_path_honours_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DCGL_DATA_DIR", str(tmp_path))
    assert prefs.default_path() == tmp_path / "settings.json"

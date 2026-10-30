import pytest

from launcher import discord_setup
from launcher.bridge import Bridge
from launcher.discord_native import DiscordNativeError
from launcher.quests import QuestService
from tests.test_quests import FakeNative, payload, quest


@pytest.fixture
def quest_payload():
    return payload(quest(app_id="100", name="Play Me"))


def make_bridge(game_manager, payload_data, prefs_path=None, **native_kwargs):
    native = FakeNative(payload=payload_data, **native_kwargs)
    service = QuestService(
        game_manager,
        native=native,
        ttl=60.0,
        prefs_path=prefs_path,
        monitor=False,
    )
    return Bridge(game_manager, quest_service=service), native


def test_discord_status_without_service(game_manager):
    bridge = Bridge(game_manager)
    state = bridge.discord_status()
    assert state["installed"] is False
    assert "unavailable" in state["hint"]


def test_get_quests_without_service(game_manager):
    result = Bridge(game_manager).get_quests()
    assert result["connected"] is False
    assert "unavailable" in result["error"]


def test_get_quests_decorates(game_manager, quest_payload):
    bridge, _native = make_bridge(game_manager, quest_payload)
    result = bridge.get_quests()
    assert result["connected"] is True
    assert result["quests"][0]["name"] == "Play Me"


def test_get_quests_surfaces_backend_errors(game_manager):
    bridge, native = make_bridge(game_manager, None)
    native.error = DiscordNativeError("QuestStore was not found")
    result = bridge.get_quests()
    assert result["connected"] is False
    assert "QuestStore" in result["error"]


def test_get_quests_force_flag_reaches_the_client(game_manager, quest_payload):
    bridge, native = make_bridge(game_manager, quest_payload)
    bridge.get_quests()
    bridge.get_quests()
    assert native.reads == 1
    bridge.get_quests(force=True)
    assert native.reads == 2


def test_start_quest_rejects_empty_id(game_manager):
    bridge, _native = make_bridge(game_manager, payload(quest()))
    assert bridge.start_quest("")["ok"] is False
    assert bridge.start_quest(None)["ok"] is False


def test_stop_quest_rejects_empty_id(game_manager):
    bridge, _native = make_bridge(game_manager, payload(quest()))
    assert bridge.stop_quest("   ")["ok"] is False


def test_start_quest_pushes_library_changed(game_manager, monkeypatch):
    events = []
    bridge, _native = make_bridge(game_manager, payload(quest(app_id="100")))
    bridge.push = events.append
    monkeypatch.setattr(
        bridge.quest_service, "start_quest", lambda quest_id: (True, "started")
    )

    result = bridge.start_quest("1")

    assert result == {"ok": True, "message": "started"}
    assert {"type": "library_changed"} in events


def test_stop_quest_wraps_failures(game_manager):
    bridge, _native = make_bridge(game_manager, payload(quest()))
    bridge.quest_service.stop_quest = lambda quest_id: (_ for _ in ()).throw(OSError("nope"))
    result = bridge.stop_quest("1")
    assert result["ok"] is False
    assert "nope" in result["message"]


def test_connect_discord_patches_then_restarts(game_manager, quest_payload, monkeypatch):
    patched = []
    monkeypatch.setattr(
        discord_setup,
        "enable",
        lambda port=None: patched.append(port) or {"ok": True, "updated": [], "failed": []},
    )
    bridge, native = make_bridge(game_manager, quest_payload)
    result = bridge.connect_discord()
    assert result["ok"] is True
    assert native.restarts == 1
    assert patched == [9222]


def test_start_discord_patches_then_starts(game_manager, quest_payload, monkeypatch):
    patched = []
    monkeypatch.setattr(
        discord_setup,
        "enable",
        lambda port=None: patched.append(port) or {"ok": True, "updated": [], "failed": []},
    )
    bridge, native = make_bridge(game_manager, quest_payload)
    result = bridge.start_discord()
    assert result["ok"] is True
    assert native.starts == 1
    assert patched == [9222]


def test_removing_the_patch_restarts_a_running_discord(
    game_manager, quest_payload, monkeypatch
):
    monkeypatch.setattr(discord_setup, "disable", lambda: {"ok": True, "restored": [], "failed": []})
    monkeypatch.setattr("launcher.bridge.is_running", lambda: True)
    bridge, native = make_bridge(game_manager, quest_payload)
    result = bridge.disable_silent_mode()
    assert result["ok"] is True
    assert result["restarted"] is True
    assert native.plain_restarts == 1


def test_removing_the_patch_leaves_a_closed_discord_alone(
    game_manager, quest_payload, monkeypatch
):
    monkeypatch.setattr(discord_setup, "disable", lambda: {"ok": True, "restored": [], "failed": []})
    monkeypatch.setattr("launcher.bridge.is_running", lambda: False)
    bridge, native = make_bridge(game_manager, quest_payload)
    result = bridge.disable_silent_mode()
    assert result["ok"] is True
    assert result["restarted"] is False
    assert native.plain_restarts == 0


def test_quest_prefs_default_and_save(game_manager, quest_payload, tmp_path):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    assert bridge.get_quest_prefs()["prefs"] == {
        "play_session_tail_min": 2,
        "run_mode": "activity",
        "test_mode": False,
    }

    saved = bridge.set_quest_prefs({"play_session_tail_min": 4})
    assert saved["ok"] is True
    assert saved["prefs"]["play_session_tail_min"] == 4
    assert bridge.get_quests()["prefs"]["play_session_tail_min"] == 4


def test_set_quest_prefs_rejects_non_dict(game_manager, quest_payload, tmp_path):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    result = bridge.set_quest_prefs(["nope"])
    assert result["ok"] is False


def test_quest_prefs_without_service(game_manager):
    bridge = Bridge(game_manager)
    assert bridge.get_quest_prefs()["prefs"]["play_session_tail_min"] == 2
    assert bridge.set_quest_prefs({"play_session_tail_min": 5})["ok"] is False


def test_start_quest_queue_delegates(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    calls = []
    monkeypatch.setattr(
        bridge.quest_service, "start_queue", lambda ids: (calls.append(ids), (True, "Queued 1"))[1]
    )
    result = bridge.start_quest_queue(["quest-1"])
    assert result["ok"] is True
    assert calls == [["quest-1"]]


def test_clear_quest_queue_reports_count(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    monkeypatch.setattr(bridge.quest_service, "clear_queue", lambda: 3)
    result = bridge.clear_quest_queue()
    assert result["ok"] is True
    assert result["cleared"] == 3


def test_skip_quest_watch_delegates(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    monkeypatch.setattr(
        bridge.quest_service, "skip_watch", lambda: (True, "Skipped the video")
    )
    result = bridge.skip_quest_watch()
    assert result["ok"] is True
    assert result["message"] == "Skipped the video"


def test_reorder_quest_queue_delegates(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    calls = []
    monkeypatch.setattr(
        bridge.quest_service,
        "reorder_queue",
        lambda ids: (calls.append(ids), (True, "Queue reordered"))[1],
    )
    result = bridge.reorder_quest_queue(["b", "a"])
    assert result["ok"] is True
    assert calls == [["b", "a"]]


def test_reorder_quest_queue_rejects_bad_input(game_manager, quest_payload):
    bridge, _native = make_bridge(game_manager, quest_payload)
    assert bridge.reorder_quest_queue("a")["ok"] is False


def test_remove_from_quest_queue_delegates(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    calls = []
    monkeypatch.setattr(
        bridge.quest_service,
        "drop_queue_item",
        lambda qid: (calls.append(qid), (True, "Removed"))[1],
    )
    result = bridge.remove_from_quest_queue("quest-1")
    assert result["ok"] is True
    assert calls == ["quest-1"]
    assert bridge.remove_from_quest_queue("")["ok"] is False


def test_accept_quest_delegates(game_manager, quest_payload, tmp_path, monkeypatch):
    bridge, _native = make_bridge(game_manager, quest_payload, prefs_path=tmp_path / "s.json")
    calls = []
    monkeypatch.setattr(
        bridge.quest_service, "accept_quest", lambda qid: (calls.append(qid), (True, "Quest accepted"))[1]
    )
    result = bridge.accept_quest("quest-1")
    assert result == {"ok": True, "message": "Quest accepted"}
    assert calls == ["quest-1"]


def test_accept_quest_rejects_bad_input(game_manager, quest_payload):
    bridge, _native = make_bridge(game_manager, quest_payload)
    assert bridge.accept_quest("")["ok"] is False


def test_start_quest_queue_rejects_bad_input(game_manager, quest_payload):
    bridge, _native = make_bridge(game_manager, quest_payload)
    result = bridge.start_quest_queue("quest-1")
    assert result["ok"] is False

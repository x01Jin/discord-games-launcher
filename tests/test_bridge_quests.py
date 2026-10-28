"""Bridge surface for the quest list."""

import pytest

from launcher.bridge import Bridge
from launcher.discord_native import DiscordNativeError
from launcher.quests import QuestService
from tests.test_quests import FakeNative, payload, quest


@pytest.fixture
def quest_payload():
    return payload(quest(app_id="100", name="Play Me"))


def make_bridge(game_manager, payload_data, **native_kwargs):
    native = FakeNative(payload=payload_data, **native_kwargs)
    service = QuestService(game_manager, native=native, ttl=60.0)
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


def test_connect_discord_reports_result(game_manager, quest_payload):
    bridge, native = make_bridge(game_manager, quest_payload)
    result = bridge.connect_discord()
    assert result["ok"] is True
    assert native.connects == 1

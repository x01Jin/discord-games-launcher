"""Tests for the quest list built from the running Discord client."""


import pytest

from launcher.discord_native import DiscordNativeError
from launcher.quests import QuestService, derive_executable_name


class FakeNative:
    """Stands in for DiscordNative: configurable status and payload."""

    def __init__(self, payload=None, state=None, error=None):
        self.payload = payload
        self.state = state or {
            "installed": True,
            "running": True,
            "connected": True,
            "debug_port": 9222,
            "hint": "Connected",
        }
        self.error = error
        self.reads = 0
        self.connects = 0

    def status(self):
        return dict(self.state)

    def read_quests(self):
        self.reads += 1
        if self.error:
            raise self.error
        return self.payload

    def connect(self):
        self.connects += 1
        return True, "Reconnected"


def quest(
    quest_id="1",
    app_id="100",
    name="Test Quest",
    game="Test Game",
    target=900,
    progress=0,
    completed=False,
    expires="2999-01-01T00:00:00+00:00",
    orbs=700,
    kind="play",
    enrolled=True,
    video=None,
):
    return {
        "id": quest_id,
        "kind": kind,
        "taskKey": "PLAY_ON_DESKTOP" if kind == "play" else kind.upper(),
        "name": name,
        "gameName": game,
        "publisher": "Pub",
        "applicationId": app_id,
        "taskKeys": ["PLAY_ON_DESKTOP", "PLAY_ON_XBOX"],
        "target": target,
        "progress": progress,
        "enrolledAt": "2026-01-01T00:00:00+00:00" if enrolled else None,
        "completedAt": "2026-01-01T00:00:00+00:00" if completed else None,
        "expiresAt": expires,
        "tile": "quests/1/tile.png",
        "hero": "PLACEHOLDER",
        "logotype": None,
        "video": video,
        "accent": "#5865F2",
        "rewardName": f"{orbs} Orbs",
        "rewardOrbs": orbs,
    }


def payload(*quests, total=None):
    return {
        "ok": True,
        "quests": list(quests),
        "questCount": total if total is not None else len(quests),
        "account": {"id": "42", "username": "tester"},
        "suspendedUntil": None,
        "enrollmentBlockedUntil": None,
    }


@pytest.fixture
def cached_game(database):
    database.save_games(
        [
            {
                "id": 100,
                "name": "Test Game",
                "aliases": [],
                "executables": [
                    {"name": "testgame.exe", "os": "win32", "is_launcher": False},
                    {"name": "testgame_launcher.exe", "os": "win32", "is_launcher": True},
                    {"name": "testgame", "os": "darwin", "is_launcher": False},
                ],
                "icon_hash": "abc123",
                "themes": [],
                "isPublished": True,
            }
        ]
    )
    return database


def make_service(game_manager, native, ttl=20.0):
    return QuestService(game_manager, native=native, ttl=ttl)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Risk of Rain 2", "RiskofRain2.exe"),
        ("War Thunder", "WarThunder.exe"),
        ("", "game.exe"),
        ("!!!", "game.exe"),
    ],
)
def test_derive_executable_name(name, expected):
    assert derive_executable_name(name) == expected


# ---------------------------------------------------------------------------
# listing
# ---------------------------------------------------------------------------


def test_list_quests_when_discord_is_not_running(game_manager):
    native = FakeNative(
        state={"installed": True, "running": False, "connected": False, "hint": "Open Discord"}
    )
    listing = make_service(game_manager, native).list_quests()
    assert listing["connected"] is False
    assert listing["quests"] == []
    assert listing["error"] is None
    assert native.reads == 0


def test_list_quests_when_read_fails(game_manager):
    native = FakeNative(error=DiscordNativeError("QuestStore was not found"))
    listing = make_service(game_manager, native).list_quests()
    assert listing["connected"] is False
    assert listing["quests"] == []
    assert "QuestStore" in listing["error"]


def test_list_quests_decorates_cached_game(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    listing = make_service(game_manager, native).list_quests()

    assert listing["connected"] is True
    assert listing["account"] == {"id": "42", "username": "tester"}
    entry = listing["quests"][0]
    assert entry["application_id"] == "100"
    assert entry["icon_hash"] == "abc123"
    assert entry["executables"][0] == "testgame.exe"
    assert entry["process_name"] == "testgame.exe"
    assert entry["state"] == "ready"
    assert entry["in_library"] is False
    assert entry["tile_url"] == "https://cdn.discordapp.com/quests/1/tile.png"
    assert entry["hero_url"] is None  # PLACEHOLDER is not an asset
    assert entry["reward"] == {"label": "700 Orbs", "orbs": 700, "premium_orbs": None}
    assert entry["target_seconds"] == 900
    assert 0.0 <= entry["progress"] <= 1.0


def test_list_quests_falls_back_when_game_is_not_cached(game_manager):
    native = FakeNative(payload=payload(quest(app_id="999", game="Unseen Game")))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["executables"] == ["UnseenGame.exe"]
    assert entry["icon_hash"] is None


def test_states_completed_expired_ready_and_order(game_manager, cached_game):
    native = FakeNative(
        payload=payload(
            quest("1", name="Done", completed=True),
            quest("2", name="Gone", expires="2000-01-01T00:00:00+00:00"),
            quest("3", name="Live"),
        )
    )
    listing = make_service(game_manager, native).list_quests()
    by_name = {q["name"]: q for q in listing["quests"]}
    assert by_name["Done"]["state"] == "completed"
    assert by_name["Gone"]["state"] == "expired"
    assert by_name["Live"]["state"] == "ready"
    # ready first, then expired, then completed
    assert [q["name"] for q in listing["quests"]] == ["Live", "Gone", "Done"]


def test_progress_counts_as_completed(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(progress=900, target=900)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["state"] == "completed"
    assert entry["progress"] == 1.0


def test_missing_application_id_is_unresolved(game_manager):
    native = FakeNative(payload=payload(quest(app_id=None)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["application_id"] is None
    assert entry["state"] == "unresolved"


def test_shared_game_count(game_manager, cached_game):
    native = FakeNative(
        payload=payload(
            quest("1", name="A"),
            quest("2", name="B"),
            quest("3", name="C", app_id="999"),
        )
    )
    listing = make_service(game_manager, native).list_quests()
    counts = {q["name"]: q["shares_game_with"] for q in listing["quests"]}
    assert counts == {"A": 1, "B": 1, "C": 0}


def test_list_quests_is_cached_and_invalidated(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, ttl=60.0)
    service.list_quests()
    service.list_quests()
    assert native.reads == 1

    service.invalidate()
    service.list_quests()
    assert native.reads == 2


def test_force_refresh_bypasses_cache(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, ttl=60.0)
    service.list_quests()
    service.list_quests(force=True)
    assert native.reads == 2


def test_library_membership_is_reported(game_manager, cached_game):
    game_manager.add_to_library(100)
    native = FakeNative(payload=payload(quest()))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["in_library"] is True


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


def test_start_quest_rejects_completed(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True)))
    ok, message = make_service(game_manager, native).start_quest("1")
    assert ok is False
    assert "already complete" in message


def test_start_quest_rejects_unknown_id(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    ok, message = make_service(game_manager, native).start_quest("does-not-exist")
    assert ok is False
    assert "no longer" in message


def test_start_quest_rejects_missing_application_id(game_manager):
    native = FakeNative(payload=payload(quest(app_id=None)))
    ok, message = make_service(game_manager, native).start_quest("1")
    assert ok is False
    assert "application id" in message


def test_start_quest_adds_to_library_then_starts(game_manager, cached_game, monkeypatch):
    started = {}

    def fake_start(game_id):
        started["id"] = game_id
        return True, "Test Game started"

    monkeypatch.setattr(game_manager, "start_game", fake_start)
    native = FakeNative(payload=payload(quest()))

    ok, message = make_service(game_manager, native).start_quest("1")

    assert ok is True and message == "Test Game started"
    assert started["id"] == 100
    assert game_manager.db.is_in_library(100) is True


def test_start_quest_registers_application_missing_from_cache(game_manager, monkeypatch):
    monkeypatch.setattr(game_manager, "start_game", lambda game_id: (True, "started"))
    native = FakeNative(payload=payload(quest(app_id="777", game="Fresh Game")))

    ok, _ = make_service(game_manager, native).start_quest("1")

    assert ok is True
    game = game_manager.db.get_game(777)
    assert game is not None
    assert game.name == "Fresh Game"
    assert game.executables[0]["name"] == "FreshGame.exe"
    assert game_manager.db.is_in_library(777) is True


def test_stop_quest_delegates(game_manager, cached_game, monkeypatch):
    calls = []
    monkeypatch.setattr(game_manager, "stop_game", lambda gid: (calls.append(gid), (True, "stopped"))[1])
    native = FakeNative(payload=payload(quest()))
    ok, message = make_service(game_manager, native).stop_quest("1")
    assert ok is True and message == "stopped"
    assert calls == [100]


def test_play_quest_states_its_action(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["kind"] == "play"
    assert entry["enrolled"] is True
    assert entry["action"] == "run"


def test_unaccepted_play_quest_asks_for_enrollment(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(enrolled=False)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["action"] == "enroll"
    assert entry["enrolled"] is False

    ok, message = make_service(game_manager, native).start_quest("1")
    assert ok is False
    assert "Accept the quest" in message


def test_watch_quest_opens_discord_instead_of_running(game_manager):
    native = FakeNative(
        payload=payload(
            quest(kind="watch", app_id=None, video={"url": "quests/1/v.mp4", "thumbnail": "quests/1/t.jpg"})
        )
    )
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["kind"] == "watch"
    assert entry["action"] == "open"
    assert entry["video_url"] == "https://cdn.discordapp.com/quests/1/v.mp4"
    assert entry["video_thumbnail"] == "https://cdn.discordapp.com/quests/1/t.jpg"
    # Watch quests have no executable to fake, so no invented one either.
    assert entry["executables"] == []

    ok, message = make_service(game_manager, native).start_quest("1")
    assert ok is False
    assert "not completed by playing" in message


def test_mobile_watch_quest_is_marked_for_the_phone(game_manager):
    native = FakeNative(
        payload=payload(quest(kind="watch_mobile", app_id=None, target=60))
    )
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["kind"] == "watch_mobile"
    assert entry["action"] == "mobile"


def test_play_quests_sort_before_watch_quests(game_manager):
    native = FakeNative(
        payload=payload(
            quest("1", name="A watch", kind="watch", app_id=None),
            quest("2", name="B play"),
        )
    )
    names = [q["name"] for q in make_service(game_manager, native).list_quests()["quests"]]
    assert names == ["B play", "A watch"]


def test_payload_counter_is_passed_through(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(), total=81))
    listing = make_service(game_manager, native).list_quests()
    assert listing["total_quests"] == 81

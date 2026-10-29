"""Tests for the quest list built from the running Discord client."""


import time

import pytest

from launcher.discord_native import DiscordNativeError
from launcher.quests import (
    WATCH_TIMEOUT_SECONDS,
    QuestService,
    derive_executable_name,
)


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
        self.accepted = []
        self.progress_posts = []

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

    def accept_quest(self, quest_id):
        self.accepted.append(str(quest_id))
        return {"ok": True, "status": 200, "enrolled": True, "completed": False}

    def send_video_progress(self, quest_id, timestamp):
        self.progress_posts.append((str(quest_id), timestamp))
        return {"ok": True, "status": 200, "completed": False, "progress": None}

    def set_show_current_game(self, enabled):
        self.previous = getattr(self, "activity", True)
        self.activity = bool(enabled)
        self.activity_writes = getattr(self, "activity_writes", 0) + 1
        return self.previous


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


def make_service(game_manager, native, ttl=20.0, prefs_path=None):
    # monitor=False keeps the background tail thread out of the tests; the
    # tick itself is exercised directly.
    return QuestService(
        game_manager,
        native=native,
        ttl=ttl,
        prefs_path=prefs_path,
        monitor=False,
    )


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
    assert entry["reward"] == {
        "label": "700 Orbs",
        "labels": [],
        "orbs": 700,
        "premium_orbs": None,
        "avatar_decoration": False,
        "in_game": False,
    }
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


def test_unaccepted_play_quest_is_accepted_before_it_runs(
    game_manager, cached_game, monkeypatch
):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(payload=payload(quest(enrolled=False)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["action"] == "enroll"
    assert entry["enrolled"] is False

    ok, _message = make_service(game_manager, native).start_quest("1")
    assert ok is True
    assert native.accepted == ["1"]


def test_watch_quest_has_no_game_to_run(game_manager):
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


# ---------------------------------------------------------------------------
# quest options, orbs, and the play session tail
# ---------------------------------------------------------------------------


def test_listing_includes_orbs_and_default_prefs(game_manager, cached_game, tmp_path):
    data = payload(quest())
    data["orbs"] = 67080
    native = FakeNative(payload=data)
    listing = make_service(game_manager, native, prefs_path=tmp_path / "s.json").list_quests()
    assert listing["orbs"] == 67080
    assert listing["prefs"] == {"hide_activity": False, "play_session_tail_min": 2}


def test_prefs_round_trip(game_manager, tmp_path):
    path = tmp_path / "s.json"
    service = make_service(game_manager, FakeNative(payload=payload()), prefs_path=path)
    updated = service.update_prefs({"hide_activity": True, "play_session_tail_min": 5})
    assert updated == {"hide_activity": True, "play_session_tail_min": 5}
    assert service.prefs() == {"hide_activity": True, "play_session_tail_min": 5}
    assert path.exists()


def test_prefs_reject_out_of_range_tail(game_manager, tmp_path):
    service = make_service(game_manager, FakeNative(), prefs_path=tmp_path / "s.json")
    updated = service.update_prefs({"play_session_tail_min": 500})
    assert updated["play_session_tail_min"] <= 30


def test_starting_a_quest_hides_the_activity_when_asked(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager, "start_game", lambda gid: (True, "started"))
    monkeypatch.setattr(game_manager, "stop_game", lambda gid: (True, "stopped"))
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service.update_prefs({"hide_activity": True, "play_session_tail_min": 0})

    service.start_quest("1")
    assert native.activity is False

    service.stop_quest("1")
    assert native.activity is True
    assert native.activity_writes == 2


def test_activity_is_left_alone_when_the_option_is_off(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager, "start_game", lambda gid: (True, "started"))
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service.start_quest("1")
    assert getattr(native, "activity_writes", 0) == 0


def test_completed_applications_only_counts_play_quests():
    from launcher.quests import _completed_applications

    done = _completed_applications(
        payload(
            quest("1", app_id="100", progress=900, target=900),
            quest("2", app_id="200", progress=899, target=900),
            quest("3", app_id="300", kind="watch", progress=60, target=60),
            quest("4", app_id="400", progress=0, target=0),
        )
    )
    assert done == {100}


def test_monitor_schedules_a_tail_then_stops_the_game(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager.process_mgr, "is_running", lambda app_id: True)
    stopped = []
    monkeypatch.setattr(
        game_manager, "stop_game", lambda gid: (stopped.append(gid), (True, "stopped"))[1]
    )
    monkeypatch.setattr("launcher.quests.random.uniform", lambda low, high: high)
    native = FakeNative(payload=payload(quest(progress=900, target=900)))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service._track_start(100, "1")

    service._monitor_tick(1000.0)
    # 2 configured minutes at the upper end of the 40-100% window
    assert service._tails == {100: 1000.0 + 120.0}
    assert stopped == []

    service._monitor_tick(1120.5)
    assert stopped == [100]
    assert service._tails == {}
    assert service._quest_apps == {}


def test_monitor_with_zero_tail_ends_on_the_next_tick(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager.process_mgr, "is_running", lambda app_id: True)
    stopped = []
    monkeypatch.setattr(
        game_manager, "stop_game", lambda gid: (stopped.append(gid), (True, "stopped"))[1]
    )
    native = FakeNative(payload=payload(quest(progress=900, target=900)))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service.update_prefs({"play_session_tail_min": 0})
    service._track_start(100, "1")

    service._monitor_tick(1000.0)
    assert stopped == []
    service._monitor_tick(1000.1)
    assert stopped == [100]


def test_monitor_ignores_quests_that_are_not_finished(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager.process_mgr, "is_running", lambda app_id: True)
    native = FakeNative(payload=payload(quest(progress=10, target=900)))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service._track_start(100, "1")
    service._monitor_tick(1000.0)
    assert service._tails == {}


def test_monitor_untracks_a_process_that_stopped_by_itself(
    game_manager, cached_game, monkeypatch, tmp_path
):
    monkeypatch.setattr(game_manager.process_mgr, "is_running", lambda app_id: False)
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, prefs_path=tmp_path / "s.json")
    service.update_prefs({"hide_activity": True})
    service._track_start(100, "1")
    assert native.activity is False
    service._monitor_tick(1000.0)
    assert service._quest_apps == {}
    assert native.activity is True


# ---------------------------------------------------------------------------
# queue: selected quests run one after another
# ---------------------------------------------------------------------------


def _queue_fixture(game_manager, monkeypatch):
    started = []

    def fake_start(game_id):
        started.append(game_id)
        return True, f"{game_id} started"

    monkeypatch.setattr(game_manager, "start_game", fake_start)
    monkeypatch.setattr(game_manager, "stop_game", lambda gid: (True, "stopped"))


def test_start_queue_runs_the_first_quest(game_manager, cached_game, monkeypatch):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)

    ok, message = service.start_queue(["1", "2"])

    assert ok is True
    assert "Queued 2" in message
    assert service._queue == ["2"]
    assert 100 in service._quest_apps


def test_queue_starts_the_next_after_stop(game_manager, cached_game, monkeypatch):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    started = []
    monkeypatch.setattr(
        game_manager, "start_game", lambda gid: (started.append(gid), (True, "ok"))[1]
    )
    service.start_queue(["1", "2"])
    assert started == [100]

    service._track_stop(100)
    service._pump()

    assert started == [100, 200]
    assert service._queue == []


def test_queue_skips_quests_that_cannot_run(game_manager, cached_game, monkeypatch):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(
        payload=payload(
            quest("1", name="Good"),
            quest("2", name="Unaccepted", enrolled=False),
            quest("3", name="Watch", kind="watch", app_id=None),
            quest("4", name="Done", completed=True),
        )
    )
    service = make_service(game_manager, native)

    ok, message = service.start_queue(["1", "2", "3", "4", "nope"])

    assert ok is True
    # The unaccepted play quest and the video quest both queue; only the
    # finished quest and the unknown id are skipped.
    assert "skipped 2" in message
    assert service._queue == ["2", "3"]
    assert 100 in service._quest_apps


def test_queue_rejects_a_selection_it_cannot_run(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1", completed=True)))
    ok, message = make_service(game_manager, native).start_queue(["1"])
    assert ok is False
    assert "unfinished" in message


def test_queue_rejects_an_empty_selection(game_manager):
    ok, message = make_service(game_manager, FakeNative()).start_queue([])
    assert ok is False
    assert "at least one" in message


def test_clear_queue(game_manager, cached_game, monkeypatch):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    service.start_queue(["1", "2"])

    assert service.clear_queue() == 1
    assert service._queue == []


def test_video_quest_is_watched_in_the_background(game_manager, monkeypatch):
    opened = []
    native = FakeNative(
        payload=payload(
            quest("3", name="Watch", kind="watch", app_id=None, enrolled=False)
        )
    )
    service = make_service(game_manager, native)

    ok, _ = service.start_queue(["3"])

    assert ok is True
    # No window is opened: the client is asked to accept the quest and the
    # progress posts happen from here.
    assert opened == []
    assert native.accepted == ["3"]
    assert service._watching == "3"
    assert service._queue == []
    listed = service.list_quests()
    assert listed["queue"] == {"ids": ["3"], "active": "3", "watching": "3"}
    assert listed["quests"][0]["queued"] is True


def test_watch_posts_video_progress_on_discord_cadence(game_manager, monkeypatch):
    monkeypatch.setattr("launcher.quests.random.uniform", lambda a, b: 7.0)
    native = FakeNative(
        payload=payload(quest("3", name="Watch", kind="watch", app_id=None))
    )
    service = make_service(game_manager, native)
    service.start_queue(["3"])
    assert native.progress_posts == []

    service._monitor_tick(time.monotonic() + 8.0)

    assert len(native.progress_posts) == 1
    quest_id, timestamp = native.progress_posts[0]
    assert quest_id == "3"
    # The timestamp is the real time spent since the previous post.
    assert 7.0 <= timestamp <= 9.0


def test_watched_video_finishing_starts_the_next_quest(
    game_manager, cached_game, monkeypatch
):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(
        payload=payload(
            quest("3", name="Watch", kind="watch", app_id=None),
            quest("1", name="Play"),
        )
    )
    service = make_service(game_manager, native)
    started = []
    monkeypatch.setattr(
        game_manager, "start_game", lambda gid: (started.append(gid), (True, "ok"))[1]
    )
    service.start_queue(["3", "1"])
    assert service._watching == "3"
    assert started == []

    native.payload = payload(
        quest("3", name="Watch", kind="watch", app_id=None, progress=90, target=90),
        quest("1", name="Play"),
    )
    service._monitor_tick(time.monotonic() + 16.0)

    assert service._watching is None
    assert started == [100]
    assert service._queue == []


def test_skip_watch_moves_on(game_manager, cached_game, monkeypatch):
    _queue_fixture(game_manager, monkeypatch)
    native = FakeNative(
        payload=payload(
            quest("3", name="Watch", kind="watch", app_id=None),
            quest("1", name="Play"),
        )
    )
    service = make_service(game_manager, native)
    service.start_queue(["3", "1"])

    ok, _message = service.skip_watch()

    assert ok is True
    assert service._watching is None
    assert 100 in service._quest_apps


def test_skip_watch_when_nothing_is_waiting(game_manager):
    ok, message = make_service(game_manager, FakeNative()).skip_watch()
    assert ok is False
    assert "Nothing" in message


def test_watch_wait_times_out(game_manager, monkeypatch):
    native = FakeNative(
        payload=payload(quest("3", name="Watch", kind="watch", app_id=None))
    )
    service = make_service(game_manager, native)
    service.start_queue(["3"])

    service._monitor_tick(time.monotonic() + WATCH_TIMEOUT_SECONDS + 1.0)

    assert service._watching is None


def test_failed_start_keeps_the_quest_at_the_head(game_manager, cached_game, monkeypatch):
    monkeypatch.setattr(game_manager, "start_game", lambda gid: (False, "Discord is gone"))
    native = FakeNative(payload=payload(quest("1")))
    service = make_service(game_manager, native)

    service.start_queue(["1"])

    assert service._queue == ["1"]
    assert service._quest_apps == {}

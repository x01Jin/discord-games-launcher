"""Tests for the quest list built from the running Discord client."""


import json
import tempfile
import time
from pathlib import Path

import pytest

from launcher.discord_native import DiscordNativeError
from launcher.quests import (
    PLAY_TIMEOUT_SECONDS,
    WATCH_TIMEOUT_SECONDS,
    QuestService,
    derive_executable_name,
)
from launcher.rpc_activity import RpcError


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
        self.heartbeats = []
        self.claims = []
        self.claim_error = None
        self.credited = {}
        self.heartbeat_error = None

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

    def send_heartbeat(self, quest_id, application_id, executable_path, terminal=False):
        if self.heartbeat_error:
            raise self.heartbeat_error
        quest_id = str(quest_id)
        self.heartbeats.append((quest_id, str(application_id), str(executable_path), bool(terminal)))
        return {
            "ok": True,
            "status": 200,
            "completed": False,
            "credited": self.credited.get(quest_id),
        }

    def claim_quest_reward(self, quest_id):
        self.claims.append(str(quest_id))
        if self.claim_error:
            raise self.claim_error
        return {"ok": True, "status": 200, "enrolled": True, "completed": True}


def quest(
    quest_id="1",
    app_id="100",
    name="Test Quest",
    game="Test Game",
    target=900,
    progress=0,
    completed=False,
    claimed=False,
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
        "claimedAt": "2026-01-01T00:00:00+00:00" if claimed else None,
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


def make_service(game_manager, native, ttl=20.0, prefs_path=None, rpc=None, notifier=None):
    # monitor=False keeps the background tail thread out of the tests; the
    # tick itself is exercised directly. The settings file is always a scratch
    # one, because a real settings.json would leak its options into every test.
    if prefs_path is None:
        prefs_path = Path(tempfile.mkdtemp(prefix="dcgl-prefs-")) / "settings.json"
    service = QuestService(
        game_manager,
        native=native,
        ttl=ttl,
        prefs_path=prefs_path,
        monitor=False,
        activity=rpc or FakeRpc(),
        notifier=notifier,
    )
    return service


class FakeRpc:
    """Stands in for the client's game pipe."""

    def __init__(self):
        self.shows = []
        self.hides = 0
        self.show_error = None

    def show(self, application_id, name):
        if self.show_error:
            raise self.show_error
        self.shows.append((int(application_id), str(name)))

    def hide(self):
        self.hides += 1


@pytest.fixture(autouse=True)
def silent_runs(monkeypatch):
    """Keep the suite on the heartbeat path unless a test asks for activity.

    Tests that write their own settings file still start from these defaults,
    so none of them reaches for a real process manager.
    """
    from launcher import prefs as quest_prefs

    monkeypatch.setitem(quest_prefs.DEFAULTS, "run_mode", quest_prefs.MODE_SILENT)


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


def test_start_quest_credits_with_heartbeats(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native)

    ok, message = service.start_quest("1")

    assert ok is True
    assert message == "Crediting Test Quest"
    assert service._playing == "1"
    assert native.heartbeats == [("1", "100", "testgame.exe", False)]
    # A run is a heartbeat stream: no process, no library entry.
    assert game_manager.db.get_library_ids() == set()


def test_start_quest_works_without_a_cached_game(game_manager):
    native = FakeNative(payload=payload(quest(app_id="777", game="Fresh Game")))

    ok, _message = make_service(game_manager, native).start_quest("1")

    assert ok is True
    assert native.heartbeats[0][1] == "777"
    assert native.heartbeats[0][2] == "FreshGame.exe"
    assert game_manager.db.get_game(777) is None


def test_stop_quest_posts_a_terminal_beat(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native)
    service.start_quest("1")

    ok, message = service.stop_quest("1")

    assert ok is True
    assert message == "Stopped the quest session"
    assert service._playing is None
    assert native.heartbeats[-1] == ("1", "100", "testgame.exe", True)


def test_stop_quest_without_a_session(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))

    ok, message = make_service(game_manager, native).stop_quest("1")

    assert ok is False
    assert message == "That quest is not running"


def test_running_quest_row_offers_stop(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native)
    service.start_quest("1")

    entry = service.list_quests()["quests"][0]

    assert entry["state"] == "running"
    assert entry["action"] == "stop"
    assert entry["queued"] is False


def test_play_quest_states_its_action(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    assert entry["kind"] == "play"
    assert entry["enrolled"] is True
    assert entry["action"] == "run"


def test_unaccepted_play_quest_is_accepted_before_it_runs(
    game_manager, cached_game, monkeypatch
):
    native = FakeNative(payload=payload(quest(enrolled=False)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]
    # Run accepts the quest itself, so there is no enrollment step in the row.
    assert entry["action"] == "run"
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


def test_mobile_watch_quest_is_credited_from_here(game_manager):
    native = FakeNative(
        payload=payload(quest(kind="watch_mobile", app_id=None, target=60))
    )
    service = make_service(game_manager, native)
    entry = service.list_quests()["quests"][0]
    assert entry["kind"] == "watch_mobile"
    assert entry["action"] == "open"

    # The mobile key posts to the same video-progress endpoint, so the queue
    # takes it instead of leaving the row unstartable.
    ok, _message = service.start_queue(["1"])
    assert ok is True
    assert service._watching == "1"


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
    assert listing["prefs"] == {"play_session_tail_min": 2, "run_mode": "silent"}


def test_prefs_round_trip(game_manager, tmp_path):
    path = tmp_path / "s.json"
    service = make_service(game_manager, FakeNative(), prefs_path=path)
    assert service.update_prefs({"play_session_tail_min": 5}) == {
        "play_session_tail_min": 5,
        "run_mode": "silent",
    }
    assert make_service(game_manager, FakeNative(), prefs_path=path).prefs() == {
        "play_session_tail_min": 5,
        "run_mode": "silent",
    }


def test_prefs_reject_out_of_range_tail(game_manager, tmp_path):
    service = make_service(game_manager, FakeNative(), prefs_path=tmp_path / "s.json")
    assert service.update_prefs({"play_session_tail_min": 900}) == {
        "play_session_tail_min": 30,
        "run_mode": "silent",
    }
    assert service.update_prefs({"play_session_tail_min": -3}) == {
        "play_session_tail_min": 0,
        "run_mode": "silent",
    }
    # Text that is not a number leaves the stored value alone.
    assert service.update_prefs({"play_session_tail_min": "soon"}) == {
        "play_session_tail_min": 0,
        "run_mode": "silent",
    }


# ---------------------------------------------------------------------------
# play sessions: one heartbeat per beat, stop when Discord says done
# ---------------------------------------------------------------------------


def test_monitor_beats_the_session(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(target=900)))
    service = make_service(game_manager, native)
    service.start_quest("1")

    service._monitor_tick(service._beat_next + 0.1)

    assert len(native.heartbeats) == 2
    assert native.heartbeats[-1][3] is False


def test_monitor_stops_a_quest_discord_reports_finished(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(target=100)))
    service = make_service(game_manager, native)
    service.start_quest("1")
    native.credited["1"] = 100

    service._monitor_tick(service._beat_next + 0.1)

    assert service._playing is None


def test_monitor_keeps_going_after_a_failed_beat(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native)
    service.start_quest("1")
    native.heartbeat_error = DiscordNativeError("socket closed")

    service._monitor_tick(service._beat_next + 0.1)

    assert service._playing == "1"


def test_monitor_stops_after_the_timeout(game_manager, cached_game):
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native)
    service.start_quest("1")

    service._monitor_tick(service._playing_at + PLAY_TIMEOUT_SECONDS + 1.0)

    assert service._playing is None


def test_a_finished_quest_waits_for_the_tail_before_the_next(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1", target=100), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    service.start_queue(["1", "2"])
    assert service._playing == "1"
    assert service._queue == ["2"]

    native.credited["1"] = 100
    service._monitor_tick(service._beat_next + 0.1)

    # The session ended, but the tail keeps the next quest waiting.
    assert service._playing is None
    assert service._play_ready_at > time.monotonic()
    assert service._queue == ["2"]

    service._play_ready_at = 0.0
    service._pump()

    assert service._playing == "2"


def test_a_zero_tail_starts_the_next_quest_at_once(game_manager, cached_game, tmp_path):
    path = tmp_path / "s.json"
    native = FakeNative(payload=payload(quest("1", target=100), quest("2", app_id="200")))
    service = make_service(game_manager, native, prefs_path=path)
    service.update_prefs({"play_session_tail_min": 0})
    service.start_queue(["1", "2"])

    native.credited["1"] = 100
    service._monitor_tick(service._beat_next + 0.1)

    assert service._playing == "2"


# ---------------------------------------------------------------------------
# activity mode: the game is shown in the client, time still comes from beats
# ---------------------------------------------------------------------------


def activity_service(game_manager, native, tmp_path, show_error=None):
    path = tmp_path / "activity.json"
    path.write_text(
        json.dumps({"run_mode": "activity", "play_session_tail_min": 0}), encoding="utf-8"
    )
    rpc = FakeRpc()
    rpc.show_error = show_error
    return make_service(game_manager, native, prefs_path=path, rpc=rpc)


def test_activity_mode_shows_the_game_and_still_posts_a_heartbeat(
    game_manager, cached_game, tmp_path
):
    native = FakeNative(payload=payload(quest()))
    service = activity_service(game_manager, native, tmp_path)

    ok, message = service.start_quest("1")

    assert ok is True
    assert message == "Showing Test Quest as playing"
    # No process is launched: the game only goes to the client's game pipe.
    assert service._rpc.shows == [(100, "Test Quest")]
    assert len(native.heartbeats) == 1
    assert native.heartbeats[0][:3] == ("1", "100", "testgame.exe")
    assert service._playing == "1"
    assert service._activity_shown is True


def test_activity_mode_withdraws_the_game_on_stop(
    game_manager, cached_game, tmp_path
):
    native = FakeNative(payload=payload(quest()))
    service = activity_service(game_manager, native, tmp_path)
    service.start_quest("1")

    ok, message = service.stop_quest("1")

    assert ok is True
    assert message == "Stopped the quest session"
    assert service._rpc.hides == 1
    # The beat has to be closed as well: the server keeps crediting otherwise.
    assert native.heartbeats[-1][3] is True
    assert service._playing is None
    assert service._activity_shown is False


def test_activity_mode_falls_back_to_private_when_the_store_refuses(
    game_manager, cached_game, tmp_path
):
    native = FakeNative(payload=payload(quest()))
    service = activity_service(
        game_manager,
        native,
        tmp_path,
        show_error=RpcError("Discord is not listening for game activity"),
    )

    ok, message = service.start_quest("1")

    assert ok is True
    assert message == "Crediting Test Quest"
    assert service._rpc.shows == []
    assert len(native.heartbeats) == 1
    assert service._activity_shown is False


def test_activity_mode_withdraws_the_game_when_the_quest_finishes(
    game_manager, cached_game, tmp_path
):
    native = FakeNative(payload=payload(quest(target=900)))
    service = activity_service(game_manager, native, tmp_path)
    service.start_quest("1")
    native.credited["1"] = 900

    service._monitor_tick(service._beat_next + 0.1)

    assert service._rpc.hides == 1
    assert service._playing is None
    # The beat that crossed the target already credited the time.
    assert all(beat[3] is False for beat in native.heartbeats)


def test_activity_mode_withdraws_the_game_on_shutdown(
    game_manager, cached_game, tmp_path
):
    native = FakeNative(payload=payload(quest()))
    service = activity_service(game_manager, native, tmp_path)
    service.start_quest("1")

    service.shutdown()

    assert service._rpc.hides == 1
    assert native.heartbeats[-1][3] is True


def test_private_mode_never_touches_the_activity_store(
    game_manager, cached_game, tmp_path
):
    path = tmp_path / "private.json"
    path.write_text(
        json.dumps({"run_mode": "silent", "play_session_tail_min": 0}), encoding="utf-8"
    )
    native = FakeNative(payload=payload(quest()))
    service = make_service(game_manager, native, prefs_path=path)

    ok, message = service.start_quest("1")
    service.stop_quest("1")

    assert ok is True
    assert message == "Crediting Test Quest"
    assert service._rpc.shows == []
    assert service._rpc.hides == 0


# ---------------------------------------------------------------------------
# queue: selected quests run in order, one per lane
# ---------------------------------------------------------------------------


def test_start_queue_runs_the_first_quest(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)

    ok, message = service.start_queue(["1", "2"])

    assert ok is True
    assert "Queued 2" in message
    assert service._playing == "1"
    assert service._queue == ["2"]


def test_queue_starts_the_next_after_a_manual_stop(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    service.start_queue(["1", "2"])

    service.stop_quest("1")

    assert service._playing == "2"
    assert service._queue == []


def test_queue_skips_quests_that_cannot_run(game_manager, cached_game):
    native = FakeNative(
        payload=payload(
            quest("1", name="Done", completed=True),
            quest("2", name="Live"),
            quest("3", name="Watch", kind="watch", app_id=None, target=60),
            quest("4", name="Gone", expires="2000-01-01T00:00:00+00:00"),
        )
    )
    service = make_service(game_manager, native)

    ok, message = service.start_queue(["1", "2", "3", "4"])

    assert ok is True
    assert "skipped 2" in message
    # The game and the video take their own lanes.
    assert service._playing == "2"
    assert service._watching == "3"
    assert service._queue == []


def test_queue_rejects_a_selection_it_cannot_run(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True)))

    ok, message = make_service(game_manager, native).start_queue(["1"])

    assert ok is False
    assert "None of the selected" in message


def test_queue_rejects_an_empty_selection(game_manager):
    ok, message = make_service(game_manager, FakeNative()).start_queue([])
    assert ok is False
    assert message == "Select at least one quest"


def test_clear_queue(game_manager, cached_game):
    native = FakeNative(
        payload=payload(quest("1"), quest("2", app_id="200"), quest("3", app_id="300"))
    )
    service = make_service(game_manager, native)
    service.start_queue(["1", "2", "3"])
    assert service._queue == ["2", "3"]

    assert service.clear_queue() == 2
    assert service._queue == []


def test_reorder_queue_puts_the_given_order_first(game_manager, cached_game):
    native = FakeNative(
        payload=payload(quest("1"), quest("2", app_id="200"), quest("3", app_id="300"))
    )
    service = make_service(game_manager, native)
    service.start_queue(["1", "2", "3"])

    ok, message = service.reorder_queue(["3", "2"])

    assert ok is True
    assert message == "Queue reordered"
    assert service._queue == ["3", "2"]


def test_reorder_queue_keeps_unlisted_ids_at_the_end(game_manager, cached_game):
    native = FakeNative(
        payload=payload(quest("1"), quest("2", app_id="200"), quest("3", app_id="300"))
    )
    service = make_service(game_manager, native)
    service.start_queue(["1", "2", "3"])

    ok, _message = service.reorder_queue(["3"])

    assert ok is True
    assert service._queue == ["3", "2"]


def test_reorder_queue_rejects_unknown_ids(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    service.start_queue(["1", "2"])

    ok, message = service.reorder_queue(["does-not-exist"])

    assert ok is False
    assert message == "That order named no queued quest"
    assert service._queue == ["2"]


def test_reorder_an_empty_queue(game_manager):
    ok, message = make_service(game_manager, FakeNative()).reorder_queue(["1"])
    assert ok is False
    assert message == "The queue is empty"


def test_drop_queue_item_leaves_the_rest(game_manager, cached_game):
    native = FakeNative(
        payload=payload(quest("1"), quest("2", app_id="200"), quest("3", app_id="300"))
    )
    service = make_service(game_manager, native)
    service.start_queue(["1", "2", "3"])

    ok, message = service.drop_queue_item("2")

    assert ok is True
    assert message == "Removed it from the queue, 1 left"
    assert service._queue == ["3"]


def test_drop_queue_item_rejects_a_quest_that_is_not_waiting(game_manager):
    ok, _message = make_service(game_manager, FakeNative()).drop_queue_item("1")
    assert ok is False


def test_failed_start_keeps_the_quest_at_the_head(game_manager, cached_game, monkeypatch):
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    calls = []

    def refuse(quest_id):
        calls.append(quest_id)
        return False, "Discord would not credit that quest"

    monkeypatch.setattr(service, "start_quest", refuse)

    ok, _message = service.start_queue(["1", "2"])
    service._monitor_tick(time.monotonic() + 1.0)

    assert ok is True
    assert calls[:2] == ["1", "1"]
    assert service._queue == ["1", "2"]


# ---------------------------------------------------------------------------
# video quests: progress posted from here, no Discord window
# ---------------------------------------------------------------------------


def test_stop_quest_ends_the_watched_video(game_manager, cached_game):
    native = FakeNative(
        payload=payload(quest("3", name="Watch", kind="watch", app_id=None), quest("1"))
    )
    service = make_service(game_manager, native)
    service.start_queue(["3", "1"])
    assert service._watching == "3"
    assert service._playing == "1"

    ok, message = service.stop_quest("3")

    assert ok is True
    assert message == "Stopped watching the video"
    assert service._watching is None
    # The game lane was never affected.
    assert service._playing == "1"


def test_a_watched_video_row_offers_stop(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("3", kind="watch", app_id=None)))
    service = make_service(game_manager, native)
    service.start_queue(["3"])

    entry = service.list_quests()["quests"][0]

    assert entry["state"] == "running"
    assert entry["action"] == "stop"


def test_video_quest_is_credited_in_the_background(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("3", kind="watch", app_id=None, target=120)))
    service = make_service(game_manager, native)

    ok, _message = service.start_queue(["3"])

    assert ok is True
    assert service._watching == "3"
    assert service._queue == []


def test_watch_posts_video_progress_on_discord_cadence(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("3", kind="watch", app_id=None, target=120)))
    service = make_service(game_manager, native)
    service.start_queue(["3"])
    now = time.monotonic()
    service._watch_last = now - 8.0
    service._watch_next = now

    service._watch_step(now + 0.5)

    assert native.progress_posts
    quest_id, timestamp = native.progress_posts[-1]
    assert quest_id == "3"
    assert 7.0 <= timestamp <= 9.0
    assert service._watch_next > now


def test_skip_watch_moves_on(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("3", kind="watch", app_id=None), quest("1")))
    service = make_service(game_manager, native)
    service.start_queue(["3", "1"])

    ok, message = service.skip_watch()

    assert ok is True
    assert message == "Skipped the video and moved on"
    assert service._watching is None
    assert service._playing == "1"


def test_skip_watch_when_nothing_is_waiting(game_manager):
    ok, _message = make_service(game_manager, FakeNative()).skip_watch()
    assert ok is False


def test_watch_wait_times_out(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("3", kind="watch", app_id=None)))
    service = make_service(game_manager, native)
    service.start_queue(["3"])
    service._watching_at = time.monotonic() - WATCH_TIMEOUT_SECONDS - 1.0

    service._monitor_tick(time.monotonic())

    assert service._watching is None


# ---------------------------------------------------------------------------
# one game session at a time
# ---------------------------------------------------------------------------


def test_a_manual_run_while_a_game_is_playing_is_queued(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1"), quest("2", app_id="200")))
    service = make_service(game_manager, native)
    service.start_queue(["1"])

    ok, message = service.start_quest("2")

    assert ok is True
    assert message == "Queued behind the game quest that is running"
    assert service._playing == "1"
    assert service._queue == ["2"]
    # Only one session is beating.
    assert {beat[0] for beat in native.heartbeats} == {"1"}


def test_running_the_playing_quest_again_is_a_no_op(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1")))
    service = make_service(game_manager, native)
    service.start_quest("1")

    ok, message = service.start_quest("1")

    assert ok is True
    assert message == "That quest is already running"
    assert len(native.heartbeats) == 1


def test_shutdown_closes_the_session(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1")))
    service = make_service(game_manager, native)
    service.start_quest("1")

    service.shutdown()

    assert service._playing is None
    assert native.heartbeats[-1][3] is True


# ---------------------------------------------------------------------------
# claiming rewards
# ---------------------------------------------------------------------------


class FakeNotifier:
    """Records what would have gone to the Action Center."""

    def __init__(self):
        self.finished = []

    def quest_finished(self, name, reward=None):
        self.finished.append((name, reward))


def test_a_finished_quest_offers_claim(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True, progress=900)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]

    assert entry["state"] == "completed"
    assert entry["claimed"] is False
    assert entry["claimable"] is True
    assert entry["action"] == "claim"


def test_a_claimed_quest_reads_done(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True, claimed=True)))
    entry = make_service(game_manager, native).list_quests()["quests"][0]

    assert entry["claimed"] is True
    assert entry["claimable"] is False
    assert entry["action"] == "done"


def test_claim_reward_claims_through_the_client(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True, progress=900)))
    service = make_service(game_manager, native)

    ok, message, captcha = service.claim_reward("1")

    assert ok is True
    assert message == "Reward claimed"
    assert captcha is False
    assert native.claims == ["1"]


def test_a_captcha_comes_back_as_user_action(game_manager, cached_game):
    from launcher.discord_native import QuestApiError

    native = FakeNative(payload=payload(quest(completed=True, progress=900)))
    native.claim_error = QuestApiError("Captcha required", captcha=True)
    service = make_service(game_manager, native)

    ok, message, captcha = service.claim_reward("1")

    assert ok is False
    assert captcha is True
    assert "captcha" in message.lower()


def test_claim_refuses_a_quest_that_is_not_finished(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(progress=300, target=900)))
    service = make_service(game_manager, native)

    ok, message, captcha = service.claim_reward("1")

    assert ok is False
    assert captcha is False
    assert message == "That quest is not finished yet"
    assert native.claims == []


def test_claim_is_idempotent_when_discord_already_recorded_it(game_manager, cached_game):
    native = FakeNative(payload=payload(quest(completed=True, claimed=True)))
    service = make_service(game_manager, native)

    ok, message, _captcha = service.claim_reward("1")

    assert ok is True
    assert "already claimed" in message
    assert native.claims == []


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------


def test_finishing_a_play_quest_posts_a_notification(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1", target=100)))
    notifier = FakeNotifier()
    service = make_service(game_manager, native, notifier=notifier)
    service.start_quest("1")
    native.credited["1"] = 100

    service._monitor_tick(service._beat_next + 0.1)

    assert notifier.finished == [("Test Quest", "700 Orbs")]
    assert service._playing is None


def test_finishing_a_video_quest_posts_a_notification(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("2", kind="watch", target=60, orbs=200)))
    notifier = FakeNotifier()
    service = make_service(game_manager, native, notifier=notifier)
    service.start_queue(["2"])

    def completed_progress(quest_id, timestamp):
        native.progress_posts.append((str(quest_id), timestamp))
        return {"ok": True, "status": 200, "completed": True, "progress": None}

    native.send_video_progress = completed_progress
    service._monitor_tick(service._watch_next + 0.1)

    assert notifier.finished == [("Test Quest", "200 Orbs")]


def test_a_stopped_quest_does_not_notify(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1", target=900)))
    notifier = FakeNotifier()
    service = make_service(game_manager, native, notifier=notifier)
    service.start_quest("1")

    service.stop_quest("1")

    assert notifier.finished == []


def test_a_finished_quest_pushes_the_new_state(game_manager, cached_game):
    native = FakeNative(payload=payload(quest("1", target=100)))
    service = make_service(game_manager, native)
    pushes = []
    service.on_change = lambda: pushes.append("changed")
    service.start_quest("1")
    native.credited["1"] = 100

    service._monitor_tick(service._beat_next + 0.1)

    assert pushes == ["changed", "changed"]

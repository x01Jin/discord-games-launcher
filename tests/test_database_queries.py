import pytest

GAMES = [
    {
        "id": 1,
        "name": "Alpha One",
        "aliases": [],
        "executables": [{"name": "alpha.exe", "os": "win32", "is_launcher": False}],
        "icon_hash": "a",
        "themes": [],
        "isPublished": True,
    },
    {
        "id": 2,
        "name": "Beta Two",
        "aliases": [],
        "executables": [{"name": "beta.exe", "os": "win32", "is_launcher": False}],
        "icon_hash": "b",
        "themes": [],
        "isPublished": True,
    },
    {
        "id": 3,
        "name": "Gamma Three",
        "aliases": [],
        "executables": [{"name": "gamma.app", "os": "darwin", "is_launcher": False}],
        "icon_hash": "c",
        "themes": [],
        "isPublished": True,
    },
    {
        "id": 4,
        "name": "Delta Four",
        "aliases": [],
        "executables": [{"name": "delta", "os": "linux", "is_launcher": False}],
        "icon_hash": "d",
        "themes": [],
        "isPublished": True,
    },
]


@pytest.fixture
def seeded(database):
    database.save_games(GAMES)
    return database


def test_get_games_page_filters_windows(seeded):
    page = seeded.get_games_page(limit=10, offset=0)
    assert [g.name for g in page] == ["Alpha One", "Beta Two"]


def test_get_games_page_paginates(seeded):
    first = seeded.get_games_page(limit=1, offset=0)
    second = seeded.get_games_page(limit=1, offset=1)
    assert [g.name for g in first] == ["Alpha One"]
    assert [g.name for g in second] == ["Beta Two"]
    assert seeded.get_games_page(limit=1, offset=5) == []


def test_get_games_page_can_include_everything(seeded):
    page = seeded.get_games_page(limit=10, offset=0, win32_only=False)
    assert len(page) == 4


def test_get_games_page_tolerates_bad_paging(seeded):
    assert len(seeded.get_games_page(limit=0, offset=-5)) == 1


def test_search_games_is_windows_only(seeded):
    assert [g.name for g in seeded.search_games("a", limit=10)] == ["Alpha One", "Beta Two"]
    assert seeded.search_games("Gamma", limit=10) == []


def test_search_games_can_include_everything(seeded):
    assert [g.name for g in seeded.search_games("Gamma", limit=10, win32_only=False)] == [
        "Gamma Three"
    ]


def test_get_games_bulk(seeded):
    found = seeded.get_games([1, 2, 4])
    assert sorted(found) == [1, 2, 4]
    assert found[2].name == "Beta Two"
    assert seeded.get_games([]) == {}


def test_get_games_bulk_chunks_large_lists(seeded, monkeypatch):
    found = seeded.get_games(list(range(1, 1201)))
    assert sorted(found) == [1, 2, 3, 4]


def test_ensure_game_row_inserts_only(seeded):
    assert seeded.ensure_game_row(900, "Brand New", "hash", [{"name": "new.exe", "os": "win32"}])
    row = seeded.get_game(900)
    assert row is not None and row.name == "Brand New"
    assert row.executables == [{"name": "new.exe", "os": "win32"}]

    seeded.ensure_game_row(900, "Renamed", None, [])
    assert seeded.get_game(900).name == "Brand New"


def test_stats_count_playable_games(seeded):
    stats = seeded.get_cache_stats()
    assert stats["cached_games"] == 4
    assert stats["games_no_win_exes"] == 2


def test_stats_are_memoised_then_invalidated(seeded, monkeypatch):
    first = seeded.get_cache_stats()
    assert first["cached_games"] == 4

    seeded.save_games([{**GAMES[0], "id": 5, "name": "Epsilon"}])
    second = seeded.get_cache_stats()
    assert second["cached_games"] == 5


def test_stats_invalidated_by_library_write(seeded):
    assert seeded.get_cache_stats()["library_games"] == 0
    seeded.add_to_library(1, "/tmp/a.exe", "alpha.exe", "alpha.exe", [])
    assert seeded.get_cache_stats()["library_games"] == 1


def test_ensure_game_row_updates_stats(seeded):
    assert seeded.get_cache_stats()["cached_games"] == 4
    seeded.ensure_game_row(901, "Another", None, [])
    assert seeded.get_cache_stats()["cached_games"] == 5


def test_count_playable_matches_page_total(database):
    database.save_games(GAMES)
    assert database.get_cache_stats()["cached_games"] - database.get_cache_stats()[
        "games_no_win_exes"
    ] == len(database.get_games_page(limit=100))

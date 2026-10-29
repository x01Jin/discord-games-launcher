
import sqlite3
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from launcher.database import Game

from launcher.api import DiscordAPIClient, DiscordAPIError
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator, DummyGeneratorError
from launcher.library_maintenance import MaintenanceMixin
from launcher.process_manager import ProcessError, ProcessManager


class GameManagerError(Exception):
    pass


class GameManager(MaintenanceMixin):

    def __init__(
        self,
        database: Database,
        api_client: DiscordAPIClient,
        dummy_generator: DummyGenerator,
        process_manager: ProcessManager,
        logger=None,
    ):
        self.db = database
        self.api = api_client
        self.dummy_gen = dummy_generator
        self.process_mgr = process_manager
        self.logger = logger

    def sync_games(self, force: bool = False) -> tuple:
        try:
            was_synced, count, skipped = self.api.sync_cache(force=force)
            if was_synced:
                self.refresh_library_candidates(drop_superseded=False)
            else:
                stats = self.db.get_cache_stats()
                count = stats["cached_games"]
            return was_synced, count, skipped
        except (DiscordAPIError, sqlite3.Error, OSError) as e:
            raise GameManagerError(f"Failed to sync games: {e}")

    def note_api_version(self, version: str | None) -> str:
        from launcher.api import API_VERSION_CANDIDATES

        if not version:
            return ""
        newest = API_VERSION_CANDIDATES[0]
        try:
            previous = self.db.get_metadata_value("active_api_version")
            self.db.set_metadata_value("active_api_version", version)
        except (sqlite3.Error, OSError, ValueError):
            previous = None
        if previous == version:
            return ""
        if self.logger:
            if version == newest:
                self.logger.info(f"Discord API back on latest ({version})")
            else:
                self.logger.warning(
                    f"Discord API {newest} unreachable, using fallback ({version})"
                )
        if version == newest and previous is not None:
            return f": back on latest API ({version})"
        if version != newest:
            return f": using fallback API ({version})"
        return ""

    def search_games(self, query: str, limit: int = 100) -> list["Game"]:
        return self.db.search_games(query, limit, win32_only=True)

    def get_all_games(self, limit: int | None = None) -> list["Game"]:
        return self.db.get_all_games(limit)

    def get_games_page(self, limit: int = 200, offset: int = 0) -> list["Game"]:
        return self.db.get_games_page(limit, offset, win32_only=True)

    def count_playable_games(self) -> int:
        stats = self.db.get_cache_stats()
        return max(0, stats.get("cached_games", 0) - stats.get("games_no_win_exes", 0))

    def get_game(self, game_id: int) -> Optional["Game"]:
        return self.db.get_game(game_id)

    def add_to_library(self, game_id: int) -> tuple:
        game = self.db.get_game(game_id)
        if not game:
            return False, "Game not found in cache"

        if self.db.is_in_library(game_id):
            return False, "Game is already in library"

        if not self.dummy_gen.is_template_available():
            return False, (
                "DummyGame.exe template not found. "
                "Run 'python templates/build_dummy.py' to build it."
            )

        win_executables = self.api.get_best_win32_executables(game.executables)

        if not win_executables:
            return False, "No Windows executable found for this game"

        best_exe = win_executables[0]
        process_name = best_exe["name"]


        normalized_name = self.api.normalize_process_name(process_name)

        try:
            exe_path, _actual_name = self.dummy_gen.ensure_dummy_for_game(
                game_id=game_id, process_name=process_name
            )

            self.db.add_to_library(
                game_id,
                str(exe_path),
                normalized_name,
                normalized_name,
                win_executables,
            )

            if self.logger:
                self.logger.game_add_library(game.name, game_id, len(win_executables))

            return (
                True,
                f"Added {game.name} to library ({len(win_executables)} executable variant(s))",
            )

        except (DummyGeneratorError, sqlite3.Error, OSError) as e:
            return False, f"Failed to add game: {e}"

    def remove_from_library(self, game_id: int) -> tuple:
        if not self.db.is_in_library(game_id):
            return False, "Game is not in library"

        lib_game = self.db.get_library_game(game_id)
        if not lib_game:
            return False, "Failed to get library entry"

        if self.process_mgr.is_running(game_id):
            self.process_mgr.stop_process(game_id)

        try:
            self.dummy_gen.remove_dummy(game_id, lib_game.process_name)
        except OSError as e:
            if self.logger:
                self.logger.warning(
                    f"Could not remove dummy files for game {game_id}: {e}"
                )

        self.db.remove_from_library(game_id)

        if self.logger:
            game = self.db.get_game(game_id)
            game_name = game.name if game else f"Game {game_id}"
            self.logger.game_remove_library(game_name, game_id)

        return True, "Game removed from library"

    def get_library(self) -> list[dict[str, Any]]:
        library = self.db.get_library()

        for game in library:
            game["is_running"] = self.process_mgr.is_running(game["game_id"])

        return library

    def is_in_library(self, game_id: int) -> bool:
        return self.db.is_in_library(game_id)

    def start_game(self, game_id: int) -> tuple:
        if not self.db.is_in_library(game_id):
            return False, "Game is not in library"

        lib_game = self.db.get_library_game(game_id)
        game = self.db.get_game(game_id)

        if not lib_game:
            return False, "Failed to get library entry"

        if self.process_mgr.is_running(game_id):
            return False, "Game is already running"

        if not lib_game.executables:
            return False, "No executable candidates stored for this game"

        game_name = game.name if game else f"Game {game_id}"
        best = lib_game.executables[0].get("name", lib_game.process_name)
        normalized = self.api.normalize_process_name(best)

        if self.logger:
            self.logger.game_start_request(game_name, game_id)

        try:
            exe_path, _actual = self.dummy_gen.ensure_dummy_for_game(
                game_id=game_id, process_name=best
            )
            self.process_mgr.start_process(game_id, exe_path, game_name)
        except (DummyGeneratorError, ProcessError, OSError, sqlite3.Error) as e:
            self.db.record_executable_attempt(game_id, normalized, success=False)
            return False, f"Failed to start game: {e}"

        self.db.record_executable_attempt(game_id, normalized, success=True)
        return True, f"{game_name} started"

    def stop_game(self, game_id: int) -> tuple:
        if not self.process_mgr.is_running(game_id):
            return False, "Game is not running"

        try:
            if self.process_mgr.stop_process(game_id):
                return True, "Game stopped"
            else:
                return False, "Failed to stop game"
        except Exception as e:
            return False, f"Error stopping game: {e}"

    def stop_all_games(self) -> int:
        return self.process_mgr.stop_all_processes()

    def get_running_games(self) -> list[int]:
        return self.process_mgr.get_running_games()

    def get_cache_stats(self) -> dict[str, int]:
        return self.db.get_cache_stats()

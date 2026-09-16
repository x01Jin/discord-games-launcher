"""Discord Games Launcher - Game Manager module.

High-level interface for managing game library operations.
Coordinates between database, API, dummy generation, and process management.
"""

import os
import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from launcher.database import Game

from launcher.api import DiscordAPIClient, DiscordAPIError
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator, DummyGeneratorError
from launcher.process_manager import ProcessError, ProcessManager


class GameManagerError(Exception):
    """Raised when game manager operation fails."""


class GameManager:
    """High-level interface for game library operations."""

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
        """Sync games from Discord API to local cache.

        Args:
            force: Force sync even if cache is fresh

        Returns:
            Tuple of (was_synced, game_count, skipped_records)
        """
        try:
            was_synced, count, skipped = self.api.sync_cache(force=force)
            if was_synced:
                # Silent path: update blobs and materialize new exes, but
                # never delete files without explicit repair consent.
                self.refresh_library_candidates(drop_superseded=False)
            else:
                stats = self.db.get_cache_stats()
                count = stats["cached_games"]
            return was_synced, count, skipped
        except (DiscordAPIError, sqlite3.Error, OSError) as e:
            raise GameManagerError(f"Failed to sync games: {e}")

    def note_api_version(self, version: str | None) -> str:
        """Record the API version that served the last sync.

        Returns a user-facing notice suffix, non-empty only on a
        transition into or out of fallback (so the UI toasts once per
        change, never on every sync).
        """
        # Local import so tests can patch the candidate list per case.
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
            return f" — back on latest API ({version})"
        if version != newest:
            return f" — using fallback API ({version})"
        return ""

    def search_games(self, query: str, limit: int = 100) -> list["Game"]:
        """Search cached games by name."""
        return self.db.search_games(query, limit)

    def get_all_games(self, limit: int | None = None) -> list["Game"]:
        """Get all cached games."""
        return self.db.get_all_games(limit)

    def get_game(self, game_id: int) -> Optional["Game"]:
        """Get a specific game by ID."""
        return self.db.get_game(game_id)

    def add_to_library(self, game_id: int) -> tuple:
        """Add a game to the user's library.

        This copies the dummy executable template and adds to library.
        Stores ALL executable candidates for smart retry.

        Args:
            game_id: The Discord game ID

        Returns:
            Tuple of (success, message)
        """
        # Check if game exists
        game = self.db.get_game(game_id)
        if not game:
            return False, "Game not found in cache"

        # Check if already in library
        if self.db.is_in_library(game_id):
            return False, "Game is already in library"

        # Check if template is available
        if not self.dummy_gen.is_template_available():
            return False, (
                "DummyGame.exe template not found. "
                "Run 'python templates/build_dummy.py' to build it."
            )

        # Get all Windows executables with smart scoring
        win_executables = self.api.get_best_win32_executables(game.executables)

        if not win_executables:
            return False, "No Windows executable found for this game"

        # Use the best executable for initial setup
        best_exe = win_executables[0]
        process_name = best_exe["name"]

        # NOTE: executable_path keeps the full relative path (e.g.
        # "_retail_/wow.exe") for file creation; process_name stores the
        # normalized filename used for Discord detection.

        # Calculate normalized name (filename only) for Discord detection
        normalized_name = self.api.normalize_process_name(process_name)

        try:
            # Copy dummy executable template (instant operation)
            exe_path, _actual_name = self.dummy_gen.ensure_dummy_for_game(
                game_id=game_id, process_name=process_name
            )

            # Add to library database with ALL executable candidates
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
        """Remove a game from the user's library.

        This stops any running process and removes the dummy executable.

        Args:
            game_id: The Discord game ID

        Returns:
            Tuple of (success, message)
        """
        # Check if in library
        if not self.db.is_in_library(game_id):
            return False, "Game is not in library"

        # Get library entry
        lib_game = self.db.get_library_game(game_id)
        if not lib_game:
            return False, "Failed to get library entry"

        # Stop any running process
        if self.process_mgr.is_running(game_id):
            self.process_mgr.stop_process(game_id)

        # Remove dummy executable (failure is non-fatal; files may be gone already)
        try:
            self.dummy_gen.remove_dummy(game_id, lib_game.process_name)
        except OSError as e:
            if self.logger:
                self.logger.warning(
                    f"Could not remove dummy files for game {game_id}: {e}"
                )

        # Remove from library
        self.db.remove_from_library(game_id)

        if self.logger:
            game = self.db.get_game(game_id)
            game_name = game.name if game else f"Game {game_id}"
            self.logger.game_remove_library(game_name, game_id)

        return True, "Game removed from library"

    def get_library(self) -> list[dict[str, Any]]:
        """Get all games in user's library with status info."""
        library = self.db.get_library()

        # Add running status to each game
        for game in library:
            game["is_running"] = self.process_mgr.is_running(game["game_id"])

        return library

    def is_in_library(self, game_id: int) -> bool:
        """Check if a game is in the library."""
        return self.db.is_in_library(game_id)

    def start_game(self, game_id: int) -> tuple:
        """Start a dummy process for a library game.

        Starts the best stored executable candidate directly: no detection
        step, no waiting. Discord picks up the running process on its own
        scan cycle.

        Args:
            game_id: The Discord game ID

        Returns:
            Tuple of (success, message)
        """
        # Check if in library
        if not self.db.is_in_library(game_id):
            return False, "Game is not in library"

        # Get library entry and game info
        lib_game = self.db.get_library_game(game_id)
        game = self.db.get_game(game_id)

        if not lib_game:
            return False, "Failed to get library entry"

        # Check if already running
        if self.process_mgr.is_running(game_id):
            return False, "Game is already running"

        # Check if we have executable candidates
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
        """Stop a running dummy process.

        Args:
            game_id: The Discord game ID

        Returns:
            Tuple of (success, message)
        """
        if not self.process_mgr.is_running(game_id):
            return False, "Game is not running"

        try:
            if self.process_mgr.stop_process(game_id):
                return True, "Game stopped"
            else:
                return False, "Failed to stop game"
        except Exception as e:  # noqa: BLE001 - report any stop failure to the UI
            return False, f"Error stopping game: {e}"

    def stop_all_games(self) -> int:
        """Stop all running games.

        Returns:
            Number of games stopped
        """
        return self.process_mgr.stop_all_processes()

    def get_running_games(self) -> list[int]:
        """Get list of running game IDs."""
        return self.process_mgr.get_running_games()

    def get_icon_path(self, game_id: int, icon_hash: str) -> Path | None:
        """Get or download game icon.

        Returns:
            Path to icon file or None if unavailable
        """
        return self.api.download_icon(game_id, icon_hash)

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache and library statistics."""
        return self.db.get_cache_stats()

    def startup_cleanup(self, reset_runtime: bool = True) -> dict[str, int]:
        """Reconcile on-disk artifacts with the database.

        Clears stale runtime records, purges dangling library rows, removes
        orphaned game directories, recreates missing dummy executables for
        library entries, and prunes icons for games no longer in the cache.
        Every step is best-effort: failures are logged and counted, never
        raised. Live processes are never touched: dangling purges skip
        running games, and the runtime reset runs at boot only
        (pass reset_runtime=False for on-demand repair).

        Returns:
            Summary counts per cleanup step plus a warnings total.
        """
        summary = {
            "stale_processes": 0,
            "dangling_removed": 0,
            "orphan_dirs_removed": 0,
            "root_exes_removed": 0,
            "exes_recreated": 0,
            "icons_pruned": 0,
            "warnings": 0,
        }

        def warn(message: str) -> None:
            summary["warnings"] += 1
            if self.logger:
                self.logger.warning(message)

        # 1. Runtime records from a previous run are meaningless: drop them
        # without touching OS processes (PIDs may have been recycled).
        # Boot-only: on-demand repair must not orphan live games.
        if reset_runtime:
            try:
                summary["stale_processes"] = self.process_mgr.reset_runtime_state()
            except Exception as e:  # noqa: BLE001 - cleanup must continue
                warn(f"Startup cleanup: could not reset runtime state: {e}")

        try:
            library_ids = self.db.get_library_ids()
            cached_ids = self.db.get_cached_game_ids()
        except (sqlite3.Error, OSError) as e:
            warn(f"Startup cleanup: could not read library/cache ids: {e}")
            return summary

        games_dir = self.dummy_gen.output_dir

        # 2. Purge library rows whose game left the cache. These are
        # invisible in the UI (get_library INNER JOINs the cache) and
        # undeletable there, while blocking re-adds. Guarded: never wipe
        # the library when the cache itself is empty (fresh install).
        if cached_ids:
            dangling = library_ids - cached_ids
            purged: set[int] = set()
            for game_id in sorted(dangling):
                if self.process_mgr.is_running(game_id):
                    warn(
                        f"Startup cleanup: skipping dangling game {game_id}: "
                        f"process running."
                    )
                    continue
                try:
                    game_dir = games_dir / str(game_id)
                    if game_dir.is_dir():
                        shutil.rmtree(game_dir)
                except OSError as e:
                    warn(
                        f"Startup cleanup: could not remove dir for "
                        f"dangling game {game_id}: {e}"
                    )
                try:
                    self.db.remove_from_library(game_id)
                    purged.add(game_id)
                    summary["dangling_removed"] += 1
                except (sqlite3.Error, OSError) as e:
                    warn(
                        f"Startup cleanup: could not purge dangling game {game_id}: {e}"
                    )
            library_ids -= purged

        # 3. Remove game directories with no library entry, plus stray
        # executables directly under games_dir (valid exes live under
        # <game_id>/). A root DummyGame.exe is kept only when it is the
        # resolved template (i.e. no higher-priority template exists).
        # normcase: on Windows the resolved template and the directory
        # entry may differ in case while naming the same file.
        template_norm = os.path.normcase(
            os.path.abspath(self.dummy_gen.template_exe_path)
        )
        try:
            if games_dir.is_dir():
                for child in games_dir.iterdir():
                    if child.is_dir():
                        try:
                            dir_id: int | None = int(child.name)
                        except ValueError:
                            dir_id = None
                        if dir_id is not None and dir_id in library_ids:
                            continue
                        try:
                            shutil.rmtree(child)
                            summary["orphan_dirs_removed"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {child}: {e}")
                    elif child.is_file() and child.suffix.lower() == ".exe":
                        if os.path.normcase(os.path.abspath(child)) == template_norm:
                            continue
                        try:
                            child.unlink()
                            summary["root_exes_removed"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {child}: {e}")
        except OSError as e:
            warn(f"Startup cleanup: could not scan {games_dir}: {e}")

        # 4. Every library entry must have its dummy executable on disk.
        template_missing_logged = False
        for game_id in sorted(library_ids):
            try:
                lib_game = self.db.get_library_game(game_id)
            except (sqlite3.Error, OSError) as e:
                warn(f"Startup cleanup: could not read library game {game_id}: {e}")
                continue
            if lib_game is None:
                continue
            exe_path = (
                Path(lib_game.executable_path) if lib_game.executable_path else None
            )
            if exe_path is not None and exe_path.exists():
                continue
            if not self.dummy_gen.is_template_available():
                if not template_missing_logged:
                    template_missing_logged = True
                    warn(
                        "Startup cleanup: DummyGame.exe template not found, "
                        "missing executables left as-is."
                    )
                continue
            candidate = lib_game.process_name
            if lib_game.executables:
                candidate = lib_game.executables[0].get("name", candidate)
            try:
                new_path, _actual = self.dummy_gen.ensure_dummy_for_game(
                    game_id=game_id, process_name=candidate
                )
            except (DummyGeneratorError, OSError) as e:
                warn(f"Startup cleanup: could not recreate exe for game {game_id}: {e}")
                continue
            # Converge the row onto the recreated file so the next repair
            # is a no-op instead of recreating forever.
            try:
                self.db.add_to_library(
                    game_id,
                    str(new_path),
                    lib_game.process_name,
                    lib_game.normalized_process_name,
                    lib_game.executables,
                )
                summary["exes_recreated"] += 1
            except (sqlite3.Error, OSError) as e:
                warn(f"Startup cleanup: could not update row {game_id}: {e}")

        # 5. Prune icons for games no longer in the cache.
        try:
            icons_dir = self.api.icons_dir
            if icons_dir.is_dir():
                for icon in icons_dir.glob("*.png"):
                    try:
                        icon_id: int | None = int(icon.stem.split("_")[0])
                    except ValueError:
                        icon_id = None
                    if icon_id is not None and icon_id not in cached_ids:
                        try:
                            icon.unlink()
                            summary["icons_pruned"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {icon}: {e}")
        except OSError as e:
            warn(f"Startup cleanup: could not scan icons: {e}")

        if self.logger:
            self.logger.info(f"Startup cleanup: {summary}")
        return summary

    def refresh_library_candidates(
        self, drop_superseded: bool = True
    ) -> dict[str, int]:
        """Refresh stored executable candidates for library games from cache.

        Rewrites the stored candidate blob when Discord's data changed; when
        the best executable changed, materializes the new dummy and drops
        the superseded exe file (unless drop_superseded is False, used by
        the silent sync path — deletions happen on explicit repair only).
        Running games are skipped. Best-effort: failures are logged and
        counted, never raised.
        """
        summary = {
            "refreshed": 0,
            "exes_replaced": 0,
            "skipped_running": 0,
            "no_win_exes": 0,
            "warnings": 0,
        }

        def warn(message: str) -> None:
            summary["warnings"] += 1
            if self.logger:
                self.logger.warning(message)

        try:
            library_ids = self.db.get_library_ids()
        except (sqlite3.Error, OSError) as e:
            warn(f"Refresh: could not read library ids: {e}")
            return summary

        for game_id in sorted(library_ids):
            try:
                game = self.db.get_game(game_id)
                lib_game = self.db.get_library_game(game_id)
            except (sqlite3.Error, OSError) as e:
                warn(f"Refresh: could not read game {game_id}: {e}")
                continue
            if game is None or lib_game is None:
                continue  # Dangling rows belong to the cleanup pass.
            win_exes = self.api.get_best_win32_executables(game.executables)
            if not win_exes:
                summary["no_win_exes"] += 1
                warn(f"Refresh: {game.name} has no Windows executables in cache.")
                continue
            old_names = [e.get("name", "") for e in lib_game.executables]
            new_names = [e.get("name", "") for e in win_exes]
            if old_names == new_names:
                continue
            if self.process_mgr.is_running(game_id):
                summary["skipped_running"] += 1
                continue
            best = win_exes[0]["name"]
            normalized = self.api.normalize_process_name(best)
            old_path = (
                Path(lib_game.executable_path) if lib_game.executable_path else None
            )
            try:
                exe_path, _actual = self.dummy_gen.ensure_dummy_for_game(
                    game_id=game_id, process_name=best
                )
            except (DummyGeneratorError, OSError) as e:
                warn(f"Refresh: could not create exe for game {game_id}: {e}")
                continue
            try:
                self.db.add_to_library(
                    game_id, str(exe_path), normalized, normalized, win_exes
                )
            except (sqlite3.Error, OSError) as e:
                warn(f"Refresh: could not update library row {game_id}: {e}")
                continue
            summary["refreshed"] += 1
            if drop_superseded and old_path is not None and old_path != exe_path:
                try:
                    if old_path.is_file():
                        old_path.unlink()
                        summary["exes_replaced"] += 1
                        self._prune_empty_parents(
                            old_path.parent,
                            self.dummy_gen.output_dir / str(game_id),
                            warn,
                        )
                except OSError as e:
                    warn(f"Refresh: could not drop old exe {old_path}: {e}")

        if self.logger:
            self.logger.info(f"Refresh candidates: {summary}")
        return summary

    @staticmethod
    def _prune_empty_parents(start: Path, stop: Path, warn) -> None:
        """Remove empty directories from start up to (and including) stop."""
        current = start
        while True:
            if current != stop and stop not in current.parents:
                return
            try:
                current.rmdir()  # Only succeeds when empty.
            except OSError:
                return
            if current == stop:
                return
            current = current.parent

    def repair_library(self, startup: bool = False) -> dict[str, int]:
        """Library repair: full cleanup plus candidate refresh.

        Pass startup=True at boot so stale runtime records are also reset;
        on-demand repair leaves runtime tracking untouched.
        """
        summary = self.startup_cleanup(reset_runtime=startup)
        refresh = self.refresh_library_candidates()
        for key, value in refresh.items():
            if key == "warnings":
                summary["warnings"] += value
            else:
                summary[f"refresh_{key}"] = value
        if self.logger:
            self.logger.info(f"Repair library: {summary}")
        return summary

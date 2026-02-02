"""Discord Games Launcher - Game Manager module.

High-level interface for managing game library operations.
Coordinates between database, API, dummy generation, and process management.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from launcher.database import Game

from launcher.database import Database
from launcher.api import DiscordAPIClient
from launcher.dummy_generator import DummyGenerator
from launcher.process_manager import ProcessManager


class GameManagerError(Exception):
    """Raised when game manager operation fails."""

    pass


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
            Tuple of (was_synced, game_count)
        """
        try:
            was_synced = self.api.sync_cache(force=force)
            stats = self.db.get_cache_stats()
            return was_synced, stats["cached_games"]
        except Exception as e:
            raise GameManagerError(f"Failed to sync games: {e}")

    def search_games(self, query: str, limit: int = 100) -> List["Game"]:
        """Search cached games by name."""
        return self.db.search_games(query, limit)

    def get_all_games(self, limit: Optional[int] = None) -> List["Game"]:
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

        # NOTE: Keep full path (e.g., "_retail_/wow.exe") for file creation
        # The DummyGenerator correctly handles subdirectories.
        # Normalization is only needed for Discord detection, not file storage.

        # Calculate normalized name (filename only) for Discord detection
        normalized_name = self.api.normalize_process_name(process_name)

        try:
            # Copy dummy executable template (instant operation)
            exe_path, actual_name = self.dummy_gen.ensure_dummy_for_game(
                game_id=game_id, process_name=process_name
            )

            # Add to library database with ALL executable candidates
            self.db.add_to_library(game_id, str(exe_path), normalized_name, normalized_name, win_executables)

            if self.logger:
                self.logger.game_add_library(game.name, game_id, len(win_executables))

            return True, f"Added {game.name} to library ({len(win_executables)} executable variant(s))"

        except Exception as e:
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

        # Remove dummy executable
        try:
            self.dummy_gen.remove_dummy(game_id, lib_game.process_name)
        except Exception:
            pass  # Continue even if removal fails

        # Remove from library
        self.db.remove_from_library(game_id)

        if self.logger:
            game = self.db.get_game(game_id)
            game_name = game.name if game else f"Game {game_id}"
            self.logger.game_remove_library(game_name, game_id)

        return True, "Game removed from library"

    def get_library(self) -> List[Dict[str, Any]]:
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
        """Start a dummy process for a library game with detection verification.

        This method initiates the detection process. The actual retry logic
        and detection is handled by the ProcessManager in a worker thread.

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

        if self.logger:
            self.logger.game_start_request(game.name if game else f"Game {game_id}", game_id)

        return True, "Starting detection verification..."

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
        except Exception as e:
            return False, f"Error stopping game: {e}"

    def stop_all_games(self) -> int:
        """Stop all running games.

        Returns:
            Number of games stopped
        """
        return self.process_mgr.stop_all_processes()

    def get_running_games(self) -> List[int]:
        """Get list of running game IDs."""
        return self.process_mgr.get_running_games()

    def get_icon_path(self, game_id: int, icon_hash: str) -> Optional[Path]:
        """Get or download game icon.

        Returns:
            Path to icon file or None if unavailable
        """
        return self.api.download_icon(game_id, icon_hash)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache and library statistics."""
        return self.db.get_cache_stats()

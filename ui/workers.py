"""Worker threads for background processing.

This module provides QRunnable-based workers for running PyInstaller compilation
and game addition workflows in background threads to keep the UI responsive.
"""

import sys
import traceback
from typing import Any, Optional, Callable

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    """Signals emitted by worker threads.

    These signals allow the main thread to receive updates from background workers
    without blocking the UI.
    """

    # (game_id, game_name, progress_percent, status_message)
    progress = pyqtSignal(int, str, int, str)

    # (game_id, game_name, success, message, exe_path)
    finished = pyqtSignal(int, str, bool, str, str)

    # (game_id, game_name, error_message, traceback)
    error = pyqtSignal(int, str, str, str)


class GameAdditionWorker(QRunnable):
    """
    Worker for complete game addition workflow.

    Handles the entire process: validation → compilation → database update
    Runs in a background thread via QThreadPool.

    Args:
        game_id: Discord game ID to add
        game_manager: GameManager instance for operations
        progress_callback: Optional callback for progress updates
    """

    def __init__(
        self,
        game_id: int,
        game_manager: Any,
        progress_callback: Optional[Callable] = None,
    ):
        super().__init__()
        self.setAutoDelete(True)
        self.game_id = game_id
        self.game_manager = game_manager
        self.progress_callback = progress_callback
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        """Mark worker for cancellation."""
        self._is_cancelled = True

    @pyqtSlot()
    def run(self):
        """Execute the complete game addition workflow."""
        game = None
        game_name = "Unknown"

        try:
            # Get game info
            game = self.game_manager.get_game(self.game_id)
            if game:
                game_name = game.name

            if not game:
                raise ValueError("Game not found in cache")

            if self._is_cancelled:
                self.signals.finished.emit(
                    self.game_id, game.name, False, "Cancelled", ""
                )
                return

            # Check if already in library
            if self.game_manager.is_in_library(self.game_id):
                self.signals.finished.emit(
                    self.game_id, game.name, False, "Game is already in library", ""
                )
                return

            # Get Windows executable
            exe_config = self.game_manager.api.get_win32_executable(game.executables)
            if not exe_config:
                raise ValueError("No Windows executable found for this game")

            process_name = exe_config["name"]
            normalized_name = self.game_manager.api.normalize_process_name(process_name)

            if self._is_cancelled:
                self.signals.finished.emit(
                    self.game_id, game.name, False, "Cancelled", ""
                )
                return

            # Emit progress - starting compilation
            self.signals.progress.emit(
                self.game_id, game.name, 10, "Generating dummy executable..."
            )

            # Set up progress callback for dummy generator
            def progress_cb(percent, message):
                self.signals.progress.emit(self.game_id, game.name, percent, message)

            self.game_manager.dummy_gen.progress_callback = progress_cb

            # Generate dummy (blocking operation)
            exe_path, actual_name = self.game_manager.dummy_gen.generate_dummy(
                game_id=self.game_id, game_name=game.name, process_name=normalized_name
            )

            # Clear callback
            self.game_manager.dummy_gen.progress_callback = None

            if self._is_cancelled:
                # Clean up generated file if cancelled
                try:
                    self.game_manager.dummy_gen.remove_dummy(self.game_id, actual_name)
                except Exception:
                    pass
                self.signals.finished.emit(
                    self.game_id, game.name, False, "Cancelled", ""
                )
                return

            # Emit progress - adding to library
            self.signals.progress.emit(
                self.game_id, game.name, 90, "Adding to library..."
            )

            # Add to library
            self.game_manager.db.add_to_library(
                self.game_id, str(exe_path), actual_name
            )

            # Success
            self.signals.finished.emit(
                self.game_id,
                game.name,
                True,
                f"Added {game.name} to library",
                str(exe_path),
            )

        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()

            # Log full error for debugging
            print(f"GameAdditionWorker error for game {self.game_id}:", file=sys.stderr)
            print(tb, file=sys.stderr)

            self.signals.error.emit(
                self.game_id, game_name if game_name else "Unknown", error_msg, tb
            )


class BatchGameAdditionWorker(QRunnable):
    """
    Worker for adding multiple games in sequence.

    Processes games one at a time to avoid overwhelming the system,
    but runs in background thread to keep UI responsive.
    """

    def __init__(self, game_ids: list, game_manager: Any):
        super().__init__()
        self.setAutoDelete(True)
        self.game_ids = game_ids
        self.game_manager = game_manager
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._current_game_id = None

    def cancel(self):
        """Mark batch for cancellation."""
        self._is_cancelled = True

    def get_current_game(self) -> Optional[int]:
        """Get the currently processing game ID."""
        return self._current_game_id

    @pyqtSlot()
    def run(self):
        """Process games sequentially."""
        total = len(self.game_ids)

        for i, game_id in enumerate(self.game_ids):
            if self._is_cancelled:
                break

            self._current_game_id = game_id
            game = None
            game_name = "Unknown"

            try:
                game = self.game_manager.get_game(game_id)
                if game:
                    game_name = game.name
                if not game:
                    self.signals.error.emit(
                        game_id, "Unknown", "Game not found in cache", ""
                    )
                    continue

                # Check if already in library
                if self.game_manager.is_in_library(game_id):
                    self.signals.finished.emit(
                        game_id, game.name, False, "Already in library", ""
                    )
                    continue

                # Emit batch progress
                batch_percent = int((i / total) * 100)
                self.signals.progress.emit(
                    game_id,
                    game.name,
                    batch_percent,
                    f"Processing ({i + 1}/{total}): {game.name}...",
                )

                # Get executable info
                exe_config = self.game_manager.api.get_win32_executable(
                    game.executables
                )
                if not exe_config:
                    self.signals.error.emit(
                        game_id, game.name, "No Windows executable found", ""
                    )
                    continue

                process_name = exe_config["name"]
                normalized_name = self.game_manager.api.normalize_process_name(
                    process_name
                )

                # Compile
                self.signals.progress.emit(
                    game_id, game.name, batch_percent + 5, f"Compiling {game.name}..."
                )

                exe_path, actual_name = self.game_manager.dummy_gen.generate_dummy(
                    game_id=game_id, game_name=game.name, process_name=normalized_name
                )

                if self._is_cancelled:
                    try:
                        self.game_manager.dummy_gen.remove_dummy(game_id, actual_name)
                    except Exception:
                        pass
                    break

                # Add to library
                self.signals.progress.emit(
                    game_id,
                    game.name,
                    batch_percent + 90,
                    f"Adding {game.name} to library...",
                )

                self.game_manager.db.add_to_library(game_id, str(exe_path), actual_name)

                self.signals.finished.emit(
                    game_id, game.name, True, f"Added {game.name}", str(exe_path)
                )

            except Exception as e:
                error_msg = str(e)
                tb = traceback.format_exc()

                print(
                    f"BatchGameAdditionWorker error for game {game_id}:",
                    file=sys.stderr,
                )
                print(tb, file=sys.stderr)

                self.signals.error.emit(game_id, game_name, error_msg, tb)

            finally:
                self._current_game_id = None

"""Discord Games Launcher - Process Manager module.

Manages running dummy processes and tracks their PIDs.
Handles process lifecycle, cleanup, and status checking.
"""

import subprocess
import sys
import psutil
import time
from pathlib import Path
from typing import Dict, Optional, List, Any
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from launcher.database import Database


class ProcessError(Exception):
    """Raised when process operation fails."""

    pass


class DetectionWorker(QObject):
    """Worker thread for game detection with Qt signals."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, object, str)

    def __init__(
        self,
        process_manager,
        game_id: int,
        game_name: str,
        executables: List[Dict[str, Any]],
    ):
        super().__init__()
        self.process_manager = process_manager
        self.game_id = game_id
        self.game_name = game_name
        self.executables = executables
        self._should_stop = False

    def run(self):
        """Run the detection and retry logic."""
        try:
            self.progress.emit(f"Starting detection for {self.game_name}...")

            success, exe, message = (
                self.process_manager._verify_and_retry_game_internal(
                    self.game_id,
                    self.game_name,
                    self.executables,
                    self.progress,
                    lambda: self._should_stop,
                )
            )

            self.finished.emit(success, exe, message)
        except Exception as e:
            self.finished.emit(False, None, f"Error: {str(e)}")

    def stop(self):
        """Stop the detection worker."""
        self._should_stop = True


class ProcessManager:
    """Manages lifecycle of dummy game processes."""

    def __init__(self, database: Database, logger=None):
        self.db = database
        self.logger = logger
        self._local_pid_cache: Dict[int, int] = {}
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Refresh local PID cache from database."""
        self._local_pid_cache = self.db.get_running_processes()

    def start_game_with_ui_updates(
        self, game_id: int, game_name: str, executables: List[Dict[str, Any]]
    ) -> tuple:
        """Start a game with UI progress updates via worker thread.

        Args:
            game_id: The Discord game ID
            game_name: Display name of the game
            executables: List of executable candidates to try

        Returns:
            Tuple of (DetectionWorker, QThread)
        """
        thread = QThread()
        worker = DetectionWorker(self, game_id, game_name, executables)
        worker.moveToThread(thread)

        # Connect signals in the proper order for safe cleanup:
        # 1. When thread starts, run the worker
        thread.started.connect(worker.run)
        # 2. When worker finishes, request thread to quit (this is safe)
        worker.finished.connect(thread.quit)
        # 3. When thread actually finishes, schedule deletions
        # IMPORTANT: Use thread.finished for deleteLater, not worker.finished
        # This ensures the thread has actually stopped before deletion
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        return worker, thread

    def _verify_and_retry_game_internal(
        self,
        game_id: int,
        game_name: str,
        executables: List[Dict[str, Any]],
        progress_callback=None,
        should_stop_callback=None,
    ) -> tuple:
        """Internal method to verify game detection with retry logic.

        Args:
            game_id: The Discord game ID
            game_name: Display name of the game
            executables: List of executable candidates to try
            progress_callback: Optional callback for progress updates
            should_stop_callback: Optional callback to check if should stop

        Returns:
            Tuple of (success, executable_data, message)
        """
        if self.logger:
            self.logger.detection_start(game_name, game_id)

        last_pid = None

        for idx, exe in enumerate(executables):
            if should_stop_callback and should_stop_callback():
                return False, None, "Detection cancelled"

            exe_name = exe.get("name", "Unknown")

            if progress_callback:
                progress_callback.emit(
                    f"Trying executable {idx + 1}/{len(executables)}: {exe_name}"
                )

            if self.logger:
                self.logger.retry_attempt(
                    game_name, exe_name, idx + 1, len(executables)
                )

            # Get normalized name for logging/recording (filename only)
            from launcher.api import DiscordAPIClient

            normalized_name = DiscordAPIClient.normalize_process_name(exe_name)

            try:
                # Generate dummy for this executable
                # IMPORTANT: Pass the ORIGINAL exe_name (with path) so the folder
                # structure matches what Discord expects (e.g., "devil may cry 5/devilmaycry5.exe")
                pid = self._start_process_for_executable(game_id, game_name, exe_name)

                last_pid = pid

                if progress_callback:
                    progress_callback.emit(
                        f"Started process (PID: {pid}), waiting for Discord detection..."
                    )

                # Wait for Discord detection (15 seconds)
                detected = self._wait_for_detection(
                    game_id, pid, progress_callback, should_stop_callback
                )

                if detected:
                    if self.logger:
                        self.logger.detection_success(game_name, exe_name, idx + 1)
                        self.logger.record_executable_attempt(
                            game_name, normalized_name, True
                        )

                    # Update preferred executable
                    self.db.record_executable_attempt(
                        game_id, normalized_name, success=True
                    )

                    return (
                        True,
                        exe,
                        (
                            f"Process started successfully with {exe_name}.\n\n"
                            f"The launcher cannot verify if Discord detected the game.\n"
                            f"Check your Discord status to confirm detection.\n\n"
                            f"If not detected, ensure:\n"
                            f"• Discord is running and logged in\n"
                            f"• 'Display current activity' is enabled in Discord settings\n"
                            f"• Wait 30-60 seconds for Discord to scan"
                        ),
                    )

                # Record failure
                if self.logger:
                    self.logger.detection_failed(
                        game_name, exe_name, "Not detected by Discord after 15 seconds"
                    )
                    self.logger.record_executable_attempt(
                        game_name, normalized_name, False
                    )

                self.db.record_executable_attempt(
                    game_id, normalized_name, success=False
                )

                # Stop the failed process
                if last_pid:
                    if self.logger:
                        self.logger.process_stop(
                            game_name, last_pid, "detection_failed"
                        )
                    self.stop_process(game_id)

            except Exception as e:
                error_msg = str(e)
                if self.logger:
                    self.logger.detection_failed(game_name, exe_name, error_msg)
                    self.logger.record_executable_attempt(
                        game_name, normalized_name, False
                    )

                self.db.record_executable_attempt(
                    game_id, normalized_name, success=False
                )

                if last_pid:
                    self.stop_process(game_id)

        # All executables failed
        if self.logger:
            self.logger.all_executables_failed(game_name, len(executables))

        if last_pid:
            # Keep the last process running as specified
            if self.logger:
                self.logger.info(
                    f"Keeping last process running for {game_name} (PID: {last_pid})"
                )
        else:
            # Try starting the last executable again to keep it running
            if executables:
                last_exe = executables[-1]
                last_exe_name = last_exe.get("name", "Unknown")

                try:
                    # Use original exe name (with path) for correct folder structure
                    last_pid = self._start_process_for_executable(
                        game_id, game_name, last_exe_name
                    )
                    if self.logger:
                        self.logger.info(
                            f"Started fallback process for {game_name} (PID: {last_pid})"
                        )
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to start fallback process: {str(e)}")

        return (
            False,
            None,
            (
                f"Process is running, but detection verification timed out after trying {len(executables)} executable(s).\n\n"
                f"The game process is still active. Discord may still detect it.\n\n"
                f"Tips:\n"
                f"• Check Discord status in 30-60 seconds\n"
                f"• Ensure 'Display current activity' is enabled in Discord settings\n"
                f"• Try running Discord as Administrator\n"
                f"• Restart Discord if still not detected"
            ),
        )

    def _start_process_for_executable(
        self, game_id: int, game_name: str, process_name: str
    ) -> int:
        """Start a process with the given executable name.

        Args:
            game_id: The Discord game ID
            game_name: Display name of the game
            process_name: Process name for the dummy executable (normalized filename)

        Returns:
            The process PID
        """
        from launcher.dummy_generator import DummyGenerator
        from platformdirs import user_data_dir

        games_dir = (
            Path(user_data_dir("discord-games-launcher", appauthor=False)) / "games"
        )
        dummy_gen = DummyGenerator(games_dir)

        # Ensure dummy executable exists
        exe_path, actual_name = dummy_gen.ensure_dummy_for_game(game_id, process_name)

        # Start the process
        if not exe_path.exists():
            raise ProcessError(f"Executable not found: {exe_path}")

        # Check if already running
        if self.is_running(game_id):
            pid = self._local_pid_cache[game_id]
            if self._verify_game_process(game_id, pid):
                return pid
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]

        # Working directory is the exe's parent directory
        working_dir = exe_path.parent

        # Start process with game name as argument
        creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0

        process = subprocess.Popen(
            [str(exe_path), game_name],
            cwd=str(working_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        pid = process.pid

        # Verify process started
        time.sleep(0.3)
        if not self._pid_exists(pid):
            raise ProcessError("Process failed to start")

        # Store in database and cache
        self.db.set_process_running(game_id, pid)
        self._local_pid_cache[game_id] = pid

        if self.logger:
            self.logger.process_start(game_name, str(exe_path), pid)
            self.logger.record_executable_attempt(game_name, process_name, True)

        return pid

    def _wait_for_detection(
        self, game_id: int, pid: int, progress_callback=None, should_stop_callback=None
    ) -> bool:
        """Wait for Discord to detect the game (15 seconds).

        Args:
            game_id: The Discord game ID
            pid: Process PID
            progress_callback: Optional callback for progress updates
            should_stop_callback: Optional callback to check if should stop

        Returns:
            True if detection verified (simulated), False otherwise
        """
        timeout = 15  # 15 seconds
        check_interval = 3  # Check every 3 seconds
        elapsed = 0

        while elapsed < timeout:
            if should_stop_callback and should_stop_callback():
                return False

            time.sleep(check_interval)
            elapsed += check_interval

            # Verify process is still running
            if not self._pid_exists(pid):
                if self.logger:
                    self.logger.warning(f"Process {pid} died during detection wait")
                return False

            # Update progress
            remaining = timeout - elapsed
            if progress_callback:
                progress_callback.emit(
                    f"Waiting for Discord detection... {remaining}s remaining"
                )

        # After 15 seconds, we assume Discord should have detected it
        # In a real implementation, you might verify via Discord's local IPC
        # For now, we return True as we've waited a full scan cycle
        return True

    def start_process(
        self, game_id: int, exe_path: Path, game_name: str = "Game"
    ) -> int:
        """Start a dummy process for a game.

        Args:
            game_id: The Discord game ID
            exe_path: Path to the dummy executable
            game_name: Display name to pass to the dummy process

        Returns:
            The process PID

        Raises:
            ProcessError: If process fails to start
        """
        if not exe_path.exists():
            raise ProcessError(f"Executable not found: {exe_path}")

        # Check if already running with system verification
        if self.is_running(game_id):
            pid = self._local_pid_cache[game_id]
            # Verify the process is actually our game
            if self._verify_game_process(game_id, pid):
                return pid
            # Stale entry, clean it up
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]

        try:
            # Working directory is the exe's parent directory
            working_dir = exe_path.parent

            # Start process with game name as argument
            # Use CREATE_NEW_CONSOLE on Windows for proper GUI behavior
            creationflags = (
                subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )

            process = subprocess.Popen(
                [str(exe_path), game_name],
                cwd=str(working_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )

            pid = process.pid

            # Verify process started
            time.sleep(0.3)
            if not self._pid_exists(pid):
                raise ProcessError("Process failed to start")

            # Store in database and cache
            self.db.set_process_running(game_id, pid)
            self._local_pid_cache[game_id] = pid

            if self.logger:
                self.logger.process_start(game_name, str(exe_path), pid)

            return pid

        except Exception as e:
            raise ProcessError(f"Failed to start process: {e}")

    def stop_process(self, game_id: int) -> bool:
        """Stop a running dummy process.

        Args:
            game_id: The Discord game ID

        Returns:
            True if stopped successfully, False if not running
        """
        if not self.is_running(game_id):
            return False

        pid = self._local_pid_cache[game_id]

        try:
            # Try to terminate the process
            if self._kill_process(pid):
                # Update database
                self.db.set_process_stopped(game_id)
                del self._local_pid_cache[game_id]

                if self.logger:
                    self.logger.process_stop(f"Game {game_id}", pid, "user_stop")

                return True
            return False

        except Exception:
            return False

    def _kill_process(self, pid: int) -> bool:
        """Kill a process by PID and all its children.

        Returns:
            True if killed successfully or already dead
        """
        try:
            parent = psutil.Process(pid)

            # Get all child processes recursively
            children = parent.children(recursive=True)

            # Terminate all children first
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            # Wait for children to terminate
            gone, alive = psutil.wait_procs(children, timeout=3)

            # Force kill any remaining children
            for child in alive:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass

            # Now terminate the parent
            parent.terminate()

            # Wait for parent to terminate
            try:
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                parent.kill()
                parent.wait(timeout=1)

            return True

        except psutil.NoSuchProcess:
            # Process already dead
            return True
        except Exception:
            return False

    def is_running(self, game_id: int) -> bool:
        """Check if a process is actually running for this game.

        This checks both the database record and verifies the process exists.
        """
        if game_id not in self._local_pid_cache:
            return False

        pid = self._local_pid_cache[game_id]

        # Verify process actually exists
        if not self._pid_exists(pid):
            # Clean up stale record
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]
            return False

        return True

    def _pid_exists(self, pid: int) -> bool:
        """Check if a process with given PID exists."""
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    def get_running_games(self) -> List[int]:
        """Get list of game IDs with running processes.

        This performs cleanup of stale records.
        """
        self._cleanup_stale_records()
        return list(self._local_pid_cache.keys())

    def _cleanup_stale_records(self) -> None:
        """Remove database records for processes that are no longer running."""
        stale_games: List[int] = []

        for game_id, pid in list(self._local_pid_cache.items()):
            if not self._pid_exists(pid):
                stale_games.append(game_id)

        for game_id in stale_games:
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]

    def stop_all_processes(self) -> int:
        """Stop all running dummy processes.

        Returns:
            Number of processes stopped
        """
        count = 0
        for game_id in list(self._local_pid_cache.keys()):
            if self.stop_process(game_id):
                count += 1
        return count

    def get_process_info(self, game_id: int) -> Optional[Dict]:
        """Get information about a running process.

        Returns:
            Dict with process info or None if not running
        """
        if not self.is_running(game_id):
            return None

        pid = self._local_pid_cache[game_id]

        try:
            process = psutil.Process(pid)
            return {
                "pid": pid,
                "name": process.name(),
                "status": process.status(),
                "create_time": process.create_time(),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "memory_info": process.memory_info()._asdict(),
            }
        except psutil.NoSuchProcess:
            return None

    def _verify_game_process(self, game_id: int, pid: int) -> bool:
        """Verify that a running process matches the expected game.

        Args:
            game_id: The Discord game ID
            pid: Process ID to verify

        Returns:
            True if process is valid, False otherwise
        """
        try:
            process = psutil.Process(pid)
            # Get the executable path
            exe_path = process.exe()
            # Check if it's in the game's directory
            expected_dir = str(game_id)
            return expected_dir in exe_path
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def force_cleanup_all(self) -> None:
        """Force cleanup of all process records (use on app exit)."""
        # Try to stop all tracked processes
        self.stop_all_processes()

        # Clear any remaining database records
        running = self.db.get_running_processes()
        for game_id in running:
            self.db.set_process_stopped(game_id)

        self._local_pid_cache.clear()

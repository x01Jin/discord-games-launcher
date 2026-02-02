"""Discord Games Launcher - Process Manager module.

Manages running dummy processes and tracks their PIDs.
Handles process lifecycle, cleanup, and status checking.
"""

import subprocess
import psutil
from pathlib import Path
from typing import Dict, Optional, List
from launcher.database import Database


class ProcessError(Exception):
    """Raised when process operation fails."""

    pass


class ProcessManager:
    """Manages lifecycle of dummy game processes."""

    def __init__(self, database: Database):
        self.db = database
        self._local_pid_cache: Dict[int, int] = {}  # game_id -> pid
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Refresh local PID cache from database."""
        self._local_pid_cache = self.db.get_running_processes()

    def start_process(self, game_id: int, exe_path: Path) -> int:
        """Start a dummy process for a game.

        Args:
            game_id: The Discord game ID
            exe_path: Path to the dummy executable

        Returns:
            The process PID

        Raises:
            ProcessError: If process fails to start
        """
        if not exe_path.exists():
            raise ProcessError(f"Executable not found: {exe_path}")

        # Check if already running
        if self.is_running(game_id):
            return self._local_pid_cache[game_id]

        try:
            # Start process without console window
            process = subprocess.Popen(
                [str(exe_path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            pid = process.pid

            # Store in database and cache
            self.db.set_process_running(game_id, pid)
            self._local_pid_cache[game_id] = pid

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
                return True
            return False

        except Exception:
            return False

    def _kill_process(self, pid: int) -> bool:
        """Kill a process by PID.

        Returns:
            True if killed successfully or already dead
        """
        try:
            process = psutil.Process(pid)
            process.terminate()

            # Wait for process to terminate
            try:
                process.wait(timeout=3)
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                process.kill()
                process.wait(timeout=1)

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

    def force_cleanup_all(self) -> None:
        """Force cleanup of all process records (use on app exit)."""
        # Try to stop all tracked processes
        self.stop_all_processes()

        # Clear any remaining database records
        running = self.db.get_running_processes()
        for game_id in running:
            self.db.set_process_stopped(game_id)

        self._local_pid_cache.clear()


import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil

from launcher.database import Database
from launcher.dummy_generator import DummyGenerator


class ProcessError(Exception):
    pass


class ProcessManager:

    def __init__(
        self,
        database: Database,
        dummy_generator: DummyGenerator,
        logger=None,
    ):
        self.db = database
        self.dummy_gen = dummy_generator
        self.logger = logger
        self._local_pid_cache: dict[int, int] = {}
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        self._local_pid_cache = self.db.get_running_processes()

    def start_process(
        self, game_id: int, exe_path: Path, game_name: str = "Game"
    ) -> int:
        if not exe_path.exists():
            raise ProcessError(f"Executable not found: {exe_path}")

        if self.is_running(game_id):
            pid = self._local_pid_cache[game_id]
            if self._verify_game_process(game_id, pid):
                return pid
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]

        try:
            working_dir = exe_path.parent

            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 7
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                [str(exe_path), game_name],
                cwd=str(working_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )

            pid = process.pid

            time.sleep(0.3)
            if not self._pid_exists(pid):
                raise ProcessError("Process failed to start")

            self.db.set_process_running(game_id, pid)
            self._local_pid_cache[game_id] = pid

            if self.logger:
                self.logger.process_start(game_name, str(exe_path), pid)

            return pid

        except (OSError, sqlite3.Error, psutil.Error) as e:
            raise ProcessError(f"Failed to start process: {e}") from e

    def stop_process(self, game_id: int) -> bool:
        if not self.is_running(game_id):
            return False

        pid = self._local_pid_cache[game_id]

        try:
            if self._kill_process(pid):
                self.db.set_process_stopped(game_id)
                self._local_pid_cache.pop(game_id, None)

                if self.logger:
                    self.logger.process_stop(f"Game {game_id}", pid, "user_stop")

                return True
            return False

        except (psutil.Error, OSError, sqlite3.Error):
            return False

    def _kill_process(self, pid: int) -> bool:
        try:
            parent = psutil.Process(pid)

            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            _gone, alive = psutil.wait_procs(children, timeout=3)

            for child in alive:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass

            parent.terminate()

            try:
                parent.wait(timeout=3)
            except psutil.TimeoutExpired:
                parent.kill()
                parent.wait(timeout=1)

            return True

        except psutil.NoSuchProcess:
            return True
        except (psutil.Error, OSError):
            return False

    def is_running(self, game_id: int) -> bool:
        if game_id not in self._local_pid_cache:
            return False

        pid = self._local_pid_cache[game_id]

        if not self._pid_exists(pid):
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]
            return False

        return True

    def _pid_exists(self, pid: int) -> bool:
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    def get_running_games(self) -> list[int]:
        self._cleanup_stale_records()
        return list(self._local_pid_cache.keys())

    def _cleanup_stale_records(self) -> None:
        stale_games: list[int] = []

        for game_id, pid in list(self._local_pid_cache.items()):
            if not self._pid_exists(pid):
                stale_games.append(game_id)

        for game_id in stale_games:
            self.db.set_process_stopped(game_id)
            del self._local_pid_cache[game_id]

    def stop_all_processes(self) -> int:
        count = 0
        for game_id in list(self._local_pid_cache.keys()):
            if self.stop_process(game_id):
                count += 1
        return count

    def _verify_game_process(self, game_id: int, pid: int) -> bool:
        try:
            process = psutil.Process(pid)
            exe_path = process.exe()
            return str(game_id) in Path(exe_path).parts
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def force_cleanup_all(self) -> None:
        self.stop_all_processes()

        running = self.db.get_running_processes()
        for game_id in running:
            self.db.set_process_stopped(game_id)

        self._local_pid_cache.clear()

    def reset_runtime_state(self) -> int:
        running = self.db.get_running_processes()
        for game_id in running:
            try:
                self.db.set_process_stopped(game_id)
            except (sqlite3.Error, OSError) as e:
                if self.logger:
                    self.logger.warning(
                        f"Could not clear runtime record for game {game_id}: {e}"
                    )
                continue
        self._local_pid_cache.clear()
        return len(running)

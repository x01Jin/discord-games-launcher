import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_data_dir

from launcher import __version__


class GameLauncherLogger:
    def __init__(self):
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger("discord-games-launcher")
        self.logger.setLevel(logging.DEBUG)

        self.logger.handlers.clear()

        app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
        logs_dir = app_data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        log_file = (
            logs_dir
            / f"dcgl_{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')}.log"
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.log_file = log_file

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)

    def app_start(self):
        self.info("=" * 50)

        self.info(f"Discord Games Launcher v{__version__} starting")
        self.info("=" * 50)

    def app_exit(self):
        self.info("=" * 50)
        self.info("Discord Games Launcher shutting down")
        self.info("=" * 50)

    def database_recreate(self):
        self.warning("Database schema invalid - recreating database")

    def process_start(self, game_name: str, exe_path: str, pid: int):
        self.info(f"Process started: {game_name} from {exe_path} (PID: {pid})")

    def process_stop(self, game_name: str, pid: int, reason: str = "user_stop"):
        self.info(f"Process stopped: {game_name} (PID: {pid}, reason: {reason})")

    def process_kill(self, game_name: str, pid: int):
        self.warning(f"Process killed: {game_name} (PID: {pid})")

    def database_operation(self, operation: str, table: str, details: str = ""):
        self.debug(f"DB: {operation} on {table}" + (f" - {details}" if details else ""))

    def record_executable_attempt(self, game_name: str, exe_name: str, success: bool):
        result = "SUCCESS" if success else "FAILURE"
        self.debug(f"History recorded for {game_name}: {exe_name} - {result}")

    def game_add_library(self, game_name: str, game_id: int, exe_count: int):
        self.info(
            f"Game added to library: {game_name} (ID: {game_id}, {exe_count} executables)"
        )

    def game_remove_library(self, game_name: str, game_id: int):
        self.info(f"Game removed from library: {game_name} (ID: {game_id})")

    def game_start_request(self, game_name: str, game_id: int):
        self.info(f"Game start requested: {game_name} (ID: {game_id})")

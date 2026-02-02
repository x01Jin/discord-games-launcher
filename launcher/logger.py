"""Discord Games Launcher - Logger module.

Centralized logging system with file rotation.
All messages are logged to files in %APPDATA%/discord-games-launcher/logs/
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from platformdirs import user_data_dir


class GameLauncherLogger:
    """Centralized logger for Discord Games Launcher."""

    def __init__(self):
        """Initialize the logger with file rotation."""
        self._setup_logger()

    def _setup_logger(self):
        """Setup logger with rotating file handler."""
        # Create logger
        self.logger = logging.getLogger("discord-games-launcher")
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Get logs directory
        app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
        logs_dir = app_data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler (10MB per file, 5 files = 50MB max)
        log_file = logs_dir / f"dcgl_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.log_file = log_file

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)

    # Game detection specific methods

    def detection_start(self, game_name: str, game_id: int):
        """Log start of game detection."""
        self.info(f"Detection started for: {game_name} (ID: {game_id})")

    def detection_success(self, game_name: str, exe_name: str, attempt: int):
        """Log successful detection."""
        self.info(f"Detection SUCCESS for {game_name}: {exe_name} (attempt {attempt})")

    def detection_failed(self, game_name: str, exe_name: str, reason: str):
        """Log failed detection attempt."""
        self.warning(f"Detection FAILED for {game_name} with {exe_name}: {reason}")

    def all_executables_failed(self, game_name: str, total_attempts: int):
        """Log when all executables failed."""
        self.error(f"All executables FAILED for {game_name} after {total_attempts} attempts")

    def retry_attempt(self, game_name: str, exe_name: str, attempt_num: int, total: int):
        """Log retry attempt."""
        self.info(f"Retry {attempt_num}/{total} for {game_name}: trying {exe_name}")

    # Application lifecycle methods

    def app_start(self):
        """Log application start."""
        self.info("=" * 50)
        self.info("Discord Games Launcher starting")
        self.info("=" * 50)

    def app_exit(self):
        """Log application exit."""
        self.info("=" * 50)
        self.info("Discord Games Launcher shutting down")
        self.info("=" * 50)

    def database_recreate(self):
        """Log database recreation."""
        self.warning("Database schema invalid - recreating database")

    # Process management methods

    def process_start(self, game_name: str, exe_path: str, pid: int):
        """Log process start."""
        self.info(f"Process started: {game_name} from {exe_path} (PID: {pid})")

    def process_stop(self, game_name: str, pid: int, reason: str = "user_stop"):
        """Log process stop."""
        self.info(f"Process stopped: {game_name} (PID: {pid}, reason: {reason})")

    def process_kill(self, game_name: str, pid: int):
        """Log forced process kill."""
        self.warning(f"Process killed: {game_name} (PID: {pid})")

    # Database methods

    def database_operation(self, operation: str, table: str, details: str = ""):
        """Log database operation."""
        self.debug(f"DB: {operation} on {table}" + (f" - {details}" if details else ""))

    def record_executable_attempt(self, game_name: str, exe_name: str, success: bool):
        """Log executable history recording."""
        result = "SUCCESS" if success else "FAILURE"
        self.debug(f"History recorded for {game_name}: {exe_name} - {result}")

    # Game management methods

    def game_add_library(self, game_name: str, game_id: int, exe_count: int):
        """Log game added to library."""
        self.info(f"Game added to library: {game_name} (ID: {game_id}, {exe_count} executables)")

    def game_remove_library(self, game_name: str, game_id: int):
        """Log game removed from library."""
        self.info(f"Game removed from library: {game_name} (ID: {game_id})")

    def game_start_request(self, game_name: str, game_id: int):
        """Log game start request."""
        self.info(f"Game start requested: {game_name} (ID: {game_id})")

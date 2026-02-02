#!/usr/bin/env python3
"""Discord Games Launcher - Main Entry Point

A Windows tool to browse Discord's supported games database and create
dummy processes for Discord's "Playing [Game]" status display.

Usage:
    python main.py

Features:
    - Browse 3000+ Discord-supported games
    - Search and filter game database
    - Add games to personal library
    - Generate dummy executables for Discord detection
    - Run multiple games simultaneously
    - Dark theme interface
"""

import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from platformdirs import user_data_dir  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtGui import QFont, QFontDatabase  # noqa: E402

from launcher.logger import GameLauncherLogger  # noqa: E402
from launcher.database import Database  # noqa: E402
from launcher.api import DiscordAPIClient  # noqa: E402
from launcher.dummy_generator import DummyGenerator  # noqa: E402
from launcher.process_manager import ProcessManager  # noqa: E402
from launcher.game_manager import GameManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


def setup_application():
    """Initialize and configure the Qt application."""
    # Enable high DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Discord Games Launcher")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("discord-games-launcher")

    # Set application font
    font = QFont("Segoe UI", 10)
    # Check if Segoe UI is available
    available_families = QFontDatabase.families()
    if "Segoe UI" not in available_families:
        font = QFont("Arial", 10)
    app.setFont(font)

    return app


def initialize_components():
    """Initialize all backend components."""
    # Setup data directories
    app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
    db_path = app_data_dir / "launcher.db"
    cache_dir = app_data_dir / "cache"
    games_dir = app_data_dir / "games"

    # Create directories
    app_data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    games_dir.mkdir(parents=True, exist_ok=True)

    print(f"Data directory: {app_data_dir}")
    print(f"Database: {db_path}")
    print(f"Games directory: {games_dir}")

    # Initialize logger first
    logger = GameLauncherLogger()
    logger.app_start()

    # Initialize components with logger
    database = Database(db_path, logger=logger)
    api_client = DiscordAPIClient(database, cache_dir)
    dummy_generator = DummyGenerator(games_dir)
    process_manager = ProcessManager(database, logger=logger)
    game_manager = GameManager(
        database=database,
        api_client=api_client,
        dummy_generator=dummy_generator,
        process_manager=process_manager,
        logger=logger,
    )

    return game_manager, logger


def main():
    """Main application entry point."""
    print("Discord Games Launcher v1.0.0")
    print("=" * 40)

    game_manager = None
    logger = None

    try:
        # Initialize Qt application
        app = setup_application()

        # Initialize backend components
        print("Initializing components...")
        game_manager, logger = initialize_components()

        # Create and show main window
        print("Loading UI...")
        window = MainWindow(game_manager)
        window.show()

        print("Ready!")
        print()

        # Run application
        sys.exit(app.exec())

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()

        if logger:
            logger.critical(f"Fatal error: {e}")

        sys.exit(1)
    finally:
        # Cleanup all processes before exit
        if game_manager:
            game_manager.process_mgr.force_cleanup_all()

        # Log application exit
        if logger:
            logger.app_exit()


if __name__ == "__main__":
    main()

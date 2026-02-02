#!/usr/bin/env python3
"""
Dummy Game for Discord Games Launcher.

This is a minimal GUI window that displays the game name passed as argument.
The process name matches what Discord expects, and the window shows
that Discord should detect it as "Playing [Game Name]".

Usage:
    dummy_game.exe "Game Name"

This template is compiled once into DummyGame.exe and then COPIED
and RENAMED for each game (matching the expected process name).
"""

import sys
from datetime import datetime

# Check if PyQt6 is available
try:
    from PyQt6.QtWidgets import (
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QLabel,
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont

    HAS_GUI = True

    class DummyGameWindow(QMainWindow):
        """Simple window showing game name for Discord detection."""

        def __init__(self, game_name: str):
            super().__init__()
            self.game_name = game_name
            self.start_time = datetime.now()
            self._setup_ui()
            self._setup_timer()

        def _setup_ui(self):
            """Setup the minimal game window UI."""
            self.setWindowTitle(self.game_name)
            self.setMinimumSize(480, 280)
            self.resize(480, 280)

            # Apply dark title bar on Windows
            try:
                import ctypes

                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(ctypes.c_int(1)),
                    ctypes.sizeof(ctypes.c_int()),
                )
            except Exception:
                pass  # Fallback on non-Windows or if API unavailable

            # Dark theme colors
            dark_bg = "#1e1e1e"
            text_color = "#cccccc"

            # Central widget
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)

            # Set dark theme
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {dark_bg};
                }}
                QWidget {{
                    background-color: {dark_bg};
                    color: {text_color};
                }}
                QLabel {{
                    background-color: transparent;
                }}
            """)

            # Game name label
            self.name_label = QLabel(f"{self.game_name}")
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
            self.name_label.setFont(name_font)
            layout.addWidget(self.name_label)

            # Subtitle
            subtitle = QLabel("Game Started!")
            subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle.setStyleSheet(
                "color: #4ade80; font-size: 12px; font-weight: bold;"
            )
            layout.addWidget(subtitle)

            # Info message
            info_message = QLabel(
                "This window helps Discord detect the game.\n\n"
                "IMPORTANT: This app cannot verify Discord detection!\n"
                "Check your Discord profile to see if status appears.\n\n"
                'If Discord doesn\'t show "Playing" status:\n'
                "\u2022 Ensure 'Display current activity' is ON in Discord settings\n"
                "\u2022 Run Discord as Administrator\n"
                "\u2022 Wait 30-60 seconds for Discord to scan processes\n"
                "\u2022 Restart Discord if still not detected"
            )
            info_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_message.setStyleSheet("color: #888; font-size: 9px; line-height: 1.4;")
            info_message.setWordWrap(True)
            layout.addWidget(info_message)

            layout.addStretch()

            # Runtime label
            self.runtime_label = QLabel("Runtime: 0:00:00")
            self.runtime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.runtime_label.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(self.runtime_label)

        def _setup_timer(self):
            """Setup timer to update runtime display."""
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_runtime)
            self.timer.start(1000)  # Update every second

        def _update_runtime(self):
            """Update runtime display."""
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.runtime_label.setText(f"Runtime: {hours}:{minutes:02d}:{seconds:02d}")

except ImportError:
    HAS_GUI = False


def main():
    """Main entry point."""
    # Get game name from command line argument
    game_name = sys.argv[1] if len(sys.argv) > 1 else "Game"

    if not HAS_GUI:
        # Fallback: just keep process alive without GUI
        print(f"Running as: {game_name} (no GUI)")
        import time

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    # Create Qt application
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName(game_name)

    # Create and show window
    window = DummyGameWindow(game_name)
    window.show()

    # Run
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

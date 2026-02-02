#!/usr/bin/env python3
"""
GUI Dummy Game for Discord Games Launcher.

This executable creates a visible window to better trigger Discord's game detection.
Includes a status panel with game information and troubleshooting help.
"""

import sys
from pathlib import Path
from datetime import datetime

# Check if PyQt6 is available (bundled with executable)
try:
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSystemTrayIcon,
        QMenu,
        QStyle,
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QFont, QAction

    HAS_GUI = True
except ImportError:
    HAS_GUI = False


# These are set during template generation
GAME_ID = "$game_id$"  # noqa: F841
GAME_NAME = "$game_name$"  # noqa: F841
PROCESS_NAME = "$process_name$"  # noqa: F841


class SignalHelper(QObject):  # type: ignore[name, base]
    """Helper class for emitting signals from timer."""
    update_signal = pyqtSignal()  # type: ignore


class GameWindow(QMainWindow):  # type: ignore[name, base]
    """
    Minimal game window with status panel.

    Features:
    - Visible window for Discord detection
    - Status panel with runtime and Discord status
    - System tray minimization
    - Troubleshooting tips
    """

    def __init__(self):
        super().__init__()
        assert HAS_GUI
        self.game_id = GAME_ID
        self.game_name = GAME_NAME
        self.process_name = PROCESS_NAME
        self.start_time = datetime.now()
        self.signal_helper = SignalHelper()

        self._setup_ui()
        self._setup_timer()
        self._setup_tray()
        self._write_pid_file()

    def _setup_ui(self):
        """Setup the minimal game window UI."""
        self.setWindowTitle(self.game_name)
        self.setMinimumSize(400, 350)
        self.resize(450, 400)

        # Dark theme colors
        dark_bg = "#1e1e1e"
        darker_bg = "#252526"
        accent_color = "#007acc"
        text_color = "#cccccc"
        border_color = "#3e3e42"
        success_color = "#4ec9b0"
        _ = success_color

        # Central widget
        central = QWidget()  # type: ignore
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)  # type: ignore
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
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)

        # Game icon placeholder (just a styled box)
        icon_container = QWidget()  # type: ignore
        icon_container.setFixedSize(80, 80)
        icon_container.setStyleSheet(f"""
            background-color: {darker_bg};
            border: 2px dashed {border_color};
            border-radius: 8px;
        """)
        icon_layout = QVBoxLayout(icon_container)  # type: ignore
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel("🎮")  # type: ignore
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        icon_label.setStyleSheet("font-size: 32px;")
        icon_layout.addWidget(icon_label)

        icon_wrapper = QHBoxLayout()  # type: ignore
        icon_wrapper.addStretch()
        icon_wrapper.addWidget(icon_container)
        icon_wrapper.addStretch()
        layout.addLayout(icon_wrapper)

        # Game name
        name_label = QLabel(self.game_name)  # type: ignore
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        name_font = QFont("Segoe UI", 14)  # type: ignore
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {text_color};")
        layout.addWidget(name_label)

        # Status Panel
        status_panel = QWidget()  # type: ignore
        status_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {darker_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 11px;
                padding: 2px 0px;
            }}
        """)
        status_layout = QVBoxLayout(status_panel)  # type: ignore
        status_layout.setContentsMargins(15, 12, 15, 12)
        status_layout.setSpacing(8)

        # Status header
        status_header = QLabel("📊 Game Status")  # type: ignore
        status_header.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {accent_color};
            padding-bottom: 5px;
            border-bottom: 1px solid {border_color};
        """)
        status_layout.addWidget(status_header)

        # Process info
        self.process_label = QLabel(f"🔧 Process: {self.process_name}")  # type: ignore
        status_layout.addWidget(self.process_label)

        # Runtime
        self.runtime_label = QLabel("⏱️  Runtime: 00:00:00")  # type: ignore
        status_layout.addWidget(self.runtime_label)

        # Discord status
        self.discord_label = QLabel("📡 Discord: Waiting for detection...")  # type: ignore
        self.discord_label.setStyleSheet("color: #ff9800;")
        status_layout.addWidget(self.discord_label)

        layout.addWidget(status_panel)

        # Troubleshooting Panel
        help_panel = QWidget()  # type: ignore
        help_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {darker_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QLabel {{
                color: #888;
                font-size: 10px;
                padding: 2px 0px;
            }}
        """)
        help_layout = QVBoxLayout(help_panel)  # type: ignore
        help_layout.setContentsMargins(15, 10, 15, 10)
        help_layout.setSpacing(4)

        help_header = QLabel("ℹ️  Troubleshooting")  # type: ignore
        help_header.setStyleSheet(f"""
            font-size: 11px;
            font-weight: bold;
            color: {text_color};
        """)
        help_layout.addWidget(help_header)

        help_text = QLabel(  # type: ignore
            "• If Discord doesn't detect the game, try:<br>"
            "  - Running Discord as Administrator<br>"
            "  - Enabling 'Display current activity' in Discord settings<br>"
            "  - Restarting Discord"
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)

        layout.addWidget(help_panel)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close Game")  # type: ignore
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #005a9e;
            }}
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Center window
        screen = QApplication.primaryScreen()  # type: ignore
        if screen:
            center = screen.availableGeometry().center()
            self.move(center.x() - 225, center.y() - 200)

    def _setup_timer(self):
        """Setup timer for updating runtime display."""
        self.signal_helper.update_signal.connect(self._update_runtime)

        self.timer = QTimer()  # type: ignore
        self.timer.timeout.connect(self._update_runtime)
        self.timer.start(1000)  # Update every second

        # Update Discord status after 30 seconds (typical detection time)
        QTimer.singleShot(30000, self._update_discord_status)  # type: ignore

    def _update_runtime(self):
        """Update the runtime display."""
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.runtime_label.setText(
            f"⏱️  Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}"
        )

    def _update_discord_status(self):
        """Update Discord detection status."""
        self.discord_label.setText("📡 Discord: Should be detected by now")
        self.discord_label.setStyleSheet("color: #4ec9b0;")

    def _setup_tray(self):
        """Setup system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():  # type: ignore
            return

        self.tray_icon = QSystemTrayIcon(self)  # type: ignore  # type: ignore
        self.tray_icon.setToolTip(f"{self.game_name} - Running")

        # Use application icon or default
        style = self.style()
        if style:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)  # type: ignore
            if icon:
                self.tray_icon.setIcon(icon)

        # Tray menu
        tray_menu = QMenu()  # type: ignore

        show_action = QAction("Show", self)  # type: ignore
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Close Game", self)  # type: ignore
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:  # type: ignore[name]
            self.show()
            self.raise_()
            self.activateWindow()

    def _write_pid_file(self):
        """Write PID file for tracking."""
        try:
            pid_file = Path(__file__).parent / ".pid"
            pid_file.write_text(str(QApplication.applicationPid()))  # type: ignore
        except Exception:
            pass

    def _cleanup_pid_file(self):
        """Remove PID file on exit."""
        try:
            pid_file = Path(__file__).parent / ".pid"
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass

    def closeEvent(self, a0):  # type: ignore
        """Handle window close."""
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()

        self._cleanup_pid_file()

        a0.accept()  # type: ignore


def fallback_main():
    """Fallback when GUI is not available - runs as background process."""
    import time
    from pathlib import Path
    import os

    # Write PID file
    try:
        pid_file = Path(__file__).parent / ".pid"
        pid_file.write_text(str(os.getpid()))
    except Exception:
        pass

    # Keep process alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            pid_file = Path(__file__).parent / ".pid"
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass


def main():
    """Main entry point."""
    if not HAS_GUI:
        # Fallback to background process if PyQt6 not available
        fallback_main()
        return

    app = QApplication(sys.argv)  # type: ignore
    app.setApplicationName(GAME_NAME)
    app.setApplicationVersion("1.0.0")

    # Enable high DPI
    app.setStyle("Fusion")

    window = GameWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

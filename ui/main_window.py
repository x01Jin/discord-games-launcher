"""Discord Games Launcher - UI Main Window module.

Main application window with dark theme styling.
Manages the tab interface and application lifecycle.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QStatusBar,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from launcher.game_manager import GameManager
from ui.browser_tab import BrowserTab
from ui.library_tab import LibraryTab


# Dark theme colors
DARK_BG = "#1e1e1e"
DARKER_BG = "#252526"
ACCENT_COLOR = "#007acc"
TEXT_COLOR = "#cccccc"
BORDER_COLOR = "#3e3e42"


class MainWindow(QMainWindow):
    """Main application window for Discord Games Launcher."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self._setup_ui()
        self._apply_dark_theme()
        self._setup_timers()

    def _setup_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle("Discord Games Launcher")
        self.setMinimumSize(1000, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Browser tab
        self.browser_tab = BrowserTab(self.game_manager)
        self.tabs.addTab(self.browser_tab, "Browse Games")

        # Library tab
        self.library_tab = LibraryTab(self.game_manager)
        self.tabs.addTab(self.library_tab, "My Library")

        # Connect tab change to refresh
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _create_header(self) -> QWidget:
        """Create the header widget with title and sync button."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Discord Games Launcher")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {TEXT_COLOR};")
        layout.addWidget(title)

        layout.addStretch()

        # Sync button
        self.sync_btn = QPushButton("Sync Games")
        self.sync_btn.setToolTip("Sync game database from Discord API")
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        layout.addWidget(self.sync_btn)

        # Stats button
        stats_btn = QPushButton("Stats")
        stats_btn.setToolTip("View cache statistics")
        stats_btn.clicked.connect(self._show_stats)
        layout.addWidget(stats_btn)

        return header

    def _apply_dark_theme(self):
        """Apply dark theme stylesheet."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {DARK_BG};
            }}
            
            QWidget {{
                background-color: {DARK_BG};
                color: {TEXT_COLOR};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }}
            
            QTabWidget::pane {{
                border: 1px solid {BORDER_COLOR};
                background-color: {DARKER_BG};
                border-radius: 4px;
            }}
            
            QTabBar::tab {{
                background-color: {DARK_BG};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-bottom: none;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {DARKER_BG};
                border-bottom: 2px solid {ACCENT_COLOR};
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {BORDER_COLOR};
            }}
            
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: #005a9e;
            }}
            
            QPushButton:pressed {{
                background-color: #004578;
            }}
            
            QPushButton:disabled {{
                background-color: {BORDER_COLOR};
                color: #666;
            }}
            
            QLineEdit {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                padding: 6px;
                border-radius: 4px;
                color: {TEXT_COLOR};
            }}
            
            QLineEdit:focus {{
                border: 1px solid {ACCENT_COLOR};
            }}
            
            QScrollArea {{
                border: none;
                background-color: {DARKER_BG};
            }}
            
            QScrollBar:vertical {{
                background-color: {DARK_BG};
                width: 12px;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {BORDER_COLOR};
                border-radius: 6px;
                min-height: 30px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QStatusBar {{
                background-color: {ACCENT_COLOR};
                color: white;
            }}
            
            QLabel {{
                color: {TEXT_COLOR};
            }}
            
            QMessageBox {{
                background-color: {DARK_BG};
            }}
            
            QMessageBox QLabel {{
                color: {TEXT_COLOR};
            }}
            
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
        """)

    def _setup_timers(self):
        """Setup periodic refresh timers."""
        # Refresh running status every 5 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_status)
        self.refresh_timer.start(5000)

    def _on_sync_clicked(self):
        """Handle sync button click."""
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing...")
        self.status_bar.showMessage("Syncing games from Discord API...")

        try:
            was_synced, count = self.game_manager.sync_games(force=True)
            if was_synced:
                self.status_bar.showMessage(f"Synced {count} games from Discord API")
                self.browser_tab.refresh_games()
            else:
                self.status_bar.showMessage("Cache is up to date")
        except Exception as e:
            QMessageBox.critical(self, "Sync Failed", f"Failed to sync games: {e}")
            self.status_bar.showMessage("Sync failed")
        finally:
            self.sync_btn.setEnabled(True)
            self.sync_btn.setText("Sync Games")

    def _show_stats(self):
        """Show cache statistics."""
        stats = self.game_manager.get_cache_stats()

        msg = QMessageBox(self)
        msg.setWindowTitle("Cache Statistics")
        msg.setText("<h3>Discord Games Launcher Statistics</h3>")
        msg.setInformativeText(f"""
            <table style='margin: 10px;'>
                <tr><td><b>Cached Games:</b></td><td>{stats["cached_games"]:,}</td></tr>
                <tr><td><b>Library Games:</b></td><td>{stats["library_games"]}</td></tr>
                <tr><td><b>Running Processes:</b></td><td>{stats["running_processes"]}</td></tr>
            </table>
        """)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        if index == 1:  # Library tab
            self.library_tab.refresh_library()

    def _refresh_status(self):
        """Periodic refresh of running status."""
        self.library_tab.update_running_status()
        self._update_status_bar()

    def _update_status_bar(self):
        """Update status bar with current stats."""
        stats = self.game_manager.get_cache_stats()
        running = len(self.game_manager.get_running_games())
        self.status_bar.showMessage(
            f"Cached: {stats['cached_games']:,} | Library: {stats['library_games']} | Running: {running}"
        )

    def closeEvent(self, a0):
        """Handle window close event.
        
        Parameter name 'a0' matches PyQt6 type stub signature.
        """
        # Stop all running processes on exit
        running = self.game_manager.stop_all_games()
        if running > 0:
            self.status_bar.showMessage(f"Stopped {running} games")

        if a0 is not None:
            a0.accept()

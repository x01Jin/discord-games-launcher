"""Discord Games Launcher - Library Tab UI module.

Tab for managing user's game library with proper list view.
Shows added games with start/stop controls in a clean list format.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QMenu,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from launcher.game_manager import GameManager


# Dark theme colors (consistent with main window)
DARK_BG = "#1e1e1e"
DARKER_BG = "#252526"
ACCENT_COLOR = "#007acc"
TEXT_COLOR = "#cccccc"
BORDER_COLOR = "#3e3e42"
SUCCESS_COLOR = "#4ec9b0"
ERROR_COLOR = "#f44336"


class LibraryTab(QWidget):
    """Tab for managing user's game library with list view."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self._setup_ui()
        self.refresh_library()

    def _setup_ui(self):
        """Setup the library tab UI with proper list view."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("My Library")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {TEXT_COLOR};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Stop all button
        stop_all_btn = QPushButton("Stop All")
        stop_all_btn.setToolTip("Stop all running games")
        stop_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        stop_all_btn.clicked.connect(self._stop_all_games)
        header_layout.addWidget(stop_all_btn)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_library)
        header_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # Info label
        self.info_label = QLabel(
            "No games in library. Browse the game list and add games."
        )
        self.info_label.setStyleSheet("color: #888; padding: 10px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # Library list widget
        self.library_list = QListWidget()
        self.library_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.library_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                outline: none;
                padding: 5px;
            }}
            QListWidget::item {{
                background-color: {DARK_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 10px;
                margin: 2px 0px;
                min-height: 50px;
            }}
            QListWidget::item:selected {{
                background-color: #2a2d2e;
                border: 1px solid {ACCENT_COLOR};
            }}
            QListWidget::item:hover {{
                background-color: #2a2d2e;
            }}
        """)
        self.library_list.setSpacing(5)
        self.library_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.library_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.library_list)

        # Status bar at bottom
        self.status_label = QLabel("0 games in library")
        self.status_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.status_label)

    def refresh_library(self):
        """Refresh the library display."""
        # Clear existing items
        self.library_list.clear()

        # Get library
        library = self.game_manager.get_library()

        if not library:
            self.info_label.show()
            self.info_label.setText(
                "No games in library. Browse the game list and add games."
            )
            self.status_label.setText("0 games in library")
            return

        self.info_label.hide()

        # Add games to list
        for game_data in library:
            item = self._create_library_item(game_data)
            self.library_list.addItem(item)

        self.status_label.setText(f"{len(library)} game(s) in library")

    def _create_library_item(self, game_data: dict) -> QListWidgetItem:
        """Create a list item for a library game with PyQt6 widgets."""
        game_id = game_data["game_id"]
        name = game_data["name"]
        is_running = game_data.get("is_running", False)
        process_name = game_data["process_name"]

        # Create list item
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, game_id)
        item.setSizeHint(QSize(0, 60))

        # Create widget container for rich display
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Left side: Name and process
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_COLOR};")
        name_font = QFont("Segoe UI", 10)
        name_font.setBold(True)
        name_label.setFont(name_font)
        
        process_label = QLabel(process_name)
        process_label.setStyleSheet("font-size: 9px; color: #666;")
        
        left_layout.addWidget(name_label)
        left_layout.addWidget(process_label)
        left_layout.addStretch()
        
        layout.addLayout(left_layout, 70)

        # Right side: Status
        status_text = "Running" if is_running else "Stopped"
        status_color = SUCCESS_COLOR if is_running else "#888"
        
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"font-size: 10px; color: {status_color}; font-weight: bold;")
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(status_label, 30)

        # Add item to list and set widget
        self.library_list.addItem(item)
        self.library_list.setItemWidget(item, widget)
        
        return item

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click on a library item - toggle start/stop."""
        game_id = item.data(Qt.ItemDataRole.UserRole)
        is_running = self.game_manager.process_mgr.is_running(game_id)

        if is_running:
            self._stop_game(game_id)
        else:
            self._start_game(game_id)

    def _show_context_menu(self, position):
        """Show context menu for selected item."""
        item = self.library_list.itemAt(position)
        if not item:
            return

        game_id = item.data(Qt.ItemDataRole.UserRole)
        game_data = self._get_game_data(game_id)

        if not game_data:
            return

        is_running = self.game_manager.process_mgr.is_running(game_id)

        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {DARK_BG};
                border: 1px solid {BORDER_COLOR};
                color: {TEXT_COLOR};
            }}
            QMenu::item {{
                padding: 5px 20px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT_COLOR};
            }}
        """)

        # Add actions
        if is_running:
            stop_action = menu.addAction("Stop Game")
            if stop_action:
                stop_action.triggered.connect(lambda: self._stop_game(game_id))
        else:
            start_action = menu.addAction("Start Game")
            if start_action:
                start_action.triggered.connect(lambda: self._start_game(game_id))

        menu.addSeparator()

        remove_action = menu.addAction("Remove from Library")
        if remove_action:
            remove_action.triggered.connect(lambda: self._remove_game(game_id))

        # Show menu
        menu.exec(self.library_list.mapToGlobal(position))

    def _get_game_data(self, game_id: int) -> dict | None:
        """Get game data by ID from library."""
        library = self.game_manager.get_library()
        for game in library:
            if game["game_id"] == game_id:
                return game
        return None

    def _start_game(self, game_id: int):
        """Start a game with GUI window."""
        success, message = self.game_manager.start_game(game_id)

        if success:
            self.refresh_library()
            # Show info about GUI window
            game_data = self._get_game_data(game_id)
            game_name = game_data['name'] if game_data else 'Game'
            
            QMessageBox.information(
                self,
                "Game Started",
                f"{game_name} is now running with a GUI window.\n\n"
                "The window helps Discord detect the game. If Discord doesn't show \"Playing\" status:\n"
                "• Run Discord as Administrator\n"
                "• Enable \"Display current activity\" in Discord settings\n"
                "• Wait 30-60 seconds for Discord to detect\n"
                "• Restart Discord if still not detected"
            )
        else:
            QMessageBox.warning(self, "Failed to Start", message)

    def _stop_game(self, game_id: int):
        """Stop a game."""
        success, message = self.game_manager.stop_game(game_id)

        if success:
            self.refresh_library()
        else:
            QMessageBox.warning(self, "Error", message)

    def _remove_game(self, game_id: int):
        """Remove a game from library with confirmation."""
        game_data = self._get_game_data(game_id)
        if not game_data:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{game_data['name']}' from library?\n\n"
            "This will stop the game if running and delete all associated files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.game_manager.remove_from_library(game_id)

            if success:
                self.refresh_library()
            else:
                QMessageBox.warning(self, "Error", message)

    def _stop_all_games(self):
        """Stop all running games."""
        count = self.game_manager.stop_all_games()

        if count > 0:
            self.refresh_library()
            QMessageBox.information(self, "Stopped", f"Stopped {count} game(s)")
        else:
            QMessageBox.information(
                self, "No Games Running", "No games are currently running"
            )

    def update_running_status(self):
        """Update running status of all items (called periodically)."""
        self.refresh_library()

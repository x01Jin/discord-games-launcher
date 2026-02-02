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
from PyQt6.QtCore import Qt, QSize, QTimer
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
        self.detection_worker = None
        self.detection_thread = None
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
        name_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {TEXT_COLOR};"
        )
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
        status_label.setStyleSheet(
            f"font-size: 10px; color: {status_color}; font-weight: bold;"
        )
        status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
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
        """Start a game with detection verification via worker thread."""
        # Check if detection is already in progress
        if self.detection_thread is not None and self.detection_thread.isRunning():
            QMessageBox.warning(
                self,
                "Detection in Progress",
                "Another game detection is in progress. Please wait for it to complete.",
            )
            return

        # Clear any stale references from previous completed detections
        self.detection_worker = None
        self.detection_thread = None

        # Initiate game start
        success, message = self.game_manager.start_game(game_id)

        if not success:
            QMessageBox.warning(self, "Failed to Start", message)
            return

        # Get library game info for executables
        lib_game = self.game_manager.db.get_library_game(game_id)
        if not lib_game or not lib_game.executables:
            QMessageBox.warning(
                self,
                "No Executables",
                "No executable candidates found. Try removing and re-adding the game.",
            )
            return

        # Get game name
        game = self.game_manager.get_game(game_id)
        game_name = game.name if game else f"Game {game_id}"

        # Update UI to show detection in progress
        self.status_label.setText(message)

        # Start detection worker
        worker, thread = self.game_manager.process_mgr.start_game_with_ui_updates(
            game_id, game_name, lib_game.executables
        )

        # Connect signals
        worker.progress.connect(self._on_detection_progress)
        worker.finished.connect(
            lambda s, e, m: self._on_detection_finished(game_id, s, e, m)
        )

        # Store references
        self.detection_worker = worker
        self.detection_thread = thread

        # Start thread
        thread.start()

    def _on_detection_progress(self, message: str):
        """Handle detection progress updates."""
        self.status_label.setText(message)

    def _on_detection_finished(
        self, game_id: int, success: bool, exe: dict, message: str
    ):
        """Handle detection completion."""
        # DO NOT clear references here - they will be auto-deleted via deleteLater
        # connected to thread.finished signal. Clearing here causes crash because
        # the Python GC may destroy the thread while Qt is still cleaning up.
        # The references will be cleared when starting a new detection or in cleanup()

        # Refresh library to update running status
        self.refresh_library()

        # Clear references after event loop processes cleanup
        def cleanup_refs():
            # Now it's safe to clear the references after Qt has processed deleteLater
            self.detection_worker = None
            self.detection_thread = None

        # Use longer delay to ensure thread cleanup is complete
        QTimer.singleShot(200, cleanup_refs)

    def _stop_game(self, game_id: int):
        """Stop a game."""
        # Stop any ongoing detection
        if self.detection_worker is not None:
            self.detection_worker.stop()

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

    def cleanup(self):
        """Cleanup resources when tab is destroyed."""
        # Stop any ongoing detection first
        if self.detection_worker is not None:
            self.detection_worker.stop()

        if self.detection_thread is not None:
            if self.detection_thread.isRunning():
                # Request thread to quit gracefully
                self.detection_thread.quit()
                # Wait up to 2 seconds for thread to finish
                # This is blocking but necessary on app close
                if not self.detection_thread.wait(2000):
                    # Force terminate if still running
                    self.detection_thread.terminate()
                    self.detection_thread.wait(500)

        # Only clear references after thread has stopped
        self.detection_worker = None
        self.detection_thread = None

"""Discord Games Launcher - Library Tab UI module.

Tab for managing user's game library.
Shows added games with start/stop controls.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QPushButton,
    QLabel,
    QMessageBox,
    QFrame,
    QGridLayout,
)
from PyQt6.QtCore import Qt
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


class LibraryGameCard(QFrame):
    """Card widget for a game in the library."""

    def __init__(self, game_data: dict, game_manager: GameManager, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.game_manager = game_manager
        self.game_id = game_data["game_id"]
        self.is_running = game_data.get("is_running", False)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the library game card UI."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            LibraryGameCard {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header with name and status
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Game name
        name_label = QLabel(self.game_data["name"])
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {TEXT_COLOR};")
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        # Status indicator
        self.status_label = QLabel()
        self._update_status_display()
        header_layout.addWidget(self.status_label)

        layout.addWidget(header)

        # Process name
        process_label = QLabel(f"Process: {self.game_data['process_name']}")
        process_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(process_label)

        # Executable path (truncated)
        exe_path = self.game_data.get("executable_path", "")
        if exe_path:
            display_path = exe_path if len(exe_path) < 50 else f"...{exe_path[-47:]}"
            path_label = QLabel(f"Path: {display_path}")
            path_label.setStyleSheet("color: #666; font-size: 8pt;")
            path_label.setWordWrap(True)
            layout.addWidget(path_label)

        layout.addStretch()

        # Buttons
        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Start/Stop button
        self.action_btn = QPushButton()
        self._update_action_button()
        self.action_btn.clicked.connect(self._on_action_clicked)
        buttons_layout.addWidget(self.action_btn)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        remove_btn.clicked.connect(self._on_remove_clicked)
        buttons_layout.addWidget(remove_btn)

        layout.addWidget(buttons)

    def _update_status_display(self):
        """Update the status label."""
        if self.is_running:
            self.status_label.setText("Running")
            self.status_label.setStyleSheet(f"""
                color: {SUCCESS_COLOR};
                font-weight: bold;
                padding: 2px 8px;
                background-color: {DARK_BG};
                border-radius: 4px;
            """)
        else:
            self.status_label.setText("Stopped")
            self.status_label.setStyleSheet(f"""
                color: #888;
                padding: 2px 8px;
                background-color: {DARK_BG};
                border-radius: 4px;
            """)

    def _update_action_button(self):
        """Update the action button state."""
        if self.is_running:
            self.action_btn.setText("Stop")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ERROR_COLOR};
                }}
                QPushButton:hover {{
                    background-color: #d32f2f;
                }}
            """)
        else:
            self.action_btn.setText("Start")
            self.action_btn.setStyleSheet("")  # Use default style

    def _on_action_clicked(self):
        """Handle start/stop button click."""
        if self.is_running:
            # Stop the game
            success, message = self.game_manager.stop_game(self.game_id)
            if success:
                self.is_running = False
                self._update_status_display()
                self._update_action_button()
            else:
                QMessageBox.warning(self, "Error", message)
        else:
            # Start the game
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Starting...")

            success, message = self.game_manager.start_game(self.game_id)

            if success:
                self.is_running = True
                self._update_status_display()
                self._update_action_button()
            else:
                QMessageBox.warning(self, "Failed to Start", message)

            self.action_btn.setEnabled(True)

    def _on_remove_clicked(self):
        """Handle remove button click."""
        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{self.game_data['name']}' from library?\n\n"
            "This will stop the game if running and delete the dummy executable.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.game_manager.remove_from_library(self.game_id)

            if success:
                # Hide this card (will be refreshed on next load)
                self.hide()
                # Notify parent to refresh
                parent = self.parent()
                while parent is not None:
                    refresh_method = getattr(parent, "refresh_library", None)
                    if callable(refresh_method):
                        refresh_method()
                        break
                    # type: ignore[attr-defined]
                    parent = parent.parent()
            else:
                QMessageBox.warning(self, "Error", message)

    def update_running_status(self):
        """Update the running status from game manager."""
        new_status = self.game_manager.get_running_games()
        should_be_running = self.game_id in new_status

        if should_be_running != self.is_running:
            self.is_running = should_be_running
            self._update_status_display()
            self._update_action_button()


class LibraryTab(QWidget):
    """Tab for managing user's game library."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self.library_cards = []
        self._setup_ui()
        self.refresh_library()

    def _setup_ui(self):
        """Setup the library tab UI."""
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

        # Scroll area for library cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none;")

        # Container for library cards
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

    def refresh_library(self):
        """Refresh the library display."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        self.library_cards.clear()

        # Get library
        library = self.game_manager.get_library()

        if not library:
            self.info_label.show()
            self.info_label.setText(
                "No games in library. Browse the game list and add games."
            )
            return

        self.info_label.hide()

        # Create cards
        columns = 2
        for i, game_data in enumerate(library):
            card = LibraryGameCard(game_data, self.game_manager)
            self.library_cards.append(card)

            row = i // columns
            col = i % columns
            self.cards_layout.addWidget(card, row, col)

        self.info_label.setText(f"{len(library)} game(s) in library")
        self.info_label.show()

    def update_running_status(self):
        """Update running status of all cards."""
        for card in self.library_cards:
            card.update_running_status()

    def _stop_all_games(self):
        """Stop all running games."""
        count = self.game_manager.stop_all_games()

        if count > 0:
            # Update all cards
            self.update_running_status()
            QMessageBox.information(self, "Stopped", f"Stopped {count} game(s)")
        else:
            QMessageBox.information(
                self, "No Games Running", "No games are currently running"
            )

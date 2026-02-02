"""Discord Games Launcher - Browser Tab UI module.

Tab for browsing and searching Discord's game database.
Allows adding games to library.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QScrollArea, QGridLayout, QPushButton, QLabel,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from launcher.game_manager import GameManager
from launcher.database import Game


# Dark theme colors (consistent with main window)
DARK_BG = "#1e1e1e"
DARKER_BG = "#252526"
ACCENT_COLOR = "#007acc"
TEXT_COLOR = "#cccccc"
BORDER_COLOR = "#3e3e42"
SUCCESS_COLOR = "#4ec9b0"


class GameCard(QFrame):
    """Card widget displaying a single game."""
    
    def __init__(self, game: Game, game_manager: GameManager, parent=None):
        super().__init__(parent)
        self.game = game
        self.game_manager = game_manager
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the game card UI."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            GameCard {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 10px;
            }}
            GameCard:hover {{
                border: 1px solid {ACCENT_COLOR};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Game name
        name_label = QLabel(self.game.name)
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setWordWrap(True)
        name_label.setStyleSheet(f"color: {TEXT_COLOR};")
        layout.addWidget(name_label)
        
        # Aliases (if any)
        if self.game.aliases:
            aliases_text = ", ".join(self.game.aliases[:3])  # Show first 3
            aliases_label = QLabel(f"Also known as: {aliases_text}")
            aliases_label.setStyleSheet("color: #888; font-size: 9pt;")
            aliases_label.setWordWrap(True)
            layout.addWidget(aliases_label)
        
        # Executables info
        win_exes = [exe for exe in self.game.executables if exe.get('os') == 'win32']
        if win_exes:
            exe_names = [exe.get('name', 'Unknown') for exe in win_exes[:2]]
            exe_label = QLabel(f"Executables: {', '.join(exe_names)}")
            exe_label.setStyleSheet("color: #888; font-size: 8pt;")
            exe_label.setWordWrap(True)
            layout.addWidget(exe_label)
        
        layout.addStretch()
        
        # Add button
        self.add_btn = QPushButton("Add to Library")
        self.add_btn.setEnabled(not self.game_manager.is_in_library(self.game.id))
        if not self.add_btn.isEnabled():
            self.add_btn.setText("In Library")
        self.add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_btn)
    
    def _on_add_clicked(self):
        """Handle add to library button click."""
        self.add_btn.setEnabled(False)
        self.add_btn.setText("Adding...")
        
        success, message = self.game_manager.add_to_library(self.game.id)
        
        if success:
            self.add_btn.setText("In Library")
            self.add_btn.setStyleSheet(f"background-color: {SUCCESS_COLOR};")
        else:
            self.add_btn.setEnabled(True)
            self.add_btn.setText("Add to Library")
            QMessageBox.warning(self, "Failed", message)


class BrowserTab(QWidget):
    """Tab for browsing and searching games."""
    
    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self.all_games = []
        self._setup_ui()
        self._load_initial_games()
    
    def _setup_ui(self):
        """Setup the browser tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Search bar
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search games...")
        self.search_input.setMinimumWidth(300)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)
        
        search_layout.addStretch()
        
        # Results count
        self.results_label = QLabel("Loading games...")
        self.results_label.setStyleSheet("color: #888;")
        search_layout.addWidget(self.results_label)
        
        layout.addLayout(search_layout)
        
        # Scroll area for game cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none;")
        
        # Container for game cards
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)
    
    def _load_initial_games(self):
        """Load initial set of games."""
        # Check if we need to sync
        try:
            was_synced, count = self.game_manager.sync_games(force=False)
            if was_synced:
                self.results_label.setText(f"Synced {count:,} games from Discord")
            else:
                stats = self.game_manager.get_cache_stats()
                self.results_label.setText(f"Using cached data ({stats['cached_games']:,} games)")
        except Exception as e:
            self.results_label.setText(f"Cache error: {e}")
        
        # Load games
        self.all_games = self.game_manager.get_all_games(limit=100)
        self._display_games(self.all_games)
    
    def _display_games(self, games: list):
        """Display game cards in the grid."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        if not games:
            # Show no results message
            no_results = QLabel("No games found. Try syncing or adjusting your search.")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.setStyleSheet("color: #888; padding: 50px;")
            self.cards_layout.addWidget(no_results, 0, 0)
            return
        
        # Calculate columns based on width
        columns = 3  # Default
        
        # Add game cards
        for i, game in enumerate(games):
            card = GameCard(game, self.game_manager)
            row = i // columns
            col = i % columns
            self.cards_layout.addWidget(card, row, col)
        
        # Update results label
        self.results_label.setText(f"Showing {len(games)} games")
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        if not text:
            self._display_games(self.all_games)
            return
        
        # Search games
        results = self.game_manager.search_games(text, limit=50)
        self._display_games(results)
    
    def refresh_games(self):
        """Refresh the game list after sync."""
        self.all_games = self.game_manager.get_all_games(limit=100)
        
        # Re-apply current search if any
        search_text = self.search_input.text()
        if search_text:
            results = self.game_manager.search_games(search_text, limit=50)
            self._display_games(results)
        else:
            self._display_games(self.all_games)

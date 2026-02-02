"""Discord Games Launcher - Browser Tab UI module.

Tab for browsing and searching Discord's game database with proper tree view.
Allows adding games to library asynchronously with queue display.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QAbstractItemView,
    QHeaderView,
    QMenu,
)
from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QFont, QBrush, QColor

from launcher.game_manager import GameManager
from launcher.database import Game
from ui.workers import GameAdditionWorker
from ui.queue_widget import CompilationQueueWidget


# Dark theme colors (consistent with main window)
DARK_BG = "#1e1e1e"
DARKER_BG = "#252526"
ACCENT_COLOR = "#007acc"
TEXT_COLOR = "#cccccc"
BORDER_COLOR = "#3e3e42"
SUCCESS_COLOR = "#4ec9b0"


class BrowserTab(QWidget):
    """Tab for browsing and searching games with tree view."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self.all_games = []

        # Setup thread pool with max 2 workers for compilation
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)

        # Create compilation queue widget
        self.queue_widget = CompilationQueueWidget()
        self.queue_widget.item_cancelled.connect(self._on_item_cancelled)

        # Track active workers
        self.active_workers: dict = {}

        self._setup_ui()
        self._load_initial_games()

    def _setup_ui(self):
        """Setup the browser tab UI with tree view."""
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

        # Tree widget for games
        self.games_tree = QTreeWidget()
        self.games_tree.setHeaderLabels(["Game", "Executables", "Status"])
        self.games_tree.setColumnWidth(0, 300)
        self.games_tree.setColumnWidth(1, 200)
        self.games_tree.setColumnWidth(2, 100)
        self.games_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.games_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                outline: none;
                padding: 5px;
            }}
            QTreeWidget::item {{
                background-color: {DARK_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
                margin: 2px 0px;
                min-height: 40px;
            }}
            QTreeWidget::item:selected {{
                background-color: #2a2d2e;
                border: 1px solid {ACCENT_COLOR};
            }}
            QTreeWidget::item:hover {{
                background-color: #2a2d2e;
            }}
            QHeaderView::section {{
                background-color: {DARKER_BG};
                color: {TEXT_COLOR};
                padding: 8px;
                border: 1px solid {BORDER_COLOR};
                font-weight: bold;
            }}
        """)
        self.games_tree.setAlternatingRowColors(False)
        header = self.games_tree.header()
        if header:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.games_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.games_tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.games_tree)

        # Bottom buttons
        buttons_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Selected to Library")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._add_selected_games)
        buttons_layout.addWidget(self.add_btn)

        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

        # Connect selection change
        self.games_tree.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_initial_games(self):
        """Load initial set of games."""
        # Check if we need to sync
        try:
            was_synced, count = self.game_manager.sync_games(force=False)
            if was_synced:
                self.results_label.setText(f"Synced {count:,} games from Discord")
            else:
                stats = self.game_manager.get_cache_stats()
                self.results_label.setText(
                    f"Using cached data ({stats['cached_games']:,} games)"
                )
        except Exception as e:
            self.results_label.setText(f"Cache error: {e}")

        # Load games
        self.all_games = self.game_manager.get_all_games(limit=100)
        self._display_games(self.all_games)

    def _display_games(self, games: list):
        """Display games in the tree widget."""
        # Clear existing items
        self.games_tree.clear()

        if not games:
            # Show no results message as a single item
            item = QTreeWidgetItem(self.games_tree)
            item.setText(0, "No games found. Try syncing or adjusting your search.")
            item.setDisabled(True)
            self.results_label.setText("0 games found")
            return

        # Get library games for status
        library_ids = {g["game_id"] for g in self.game_manager.get_library()}

        # Add game items
        for game in games:
            item = self._create_game_item(game, game.id in library_ids)
            self.games_tree.addTopLevelItem(item)

        # Update results label
        self.results_label.setText(f"Showing {len(games)} games")

    def _create_game_item(self, game: Game, in_library: bool) -> QTreeWidgetItem:
        """Create a tree item for a game."""
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, game.id)

        # Game name (column 0)
        name_text = game.name
        if game.aliases:
            aliases_text = ", ".join(game.aliases[:2])
            name_text = f"{game.name}\nAlso known as: {aliases_text}"
        item.setText(0, name_text)
        item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))

        # Executables (column 1)
        win_exes = [exe for exe in game.executables if exe.get("os") == "win32"]
        if win_exes:
            exe_names = [exe.get("name", "Unknown") for exe in win_exes[:2]]
            exe_text = "\n".join(exe_names)
            if len(win_exes) > 2:
                exe_text += f"\n+{len(win_exes) - 2} more"
            item.setText(1, exe_text)
        else:
            item.setText(1, "No Windows executable")
            item.setForeground(1, QBrush(QColor("#888")))

        # Status (column 2)
        if in_library:
            item.setText(2, "In Library")
            item.setForeground(2, QBrush(QColor(SUCCESS_COLOR)))
        else:
            item.setText(2, "Available")
            item.setForeground(2, QBrush(QColor(TEXT_COLOR)))

        return item

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        if not text:
            self._display_games(self.all_games)
            return

        # Search games
        results = self.game_manager.search_games(text, limit=50)
        self._display_games(results)

    def _on_selection_changed(self):
        """Handle selection change to enable/disable add button."""
        selected_items = self.games_tree.selectedItems()
        has_selection = len(selected_items) > 0

        # Check if any selected items are already in library
        can_add = False
        for item in selected_items:
            game_id = item.data(0, Qt.ItemDataRole.UserRole)
            if game_id and not self.game_manager.is_in_library(game_id):
                can_add = True
                break

        self.add_btn.setEnabled(has_selection and can_add)

    def _show_context_menu(self, position):
        """Show context menu for selected item."""
        item = self.games_tree.itemAt(position)
        if not item:
            return

        game_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not game_id:
            return

        in_library = self.game_manager.is_in_library(game_id)

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

        if in_library:
            action = menu.addAction("Already in Library (disabled)")
            if action:
                action.setEnabled(False)
        else:
            action = menu.addAction("Add to Library")
            if action:
                action.triggered.connect(lambda: self._add_game(game_id))

        # Show menu
        menu.exec(self.games_tree.mapToGlobal(position))

    def _add_game(self, game_id: int):
        """Add a single game to library asynchronously."""
        # Check if already in queue
        if self.queue_widget.is_game_in_queue(game_id):
            QMessageBox.information(
                self, "Already Queued", "This game is already in the compilation queue."
            )
            return

        # Get game info
        game = self.game_manager.get_game(game_id)
        if not game:
            QMessageBox.warning(self, "Error", "Game not found")
            return

        # Add to queue widget
        self.queue_widget.add_item(game_id, game.name)

        # Create and start worker
        worker = GameAdditionWorker(game_id, self.game_manager)
        worker.signals.progress.connect(
            lambda gid, name, pct, msg: self._on_compilation_progress(
                gid, name, pct, msg
            )
        )
        worker.signals.finished.connect(
            lambda gid, name, success, msg, path: self._on_compilation_finished(
                gid, name, success, msg
            )
        )
        worker.signals.error.connect(
            lambda gid, name, err, tb: self._on_compilation_error(gid, name, err)
        )

        self.active_workers[game_id] = worker
        self.queue_widget.register_worker(game_id, worker)
        self.thread_pool.start(worker)

        # Show queue widget if not visible
        if not self.queue_widget.isVisible():
            self.queue_widget.show()
            self._center_queue_widget()

    def _add_selected_games(self):
        """Add all selected games to library asynchronously."""
        selected_items = self.games_tree.selectedItems()
        queued_count = 0

        for item in selected_items:
            game_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not game_id:
                continue

            # Check if already in library
            if self.game_manager.is_in_library(game_id):
                continue

            # Check if already in queue
            if self.queue_widget.is_game_in_queue(game_id):
                continue

            # Get game info
            game = self.game_manager.get_game(game_id)
            if not game:
                continue

            # Add to queue widget
            self.queue_widget.add_item(game_id, game.name)

            # Create and start worker
            worker = GameAdditionWorker(game_id, self.game_manager)
            worker.signals.progress.connect(
                lambda gid, name, pct, msg: self._on_compilation_progress(
                    gid, name, pct, msg
                )
            )
            worker.signals.finished.connect(
                lambda gid, name, success, msg, path: self._on_compilation_finished(
                    gid, name, success, msg
                )
            )
            worker.signals.error.connect(
                lambda gid, name, err, tb: self._on_compilation_error(gid, name, err)
            )

            self.active_workers[game_id] = worker
            self.queue_widget.register_worker(game_id, worker)
            self.thread_pool.start(worker)

            queued_count += 1

        if queued_count > 0:
            # Show queue widget
            if not self.queue_widget.isVisible():
                self.queue_widget.show()
                self._center_queue_widget()

            self.results_label.setText(
                f"Queued {queued_count} game(s) for compilation..."
            )

    def _on_compilation_progress(
        self, game_id: int, game_name: str, percent: int, message: str
    ):
        """Handle compilation progress update."""
        self.queue_widget.update_progress(game_id, percent, message)

    def _on_compilation_finished(
        self, game_id: int, game_name: str, success: bool, message: str
    ):
        """Handle compilation completion."""
        self.queue_widget.mark_complete(game_id, success, message)

        if success:
            self._refresh_current_display()
            # Show success in results label temporarily
            self.results_label.setText(f"✓ {game_name} added successfully")
        else:
            self.results_label.setText(f"✗ {game_name}: {message}")

        # Clean up worker reference
        if game_id in self.active_workers:
            del self.active_workers[game_id]

    def _on_compilation_error(self, game_id: int, game_name: str, error: str):
        """Handle compilation error."""
        self.queue_widget.mark_complete(game_id, False, f"Error: {error}")
        self.results_label.setText(f"✗ {game_name} failed: {error}")

        if game_id in self.active_workers:
            del self.active_workers[game_id]

    def _on_item_cancelled(self, game_id: int):
        """Handle item cancellation from queue widget."""
        if game_id in self.active_workers:
            worker = self.active_workers[game_id]
            if hasattr(worker, "cancel"):
                worker.cancel()

    def _center_queue_widget(self):
        """Center the queue widget on the browser tab."""
        # Center on this widget
        rect = self.geometry()
        self.queue_widget.move(
            rect.center().x() - self.queue_widget.width() // 2,
            rect.center().y() - self.queue_widget.height() // 2,
        )

    def _refresh_current_display(self):
        """Refresh the current display."""
        search_text = self.search_input.text()
        if search_text:
            results = self.game_manager.search_games(search_text, limit=50)
            self._display_games(results)
        else:
            self.all_games = self.game_manager.get_all_games(limit=100)
            self._display_games(self.all_games)

    def refresh_games(self):
        """Refresh the game list after sync."""
        self.all_games = self.game_manager.get_all_games(limit=100)
        self._refresh_current_display()

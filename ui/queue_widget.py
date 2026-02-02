"""Compilation queue widget with detailed progress display.

This module provides a widget for displaying the compilation queue with real-time
progress updates, status indicators, and queue statistics.
"""

from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QFrame,
    QPushButton,
    QSizePolicy,
    QApplication,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont, QCloseEvent


# Dark theme colors (consistent with main window)
DARK_BG = "#1e1e1e"
DARKER_BG = "#252526"
ACCENT_COLOR = "#007acc"
TEXT_COLOR = "#cccccc"
BORDER_COLOR = "#3e3e42"
SUCCESS_COLOR = "#4ec9b0"
ERROR_COLOR = "#f44336"
WARNING_COLOR = "#ff9800"


class QueueItemWidget(QFrame):
    """Individual compilation queue item with progress display."""

    def __init__(self, game_id: int, game_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.game_id = game_id
        self.game_name = game_name
        self._is_cancelled = False
        self._setup_ui()

    def _setup_ui(self):
        """Setup the queue item UI."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {DARKER_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Header row: Name + Status
        header_layout = QHBoxLayout()

        # Game name
        self.name_label = QLabel(self.game_name)
        self.name_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {TEXT_COLOR};
        """)
        header_layout.addWidget(self.name_label)

        header_layout.addStretch()

        # Status label
        self.status_label = QLabel("Queued")
        self.status_label.setStyleSheet(f"""
            font-size: 10px;
            color: {WARNING_COLOR};
            font-weight: bold;
            padding: 2px 8px;
            background-color: {DARK_BG};
            border-radius: 4px;
        """)
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {DARK_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                color: {TEXT_COLOR};
                height: 20px;
                font-size: 9px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_COLOR};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Info row: Message + Cancel button
        info_layout = QHBoxLayout()

        # Status message
        self.message_label = QLabel("Waiting for available worker...")
        self.message_label.setStyleSheet("""
            font-size: 9px;
            color: #888;
        """)
        info_layout.addWidget(self.message_label)

        info_layout.addStretch()

        # Cancel button (shown only when active)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 3px;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        self.cancel_btn.hide()
        info_layout.addWidget(self.cancel_btn)

        layout.addLayout(info_layout)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(90)

    def update_progress(self, percent: int, message: str):
        """Update progress display."""
        self.progress_bar.setValue(percent)
        self.message_label.setText(message)

        if percent > 0 and percent < 100:
            self.status_label.setText("Compiling...")
            self.status_label.setStyleSheet(f"""
                font-size: 10px;
                color: {ACCENT_COLOR};
                font-weight: bold;
                padding: 2px 8px;
                background-color: {DARK_BG};
                border-radius: 4px;
            """)
            self.cancel_btn.show()

    def mark_complete(self, success: bool, message: str):
        """Mark item as complete."""
        self.progress_bar.setValue(100)
        self.message_label.setText(message)
        self.cancel_btn.hide()

        if success:
            self.status_label.setText("Complete")
            self.status_label.setStyleSheet(f"""
                font-size: 10px;
                color: {SUCCESS_COLOR};
                font-weight: bold;
                padding: 2px 8px;
                background-color: {DARK_BG};
                border-radius: 4px;
            """)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {DARK_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 4px;
                    text-align: center;
                    color: {TEXT_COLOR};
                    height: 20px;
                    font-size: 9px;
                }}
                QProgressBar::chunk {{
                    background-color: {SUCCESS_COLOR};
                    border-radius: 3px;
                }}
            """)
        else:
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet(f"""
                font-size: 10px;
                color: {ERROR_COLOR};
                font-weight: bold;
                padding: 2px 8px;
                background-color: {DARK_BG};
                border-radius: 4px;
            """)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {DARK_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 4px;
                    text-align: center;
                    color: {TEXT_COLOR};
                    height: 20px;
                    font-size: 9px;
                }}
                QProgressBar::chunk {{
                    background-color: {ERROR_COLOR};
                    border-radius: 3px;
                }}
            """)

    def is_cancelled(self) -> bool:
        """Check if this item was cancelled."""
        return self._is_cancelled

    def cancel(self):
        """Mark this item as cancelled."""
        self._is_cancelled = True
        self.status_label.setText("Cancelled")
        self.status_label.setStyleSheet(f"""
            font-size: 10px;
            color: #888;
            font-weight: bold;
            padding: 2px 8px;
            background-color: {DARK_BG};
            border-radius: 4px;
        """)
        self.cancel_btn.hide()
        self.message_label.setText("Cancelled by user")


class CompilationQueueWidget(QWidget):
    """
    Widget displaying the compilation queue with detailed progress.

    Features:
    - Shows all queued, active, and completed compilations
    - Real-time progress updates
    - Statistics (queue size, active workers, completed count)
    - Cancel and clear functionality

    Signals:
        item_cancelled(game_id): Emitted when user clicks cancel on an item
        all_cleared(): Emitted when all completed items are cleared
    """

    item_cancelled = pyqtSignal(int)
    all_cleared = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue_items: Dict[int, QueueItemWidget] = {}
        self.completed_items: List[int] = []
        self.cancelled_items: List[int] = []
        self.active_workers: Dict[int, Any] = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup the queue widget UI."""
        self.setWindowTitle("Compilation Queue")
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_BG};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header with stats
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Compilation Queue")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {TEXT_COLOR};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Stats label
        self.stats_label = QLabel("Queue: 0 | Active: 0 | Completed: 0")
        self.stats_label.setStyleSheet("color: #888; font-size: 10px;")
        header_layout.addWidget(self.stats_label)

        layout.addWidget(header)

        # Info text
        info_label = QLabel(
            "Games are compiled in background. Max 2 concurrent compilations."
        )
        info_label.setStyleSheet("color: #666; font-size: 9px; padding-bottom: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Scroll area for queue items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                background-color: {DARK_BG};
            }}
        """)

        # Container for queue items
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(10, 10, 10, 10)
        self.queue_layout.setSpacing(8)
        self.queue_layout.addStretch()

        scroll.setWidget(self.queue_container)
        layout.addWidget(scroll)

        # Bottom controls
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        # Cancel all button
        self.cancel_all_btn = QPushButton("Cancel All")
        self.cancel_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
            QPushButton:disabled {{
                background-color: {BORDER_COLOR};
                color: #666;
            }}
        """)
        self.cancel_all_btn.clicked.connect(self._cancel_all)
        self.cancel_all_btn.setEnabled(False)
        controls_layout.addWidget(self.cancel_all_btn)

        controls_layout.addStretch()

        # Clear completed button
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BORDER_COLOR};
                color: {TEXT_COLOR};
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #555;
            }}
            QPushButton:disabled {{
                background-color: {DARK_BG};
                color: #555;
            }}
        """)
        self.clear_btn.clicked.connect(self._clear_completed)
        self.clear_btn.setEnabled(False)
        controls_layout.addWidget(self.clear_btn)

        layout.addWidget(controls)

        # Set window properties
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self.resize(500, 450)

    def add_item(self, game_id: int, game_name: str) -> QueueItemWidget:
        """Add a new item to the queue."""
        if game_id in self.queue_items:
            return self.queue_items[game_id]

        item = QueueItemWidget(game_id, game_name)
        item.cancel_btn.clicked.connect(lambda: self._on_cancel(game_id))

        # Insert before the stretch
        index = self.queue_layout.count() - 1
        self.queue_layout.insertWidget(index, item)

        self.queue_items[game_id] = item
        self._update_stats()

        # Show window if hidden and this is the first item
        if not self.isVisible() and len(self.queue_items) == 1:
            self.show()
            self._center_on_screen()

        return item

    def update_progress(self, game_id: int, percent: int, message: str):
        """Update progress for a specific item."""
        if game_id in self.queue_items:
            self.queue_items[game_id].update_progress(percent, message)

    def mark_complete(self, game_id: int, success: bool, message: str):
        """Mark an item as complete."""
        if game_id in self.queue_items:
            self.queue_items[game_id].mark_complete(success, message)
            if game_id not in self.completed_items:
                self.completed_items.append(game_id)
            # Remove from active workers if present
            if game_id in self.active_workers:
                del self.active_workers[game_id]
            self._update_stats()

    def register_worker(self, game_id: int, worker: Any):
        """Register a worker for a game."""
        self.active_workers[game_id] = worker
        self._update_stats()

    def _on_cancel(self, game_id: int):
        """Handle cancel button click."""
        if game_id in self.active_workers:
            worker = self.active_workers[game_id]
            if hasattr(worker, "cancel"):
                worker.cancel()

        if game_id in self.queue_items:
            self.queue_items[game_id].cancel()
            if game_id not in self.cancelled_items:
                self.cancelled_items.append(game_id)

        self.item_cancelled.emit(game_id)
        self._update_stats()

    def _cancel_all(self):
        """Cancel all active and queued items."""
        # Cancel active workers
        for game_id, worker in list(self.active_workers.items()):
            if hasattr(worker, "cancel"):
                worker.cancel()
            if game_id in self.queue_items:
                self.queue_items[game_id].cancel()
            if game_id not in self.cancelled_items:
                self.cancelled_items.append(game_id)

        # Mark all queued items as cancelled
        for game_id, item in self.queue_items.items():
            if item.progress_bar.value() == 0:
                item.cancel()
                if game_id not in self.cancelled_items:
                    self.cancelled_items.append(game_id)

        self._update_stats()

    def _clear_completed(self):
        """Clear all completed and cancelled items from the queue."""
        items_to_remove = self.completed_items + self.cancelled_items

        for game_id in items_to_remove:
            if game_id in self.queue_items:
                item = self.queue_items[game_id]
                self.queue_layout.removeWidget(item)
                item.deleteLater()
                del self.queue_items[game_id]

        self.completed_items.clear()
        self.cancelled_items.clear()
        self._update_stats()
        self.all_cleared.emit()

        # Hide if empty
        if len(self.queue_items) == 0:
            self.hide()

    def _update_stats(self):
        """Update statistics display."""
        total = len(self.queue_items)
        active = sum(
            1
            for item in self.queue_items.values()
            if 0 < item.progress_bar.value() < 100
        )
        completed = len(self.completed_items)
        cancelled = len(self.cancelled_items)
        queued = total - active - completed - cancelled

        self.stats_label.setText(
            f"Queue: {queued} | Active: {active} | Completed: {completed}"
        )

        # Update button states
        self.clear_btn.setEnabled(completed > 0 or cancelled > 0)
        self.cancel_all_btn.setEnabled(active > 0 or queued > 0)

    def get_active_count(self) -> int:
        """Get number of active compilations."""
        return sum(
            1
            for item in self.queue_items.values()
            if 0 < item.progress_bar.value() < 100
        )

    def is_game_in_queue(self, game_id: int) -> bool:
        """Check if a game is already in the queue."""
        return game_id in self.queue_items

    def _center_on_screen(self):
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def closeEvent(self, a0: QCloseEvent | None):
        """Handle close event - hide instead of close."""
        self.hide()
        if a0:
            a0.ignore()

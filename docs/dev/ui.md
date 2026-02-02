# UI Documentation

## Overview

The Discord Games Launcher UI is built with PyQt6 and features a modern dark theme with proper list widgets for better organization and scalability.

**Framework:** PyQt6>=6.9.0  
**Theme:** Dark mode with blue accent (#007acc)  
**Components:** Main window with tabbed interface using QTreeWidget and QListWidget with custom widget items

## File Structure

```structure
ui/
├── __init__.py
├── main_window.py    # Main application window
├── browser_tab.py    # Game browser using QTreeWidget
└── library_tab.py    # Library management using QListWidget with custom widgets
```

## Theme Colors

Defined consistently across all UI files:

```python
DARK_BG = "#1e1e1e"        # Main background
DARKER_BG = "#252526"      # List/secondary background  
ACCENT_COLOR = "#007acc"   # Primary accent (blue)
TEXT_COLOR = "#cccccc"     # Primary text
BORDER_COLOR = "#3e3e42"   # Borders and dividers
SUCCESS_COLOR = "#4ec9b0"  # Success states (green)
ERROR_COLOR = "#f44336"    # Error states (red)
```

## Main Window

**File:** `ui/main_window.py`

### MainWindow Class

Main application window with header, tab widget, and status bar.

```python
class MainWindow(QMainWindow):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Minimum size: 1000x700 pixels
- Dark theme stylesheet
- Two tabs: Browse Games (QTreeWidget), My Library (QListWidget)
- Sync button for manual cache refresh
- Stats button for cache information
- Auto-refresh timer (5-second intervals)
- Status bar with live statistics

### UI Structure

```structure
MainWindow
├── Header (QHBoxLayout)
│   ├── Title Label
│   ├── Spacer
│   ├── Sync Button
│   └── Stats Button
├── Tab Widget (QTabWidget)
│   ├── BrowserTab (QTreeWidget - "Browse Games")
│   └── LibraryTab (QListWidget - "My Library")
└── Status Bar
```

## Browser Tab

**File:** `ui/browser_tab.py`

### BrowserTab Class

Tab for browsing and searching games using QTreeWidget for organized display.

```python
class BrowserTab(QWidget):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Tree view with 3 columns: Game Name, Executables, Status
- Real-time search filtering
- Multi-select support (Ctrl+Click, Shift+Click)
- Context menu for quick add
- Shows game aliases and available executables
- Visual status (Available / In Library)

### UI Structure_

```structure
BrowserTab
├── Search Layout (QHBoxLayout)
│   ├── Search Input (QLineEdit)
│   ├── Spacer
│   └── Results Label
├── Tree Widget (QTreeWidget)
│   ├── Column 0: Game name + aliases
│   ├── Column 1: Windows executables
│   └── Column 2: Status (Available/In Library)
└── Buttons Layout
    └── Add Selected Button
```

### Tree Widget Styling

```python
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
    QHeaderView::section {{
        background-color: {DARKER_BG};
        color: {TEXT_COLOR};
        padding: 8px;
        border: 1px solid {BORDER_COLOR};
        font-weight: bold;
    }}
""")
```

### Key Interactions

- **Search:** Type in search box to filter games instantly
- **Multi-select:** Hold Ctrl to select multiple games
- **Add Selected:** Click button to add all selected games (instant copy-based operation)
- **Context Menu:** Right-click game for quick add
- **Visual Feedback:** Games in library show green "In Library" status

## Library Tab

**File:** `ui/library_tab.py`

### LibraryTab Class

Tab for managing user's game library using QListWidget with PyQt6 custom widget items for rich display.

```python
class LibraryTab(QWidget):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Clean list view showing all library games
- PyQt6 custom widget items with QLabel for game info
- Status indicators (Running/Stopped with colors)
- Double-click to toggle start/stop
- Context menu for actions
- Stop All button for quick cleanup

### UI Structure__

```structure
LibraryTab
├── Header Layout
│   ├── Title Label ("My Library")
│   ├── Spacer
│   ├── Stop All Button
│   └── Refresh Button
├── Info Label (shown when empty)
├── List Widget (QListWidget)
│   └── Custom widget items showing:
│       ├── Game name (bold QLabel)
│       ├── Process name (small QLabel, gray)
│       └── Status (Running=green, Stopped=gray)
└── Status Label (game count)
```

### List Widget Styling

```python
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
""")
```

### Item Display Format

Items use PyQt6 widgets (QHBoxLayout with QLabels) for rich formatting:

```python
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
```

**Benefits of PyQt6 Widgets vs HTML:**

- Proper text rendering and font handling
- Better performance
- Native Qt styling support
- Easier to maintain and debug
- Consistent with rest of application

### Key Interactions_

- **Double-click:** Toggle start/stop the game
- **Context Menu:** Right-click for Start/Stop/Remove options
- **Stop All:** Button to stop all running games at once
- **Visual Status:** Green "Running" or gray "Stopped" indicator

## Context Menus

Both tabs support context menus with dark theme styling:

```python
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
```

## Dialogs and Messages

### Message Boxes

Dark theme applied to QMessageBox:

```python
msg = QMessageBox(self)
msg.setWindowTitle("Cache Statistics")
msg.setText("<h3>Discord Games Launcher Statistics</h3>")
msg.setInformativeText(f"""
    <table style='margin: 10px;'>
        <tr><td><b>Cached Games:</b></td><td>{stats["cached_games"]:,}</td></tr>
        <tr><td><b>Library Games:</b></td><td>{stats["library_games"]}</td></tr>
    </table>
""")
```

### Confirmation Dialogs

Library removal confirmation:

```python
reply = QMessageBox.question(
    self,
    "Confirm Removal",
    f"Remove '{game_name}' from library?\n\n"
    "This will stop the game if running and delete all associated files.",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
)
```

## Timer System

**Setup in MainWindow:**

```python
def _setup_timers(self):
    # Refresh running status every 5 seconds
    self.refresh_timer = QTimer()
    self.refresh_timer.timeout.connect(self._refresh_status)
    self.refresh_timer.start(5000)  # 5 seconds
```

**Purpose:**

- Updates running/stopped status indicators
- Refreshes status bar statistics
- Detects externally killed processes
- Updates UI to match actual process state

## Font Configuration

**Application-wide font (main.py):**

```python
font = QFont("Segoe UI", 10)
# Fallback to Arial if Segoe UI unavailable
available_families = QFontDatabase.families()
if "Segoe UI" not in available_families:
    font = QFont("Arial", 10)
app.setFont(font)
```

## High DPI Support

**Enabled in main.py:**

```python
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
```

## Common Patterns

### Creating a Rich List Item with PyQt6 Widgets

```python
item = QListWidgetItem()
item.setData(Qt.ItemDataRole.UserRole, game_id)
item.setSizeHint(QSize(0, 60))

# Create widget container
widget = QWidget()
layout = QHBoxLayout(widget)
layout.setContentsMargins(10, 5, 10, 5)
layout.setSpacing(10)

# Add labels
name_label = QLabel(game_name)
name_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_COLOR};")
status_label = QLabel(status)
status_label.setStyleSheet(f"font-size: 10px; color: {status_color};")

layout.addWidget(name_label)
layout.addWidget(status_label)

# Set widget on item
self.library_list.addItem(item)
self.library_list.setItemWidget(item, widget)
```

### Handling Context Menus

```python
def _show_context_menu(self, position):
    item = self.library_list.itemAt(position)
    if not item:
        return
    
    game_id = item.data(Qt.ItemDataRole.UserRole)
    
    menu = QMenu(self)
    action = menu.addAction("Start Game")
    action.triggered.connect(lambda: self._start_game(game_id))
    menu.exec(self.library_list.mapToGlobal(position))
```

### Multi-Selection in Tree Widget

```python
self.games_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

# Get selected items
selected_items = self.games_tree.selectedItems()
for item in selected_items:
    game_id = item.data(0, Qt.ItemDataRole.UserRole)
    # Process each selected game
```

## UI Improvements Summary

### Previous Implementation

- **Browser:** Grid layout with card widgets (3 columns)
- **Library:** Grid layout with card widgets (2 columns)
- **Items:** HTML-formatted text (didn't render properly)
- Issues: Poor scalability, inconsistent spacing, raw HTML displayed

### New Implementation

- **Browser:** QTreeWidget with columns (sortable, organized)
- **Library:** QListWidget with PyQt6 custom widget items (clean, scannable)
- **Items:** Native PyQt6 widgets (QLabel with proper styling)
- Benefits: Better organization, easier navigation, professional appearance, proper rendering

## Worker Threads

### Detection Worker Pattern

**Location:** `launcher/process_manager.py` and `ui/library_tab.py`

The Library Tab uses a QThread-based worker pattern for game detection that runs in the background, allowing the UI to remain responsive during the 15-second detection wait period.

```python
class DetectionWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, object, str)
    
    def run(self):
        # Detection logic runs here in separate thread
        ...
```

**Key Features:**

- Runs detection verification in a background thread
- Emits progress signals for real-time UI updates
- Emits finished signal with result when complete
- Supports early cancellation via `stop()` method

### Thread Lifecycle Management

The thread/worker cleanup sequence is critical to prevent crashes:

```python
# In ProcessManager.start_game_with_ui_updates():
thread = QThread()
worker = DetectionWorker(...)
worker.moveToThread(thread)

# Signal connections in correct order:
thread.started.connect(worker.run)           # 1. Start worker when thread starts
worker.finished.connect(thread.quit)         # 2. Request thread quit when worker finishes
thread.finished.connect(worker.deleteLater)  # 3. Delete worker AFTER thread stops
thread.finished.connect(thread.deleteLater)  # 4. Delete thread AFTER it stops
```

**Critical Points:**

- `deleteLater()` must be connected to `thread.finished`, NOT `worker.finished`
- This ensures the QThread has fully stopped before Qt cleans up objects
- Python references should not be cleared until after Qt cleanup completes
- Use `QTimer.singleShot()` to delay operations that depend on thread completion

### Library Tab Thread Handling

```python
class LibraryTab(QWidget):
    def __init__(self, ...):
        self.detection_worker = None  # Current worker reference
        self.detection_thread = None  # Current thread reference
    
    def _start_game(self, game_id):
        # Check if detection already running
        if self.detection_thread is not None and self.detection_thread.isRunning():
            return  # Block concurrent detection
        
        # Create worker and thread
        worker, thread = self.game_manager.process_mgr.start_game_with_ui_updates(...)
        
        # Store references (but don't clear them in _on_detection_finished!)
        self.detection_worker = worker
        self.detection_thread = thread
        
        # Connect signals
        worker.progress.connect(self._on_detection_progress)
        worker.finished.connect(lambda s, e, m: self._on_detection_finished(...))
        
        thread.start()
    
    def _on_detection_finished(self, ...):
        # DON'T clear references here - let Qt's deleteLater handle cleanup
        # References cleared via QTimer.singleShot after cleanup completes
        def show_result():
            self.detection_worker = None
            self.detection_thread = None
            # Show result dialog...
        QTimer.singleShot(200, show_result)
    
    def cleanup(self):
        # Called on app close - must wait for thread to actually stop
        if self.detection_worker is not None:
            self.detection_worker.stop()
        if self.detection_thread is not None and self.detection_thread.isRunning():
            self.detection_thread.quit()
            self.detection_thread.wait(2000)  # Block until thread stops
```

### Benefits of This Architecture

- **UI Responsiveness:** Main thread never blocked during 15-second detection wait
- **Safe Cleanup:** Thread/worker objects properly cleaned up by Qt's event loop
- **No Crashes:** Prevents "QThread: Destroyed while thread is still running" errors
- **Cancellation:** Users can cancel ongoing detection or close the app safely

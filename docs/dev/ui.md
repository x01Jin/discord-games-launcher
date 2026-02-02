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

CompilationQueueWidget (NEW - Shows when adding games)
├── Header (stats: Queue | Active | Completed)
├── Queue Items (QScrollArea)
│   └── QueueItemWidget (game name, progress bar, cancel button)
└── Controls
    ├── Cancel All Button
    └── Clear Completed Button
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
- **Add Selected:** Click button to add all selected games
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
- **NEW:** GUI mode for better Discord game detection with status info dialog

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

## Testing Checklist

- [ ] Search functionality filters correctly
- [ ] Tree widget displays games properly
- [ ] List widget shows library with widget-based items
- [ ] Multi-select works in browser
- [ ] Context menus appear and function
- [ ] Double-click toggles start/stop
- [ ] Status updates reflect process state
- [ ] Dark theme consistent throughout
- [ ] Resize handling works properly
- [ ] Empty library message displays
- [ ] Library items render correctly (not showing HTML)

## Compilation Queue Widget

**File:** `ui/queue_widget.py`

### CompilationQueueWidget Class

Widget for displaying compilation queue with real-time progress updates during PyInstaller execution.

```python
class CompilationQueueWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None)
```

**Features:**

- Shows all queued, active, and completed compilations
- Real-time progress updates from worker threads
- Queue statistics (queued count, active workers, completed count)
- Cancel individual or all compilations
- Clear completed items button
- Auto-shows when games are added, hides when queue empties
- Floating window style

### QueueItemWidget Class

Individual item in the compilation queue with progress display.

```python
class QueueItemWidget(QFrame):
    def __init__(self, game_id: int, game_name: str, parent: Optional[QWidget] = None)
```

**Features:**

- Game name and status badge
- Progress bar with percentage
- Status message
- Cancel button (only visible when active)
- Color-coded status (Queued/Compiling/Complete/Failed)

## Worker Threads

**File:** `ui/workers.py`

### GameAdditionWorker Class

Worker thread for adding a single game to library asynchronously.

```python
class GameAdditionWorker(QRunnable):
    def __init__(self, game_id: int, game_manager: Any, progress_callback: Optional[Callable] = None)
```

**Features:**

- Runs complete game addition workflow in background thread
- Emits progress signals for UI updates
- Emits finished/error signals on completion
- Supports cancellation mid-compilation
- Handles cleanup if cancelled

**Workflow:**

1. Validate game exists in cache
2. Check if already in library
3. Get Windows executable configuration
4. Emit progress: "Generating dummy executable..."
5. Call `DummyGenerator.generate_dummy()` (blocking)
6. Emit progress: "Adding to library..."
7. Update database
8. Emit finished signal with result/error

### WorkerSignals Class

Signals emitted by worker threads.

```python
class WorkerSignals(QObject):
    progress = pyqtSignal(int, str, int, str)  # (game_id, game_name, percent, message)
    finished = pyqtSignal(int, str, bool, str, str)  # (game_id, game_name, success, message, exe_path)
    error = pyqtSignal(int, str, str, str)  # (game_id, game_name, error, traceback)
```

## Threading Architecture

### Thread Pool Configuration

Browser tab uses `QThreadPool` with maximum 2 concurrent workers:

```python
self.thread_pool = QThreadPool()
self.thread_pool.setMaxThreadCount(2)
```

This prevents overwhelming the system during PyInstaller compilation (CPU-intensive operation).

### Adding Games Flow

```flow
User clicks "Add Selected"
         │
         ▼
BrowserTab._add_selected_games()
         │
         ├─► Check if already in queue
         ├─► Add to CompilationQueueWidget
         ├─► Create GameAdditionWorker
         ├─► Connect worker signals
         │    ├─► progress → queue_widget.update_progress()
         │    ├─► finished → queue_widget.mark_complete()
         │    └─► error → queue_widget.mark_complete(success=False)
         ├─► Register worker with queue widget
         └─► thread_pool.start(worker)
              │
              ▼
         Worker Thread (Background)
              │
              ├─► Get game info
              ├─► Validate not in library
              ├─► Get executable config
              ├─► Generate dummy via PyInstaller (BLOCKING)
              │     └─► Can take 30-60 seconds
              ├─► Add to database
              └─► Emit finished signal
                    │
                    ▼
               UI Thread Updates (via signals)
                    ├─► Queue item shows progress
                    ├─► Progress bar updates
                    └─► Status changes: Queued → Compiling → Complete
```

### Benefits of Threading

- **UI Responsiveness:** Main thread never blocked during PyInstaller compilation
- **Real-time Feedback:** Users see progress for all queued compilations
- **Cancellation:** Users can cancel ongoing compilations
- **Scalability:** Can queue multiple games, process in background
- **User Experience:** Can continue browsing/using app while compilations run

# UI Documentation

## Overview

The Discord Games Launcher UI is built with PyQt6 and features a modern dark theme inspired by Visual Studio Code.

**Framework:** PyQt6>=6.9.0  
**Theme:** Dark mode with blue accent (#007acc)  
**Components:** Main window with tabbed interface

## File Structure

```structure
ui/
├── __init__.py
├── main_window.py    # Main application window
├── browser_tab.py    # Game browser/search tab
└── library_tab.py    # Library management tab
```

## Theme Colors

Defined consistently across all UI files:

```python
DARK_BG = "#1e1e1e"        # Main background
DARKER_BG = "#252526"      # Card/secondary background  
ACCENT_COLOR = "#007acc"   # Primary accent (blue)
TEXT_COLOR = "#cccccc"     # Primary text
BORDER_COLOR = "#3e3e42"   # Borders and dividers
SUCCESS_COLOR = "#4ec9b0"  # Success states (green)
ERROR_COLOR = "#f44336"    # Error states (red)
```

## Main Window

**File:** `ui/main_window.py:34`

### MainWindow Class

Main application window with header, tab widget, and status bar.

```python
class MainWindow(QMainWindow):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Minimum size: 1000x700 pixels
- Dark theme stylesheet
- Two tabs: Browse Games, My Library
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
│   ├── BrowserTab ("Browse Games")
│   └── LibraryTab ("My Library")
└── Status Bar
```

### Key Methods

#### _setup_ui()

**Line:** 44

Initializes all UI components and layout.

#### _apply_dark_theme()

**Line:** 113

Applies comprehensive dark theme stylesheet covering:

- Main window background
- Tab widgets and bars
- Buttons (hover, pressed, disabled states)
- Input fields (QLineEdit)
- Scroll areas and bars
- Status bar
- Message boxes

#### _on_sync_clicked()

**Line:** 241

Handles manual sync button click with loading state.

#### _show_stats()

**Line:** 261

Displays cache statistics in a message box.

#### closeEvent()

**Line:** 296

Cleanup on window close - stops all running games.

## Browser Tab

**File:** `ui/browser_tab.py:108`

### BrowserTab Class

Tab for browsing and searching Discord's game database.

```python
class BrowserTab(QWidget):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Search games by name
- Grid display of game cards
- Real-time search filtering
- Add games to library
- Auto-load on startup

### UI Structure 2

```structure
BrowserTab
├── Search Layout (QHBoxLayout)
│   ├── Search Input (QLineEdit)
│   ├── Spacer
│   └── Results Label
└── Scroll Area
    └── Cards Container (QGridLayout)
        └── GameCard widgets
```

### GameCard Class

**Line:** 28

Individual game card displaying game information.

**Displays:**

- Game name (bold)
- Aliases (if any, first 3)
- Windows executables (first 2)
- "Add to Library" button

**Button States:**

- Enabled: "Add to Library" (default)
- Disabled: "In Library" (green background when added)
- Loading: "Adding..." (disabled during operation)

### Key Methods_

#### _load_initial_games()

**Line:** 157

Loads initial game cache, syncs if needed.

#### _display_games()

**Line:** 174

Displays games in grid layout (3 columns).

#### _on_search_changed()

**Line:** 205

Filters games based on search text.

#### refresh_games()

**Line:** 215

Refreshes display after sync.

## Library Tab

**File:** `ui/library_tab.py:228`

### LibraryTab Class

Tab for managing user's game library.

```python
class LibraryTab(QWidget):
    def __init__(self, game_manager: GameManager)
```

**Features:**

- Display library games with status
- Start/stop dummy processes
- Remove games from library
- Stop all running games
- Real-time status updates

### UI Structure_

```structure
LibraryTab
├── Header Layout
│   ├── Title Label ("My Library")
│   ├── Spacer
│   ├── Stop All Button
│   └── Refresh Button
├── Info Label (empty library message)
└── Scroll Area
    └── Cards Container (QGridLayout)
        └── LibraryGameCard widgets
```

### LibraryGameCard Class

**Line:** 34

Card for a game in the user's library.

**Displays:**

- Game name
- Status indicator (Running/Stopped)
- Process name
- Executable path (truncated)
- Start/Stop button
- Remove button

**Status Indicators:**

- Running: Green text "Running" with badge
- Stopped: Gray text "Stopped" with badge

**Buttons:**

- Start: Blue accent, starts process
- Stop: Red, stops process
- Remove: Red, removes from library

### Key Methods__

#### refresh_library()

**Line:** 303

Reloads and displays all library games.

#### update_running_status()

**Line:** 340

Updates running status of all cards from process manager.

#### _stop_all_games()

**Line:** 345

Stops all running games with confirmation.

## Styling Examples

### Game Card Style

```python
GameCard {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 8px;
    padding: 10px;
}
GameCard:hover {
    border: 1px solid #007acc;
}
```

### Button States

```python
QPushButton {
    background-color: #007acc;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:pressed {
    background-color: #004578;
}
QPushButton:disabled {
    background-color: #3e3e42;
    color: #666;
}
```

### Tab Styling

```python
QTabBar::tab {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #3e3e42;
    border-bottom: none;
    padding: 8px 20px;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background-color: #252526;
    border-bottom: 2px solid #007acc;
}
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
    "This will stop the game if running and delete the dummy executable.",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
)
```

## Timer System

**Setup in MainWindow (line 234):**

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

## Font Configuration

**Application-wide font (main.py:51):**

```python
font = QFont("Segoe UI", 10)
# Fallback to Arial if Segoe UI unavailable
available_families = QFontDatabase.families()
if "Segoe UI" not in available_families:
    font = QFont("Arial", 10)
app.setFont(font)
```

## High DPI Support

**Enabled in main.py:42:**

```python
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
```

## Testing

UI tests use pytest-qt:

```python
# tests/ directory (if UI tests exist)
# Requires: pytest-qt>=4.4.0
```

**Manual testing checklist:**

- [ ] Search functionality
- [ ] Add to library
- [ ] Start/stop processes
- [ ] Remove from library
- [ ] Sync games
- [ ] Dark theme consistency
- [ ] Resize handling
- [ ] Status updates

## Common Patterns

### Adding a Widget with Stretch

```python
layout.addWidget(widget)
layout.addStretch()  # Pushes widget to left
```

### Creating a Card Widget

```python
card = QFrame()
card.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
card.setStyleSheet("background-color: #252526; border-radius: 8px;")
```

### Enabling/Disabling with Loading State

```python
self.button.setEnabled(False)
self.button.setText("Loading...")
# ... do work ...
self.button.setEnabled(True)
self.button.setText("Click Me")
```

### Safe Parent Traversal

```python
parent = self.parent()
while parent is not None:
    refresh_method = getattr(parent, "refresh_library", None)
    if callable(refresh_method):
        refresh_method()
        break
    parent = parent.parent()
```

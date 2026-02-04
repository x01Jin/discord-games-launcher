# Discord Games Launcher Documentation

Welcome to the Discord Games Launcher documentation. This documentation is organized into two main sections:

## Documentation Sections

### [Developer Documentation](./dev/)

Technical documentation for developers working on or extending the launcher.

- **[Architecture](./dev/architecture.md)** - System architecture, component overview, and data flow
- **[API](./dev/api.md)** - Discord API client documentation and integration details  
- **[Database](./dev/database.md)** - SQLite schema, models, and database operations
- **[UI](./dev/ui.md)** - PyQt6 UI components, theming, and interface design
- **[Testing](./dev/testing.md)** - Test suite, running tests, and test coverage

### [User Documentation](./user/)

End-user documentation for installing and using the launcher.

- **[Installation](./user/installation.md)** - System requirements and installation guide
- **[Getting Started](./user/getting-started.md)** - Quick start guide and first steps
- **[Features](./user/features.md)** - Complete feature documentation
- **[Troubleshooting](./user/troubleshooting.md)** - Common issues and solutions

## Quick Links

**For Users:**

- New users: Start with [Installation](./user/installation.md) → [Getting Started](./user/getting-started.md)
- Having issues? Check [Troubleshooting](./user/troubleshooting.md)

**For Developers:**

- Understanding the system: [Architecture](./dev/architecture.md)
- Making changes: [Testing](./dev/testing.md)
- API integration: [API](./dev/api.md)

## Overview

Discord Games Launcher is a Windows application that allows users to browse Discord's supported games database and create dummy processes that trigger Discord's "Playing [Game]" status display. It provides:

- Browse 20,000+ Discord-supported games
- Search and filter game database
- Add games to personal library
- Copy pre-built dummy executable templates for Discord detection
- Run multiple games simultaneously
- Dark theme interface

## Technology Stack

- **Python 3.13+**
- **PyQt6** - GUI framework
- **SQLite** - Local database
- **httpx** - HTTP client for Discord API
- **Copy-based template system** - Instant dummy executable generation
- **psutil** - Process management

## Project Structure

```structure
discord-games-launcher/
├── docs/               # This documentation
├── launcher/           # Backend modules
│   ├── api.py         # Discord API client
│   ├── database.py    # SQLite database
│   ├── dummy_generator.py  # Dummy exe generator
│   ├── game_manager.py     # High-level game operations
│   └── process_manager.py  # Process lifecycle
├── ui/                # UI components
│   ├── main_window.py # Main window
│   ├── browser_tab.py # Game browser
│   └── library_tab.py # Library manager
├── templates/         # PyInstaller templates
├── tests/            # Test suite
└── main.py          # Entry point
```

---

- *Last updated: 2025-02-04* -

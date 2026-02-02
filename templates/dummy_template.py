#!/usr/bin/env python3
"""Template for generating dummy game processes.

This script is compiled by PyInstaller to create dummy executables
that mimic real game processes to trigger Discord's "Playing" status.

Placeholders:
- {game_id}: Discord application ID
- {game_name}: Display name of the game
- {process_name}: Target process name (e.g., "overwatch.exe")
"""

import time
import os
from pathlib import Path


def main():
    """Keep process alive to trigger Discord's Playing status."""
    # These variables are set during template generation
    # noqa: F841 - variables intentionally defined but unused (Discord detects by process name)
    game_id = "{game_id}"  # noqa: F841
    game_name = "{game_name}"  # noqa: F841
    process_name = "{process_name}"  # noqa: F841

    # Write PID file for tracking
    try:
        pid_file = Path(__file__).parent / ".pid"
        pid_file.write_text(str(os.getpid()))
    except Exception:
        pass

    try:
        # Keep process alive with minimal CPU usage
        # Discord detects games based on process name
        while True:
            time.sleep(60)  # Sleep for 1 minute at a time
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup PID file
        try:
            pid_file = Path(__file__).parent / ".pid"
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()

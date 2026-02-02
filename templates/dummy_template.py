#!/usr/bin/env python3
"""Dummy background process for Discord Games Launcher.

This executable mimics a game process to trigger Discord's "Playing" status.
Simply keeps the process alive without any GUI.

Placeholders:
- $game_id$: Discord application ID
- $game_name$: Display name of the game
- $process_name$: Target process name (e.g., "overwatch.exe")
"""

import time
from pathlib import Path
import os


def main():
    """Keep process alive to trigger Discord's Playing status."""
    # These variables are set during template generation
    game_id = "$game_id$"  # noqa: F841
    game_name = "$game_name$"  # noqa: F841
    process_name = "$process_name$"  # noqa: F841

    # Write PID file for tracking
    try:
        pid_file = Path(__file__).parent / ".pid"
        pid_file.write_text(str(os.getpid()))
    except Exception:
        pass

    # Keep process alive with minimal CPU usage
    try:
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

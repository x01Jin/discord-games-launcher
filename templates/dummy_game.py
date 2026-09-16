#!/usr/bin/env python3
"""
Dummy Game for Discord Games Launcher.

A minimal stdlib-only (tkinter) window that displays the game name passed
as argument. The process name matches what Discord expects, and the window
shows that Discord should detect it as "Playing [Game Name]".

Usage:
    dummy_game.exe "Game Name"

This template is compiled once into DummyGame.exe and then COPIED
and RENAMED for each game (matching the expected process name).
"""

import sys
from datetime import datetime, timezone

try:
    import tkinter as tk

    HAS_GUI = True
except ImportError:
    tk = None  # type: ignore[assignment]
    HAS_GUI = False


def run_gui(game_name: str) -> None:
    """Show the status window (stdlib tkinter, no third-party deps)."""
    assert tk is not None, "tkinter is required for the GUI"
    start_time = datetime.now(timezone.utc)

    root = tk.Tk()
    root.title(game_name)
    root.geometry("480x300")
    root.minsize(480, 300)
    root.configure(bg="#1e1e1e")

    title = tk.Label(
        root,
        text=game_name,
        bg="#1e1e1e",
        fg="#cccccc",
        font=("Segoe UI", 16, "bold"),
    )
    title.pack(pady=(24, 4))

    subtitle = tk.Label(
        root,
        text="Game Started!",
        bg="#1e1e1e",
        fg="#4ade80",
        font=("Segoe UI", 12, "bold"),
    )
    subtitle.pack()

    info = tk.Label(
        root,
        text=(
            "This window helps Discord detect the game.\n\n"
            "Check your Discord profile to see if status appears.\n\n"
            "\u2022 Ensure 'Display current activity' is ON in Discord settings\n"
            "\u2022 Run Discord as Administrator\n"
            "\u2022 Wait 30-60 seconds for Discord to scan processes"
        ),
        bg="#1e1e1e",
        fg="#888888",
        font=("Segoe UI", 9),
        justify="center",
    )
    info.pack(pady=12)

    runtime_label = tk.Label(
        root,
        text="Runtime: 0:00:00",
        bg="#1e1e1e",
        fg="#666666",
        font=("Segoe UI", 10),
    )
    runtime_label.pack(side="bottom", pady=12)

    def _tick() -> None:
        elapsed = datetime.now(timezone.utc) - start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_label.config(text=f"Runtime: {hours}:{minutes:02d}:{seconds:02d}")
        root.after(1000, _tick)

    _tick()
    root.mainloop()


def main():
    """Main entry point."""
    game_name = sys.argv[1] if len(sys.argv) > 1 else "Game"

    if not HAS_GUI:
        # Fallback: just keep process alive without GUI
        print(f"Running as: {game_name} (no GUI)")
        import time

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    run_gui(game_name)


if __name__ == "__main__":
    main()

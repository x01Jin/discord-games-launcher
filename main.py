#!/usr/bin/env python3
"""Discord Games Launcher - Main Entry Point.

Hosts the React frontend (frontend-dist/) in a native pywebview window
with a DWM-styled dark frame. Python backend is exposed to the page
through the Bridge js_api.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import webview
from platformdirs import user_data_dir
from screeninfo import get_monitors

from launcher.api import DiscordAPIClient
from launcher.bridge import Bridge
from launcher.database import Database
from launcher.dummy_generator import DummyGenerator
from launcher.game_manager import GameManager
from launcher.logger import GameLauncherLogger
from launcher.process_manager import ProcessManager

APP_TITLE = "Discord Games Launcher"
APP_VERSION = "3.0.0"

# DWM window attributes (verified against Win11 SDK docs)
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_WIN10 = 19
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36

_FRAME_BG = 0x0014151C  # BGR for #14151c
_FRAME_TEXT = 0x00FFFFFF


def _dwm_set(hwnd: int, attr: int, value: int) -> bool:
    """Set one DWMWA attribute; False instead of raising on failure."""
    try:
        import ctypes

        v = ctypes.c_int(value)
        return (
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)
            == 0
        )
    except (AttributeError, OSError):
        return False


def _apply_native_frame_style(window: webview.Window) -> None:
    """Dark native frame, applied once the native handle exists.

    Keeps 100% native behavior (resize, Aero Snap, shadow, rounded
    corners): only tint and dark mode are customized, never geometry.
    """
    if os.name != "nt":
        return
    native = window.native
    if native is None:
        return
    try:
        hwnd = int(native.Handle.ToInt32())
    except (AttributeError, ValueError, TypeError):
        return
    if not _dwm_set(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, 1):
        _dwm_set(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE_WIN10, 1)
    _dwm_set(hwnd, _DWMWA_CAPTION_COLOR, _FRAME_BG)
    _dwm_set(hwnd, _DWMWA_TEXT_COLOR, _FRAME_TEXT)
    _dwm_set(hwnd, _DWMWA_BORDER_COLOR, _FRAME_BG)
    _dwm_set(hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE, 2)  # round


def _resolve_frontend_url() -> str:
    """Dev-server URL if requested, else the bundled production build."""
    dev_url = os.environ.get("DCGL_FRONTEND_URL")
    if dev_url:
        return dev_url
    base = Path(getattr(sys, "_MEIPASS", project_root))
    entry = base / "frontend-dist" / "index.html"
    if not entry.is_file():
        raise FileNotFoundError(
            f"Frontend build not found at {entry}. "
            "Run 'npm run build' in frontend/ or set DCGL_FRONTEND_URL."
        )
    return str(entry)


def initialize_components():
    """Initialize all backend components."""
    app_data_dir = Path(user_data_dir("discord-games-launcher", appauthor=False))
    db_path = app_data_dir / "launcher.db"
    cache_dir = app_data_dir / "cache"
    games_dir = app_data_dir / "games"

    app_data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    games_dir.mkdir(parents=True, exist_ok=True)

    print(f"Data directory: {app_data_dir}")

    logger = GameLauncherLogger()
    logger.app_start()

    database = Database(db_path, logger=logger)
    api_client = DiscordAPIClient(database, cache_dir, logger=logger)
    dummy_generator = DummyGenerator(games_dir)
    process_manager = ProcessManager(database, dummy_generator, logger=logger)
    game_manager = GameManager(
        database=database,
        api_client=api_client,
        dummy_generator=dummy_generator,
        process_manager=process_manager,
        logger=logger,
    )

    try:
        repair = game_manager.repair_library(startup=True)
        print(f"Library repair: {repair}")
    except Exception as e:  # noqa: BLE001 - repair must never block startup
        print(f"Library repair skipped: {e}")

    return game_manager, logger


def _calculate_window_geometry() -> tuple[int, int, int, int]:
    """Calculate window width, height, x, y for 75% of primary monitor, centered."""
    try:
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        screen_w, screen_h = primary.width, primary.height
    except (StopIteration, IndexError, OSError):
        # Fallback defaults
        screen_w, screen_h = 1920, 1080

    w = int(screen_w * 0.75)
    h = int(screen_h * 0.75)
    x = (screen_w - w) // 2
    y = (screen_h - h) // 2

    # Clamp to reasonable minimums
    w = max(w, 900)
    h = max(h, 600)
    return w, h, x, y


def main():
    """Main application entry point."""
    print(f"Discord Games Launcher v{APP_VERSION}")
    print("=" * 40)

    game_manager = None
    logger = None

    try:
        print("Initializing components...")
        game_manager, logger = initialize_components()
        bridge = Bridge(game_manager)

        url = _resolve_frontend_url()
        print(f"Frontend: {url}")

        w, h, x, y = _calculate_window_geometry()
        print(f"Window: {w}x{h} at ({x}, {y})")

        window = webview.create_window(
            APP_TITLE,
            url=url,
            width=w,
            height=h,
            x=x,
            y=y,
            min_size=(900, 600),
            resizable=True,
            frameless=False,
            shadow=True,
            focus=True,
            background_color="#14151c",
            js_api=bridge,
        )
        if window is None:
            raise RuntimeError("Failed to create application window")

        def _push(event: dict) -> None:
            payload = json.dumps(event, separators=(",", ":"))
            window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('dcgl',{{detail:{payload}}}))"
            )

        bridge.push = _push
        window.events.shown += lambda *a: _apply_native_frame_style(window)

        print("Ready!")
        webview.start(debug=bool(os.environ.get("DCGL_DEBUG")))

    except Exception as e:  # noqa: BLE001 - last resort: report anything before exit
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()

        if logger:
            logger.critical(f"Fatal error: {e}")

        sys.exit(1)
    finally:
        if game_manager:
            game_manager.process_mgr.force_cleanup_all()
        if logger:
            logger.app_exit()


if __name__ == "__main__":
    main()

# Build & Packaging

## Overview

This page covers the two build artifacts developers produce: the distributable `dcgl.exe` (PyInstaller, `dcgl.spec`) and the dummy-game template (`templates/dist/DummyGame.exe`, via `templates/build_dummy.py`).

## Building dcgl.exe

```cmd
pyinstaller dcgl.spec
```

Rebuild from clean state when the icon or bundled data changes:

```cmd
pyinstaller --clean dcgl.spec
```

## App Icon Pipeline

The exe icon comes from `assets/icon.ico`, embedded by `dcgl.spec:40` (`icon=['assets/icon.ico']`). PyInstaller cannot use PNGs for exe icons, so the source of truth is `assets/dcgl.png` and the `.ico` is generated from it with Pillow (`pillow` is in `requirements.txt`).

### App Icon Stays Old After Rebuilding

Replaced the icon in `assets/` but the built app still shows the old one. Causes and fixes, in order:

1. **The build embeds the `.ico`, not the `.png`.** Regenerate the `.ico` from the new `.png` first (install requirements, then save with sizes 16–256 via Pillow). A bare `.NET`-written `.ico` is rejected at the "Copying icon" step — regenerate it with Pillow.
2. **Stale PyInstaller cache.** Rebuild with the clean flag:

   ```cmd
   pyinstaller --clean dcgl.spec
   ```

3. **Windows icon cache.** If the new icon still doesn't show, refresh it with `ie4uinit.exe -show`, or as a last resort delete `%LOCALAPPDATA%\IconCache.db` and restart Explorer.

Note: the window title-bar and taskbar icon come from the exe itself (`main.py` sets no separate window icon), so fixing the `.ico` fixes both.

## Dummy Template Build

The runtime never compiles executables — it copies a prebuilt template. Rebuild the template after changing `templates/dummy_game.py`:

```cmd
python templates/build_dummy.py
```

This produces `templates/dist/DummyGame.exe`, which `DummyGenerator` copies and renames per game (see [Architecture](./architecture.md)). You can also point the generator at a custom template with the `DUMMYGAME_EXE` environment variable.

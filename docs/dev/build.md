# Build and packaging

## Overview

Two artifacts get built: the distributable single-file `dcgl.exe` (PyInstaller, `dcgl.spec`) and the dummy-game template (`templates/dist/DummyGame.exe`, via `templates/build_dummy.py`).

## Building dcgl.exe

From the repository root, with the virtual environment active:

```cmd
pyinstaller --clean --noconfirm dcgl.spec
```

The result is `dist/dcgl.exe`, one file of about 61 MB. That is the file users download.

Build inputs the spec refuses to start without:

| Input | Build it with |
| --- | --- |
| `frontend-dist/index.html` | `npm run build` in `frontend/` |
| `templates/dist/DummyGame.exe` | `python templates/build_dummy.py` |
| `assets/icon.ico` | Generate from `assets/dcgl.png` with Pillow (see below) |

A missing input stops the build with the command that produces it, instead of a PyInstaller traceback.

## Version

`launcher/__init__.py` holds the version:

```python
__version__ = "3.5.0"
```

`main.py` imports it as `APP_VERSION` for the startup banner, and `dcgl.spec` reads it to generate `build/version_info.txt`, which becomes the Windows version resource. Explorer Properties shows that number under FileVersion and ProductVersion. Bump it in one place and rebuild; nothing else needs editing.

## Single file or folder

The spec builds a single-file exe by default. On launch, PyInstaller unpacks the bundle into `%TEMP%` and starts the app from there, which costs startup time. Measured on this machine, time from launch until the page answers:

| Layout | Command | Startup |
| --- | --- | --- |
| Single file | `pyinstaller --clean --noconfirm dcgl.spec` | 5.1 to 5.6 s |
| Folder | `set DCGL_ONEFILE=0`, then the same command | 3.5 s |

The folder build lands in `dist/dcgl/dcgl.exe` with its libraries beside it. Use it while iterating on the app; ship the single file.

Both layouts read the frontend and the dummy template from `sys._MEIPASS`, so nothing else changes between them.

## Fatal errors in a windowed build

`console=False` means a frozen build has no stdout, so an early exception would otherwise close the app without a trace. `main.py` catches it, writes to the log, and shows a message box with the error text. Development runs keep printing to the console.

## App icon pipeline

The exe icon comes from `assets/icon.ico`, embedded by the `icon=` argument in `dcgl.spec`. PyInstaller cannot use PNGs for exe icons, so the source of truth is `assets/dcgl.png` and the `.ico` is generated from it with Pillow (`pillow` is in `requirements.txt`).

### App icon stays old after rebuilding

Replaced the icon in `assets/` but the built app still shows the old one. Causes and fixes, in order:

1. The built exe embeds the `.ico`, not the `.png`. Regenerate the `.ico` from the new `.png` first (sizes 16 to 256, saved with Pillow). A bare .NET-written `.ico` is rejected at the "Copying icon" step, so regenerate it with Pillow.
2. Stale PyInstaller cache. Rebuild with the clean flag:

   ```cmd
   pyinstaller --clean --noconfirm dcgl.spec
   ```

3. Windows icon cache. If the new icon still does not show, run `ie4uinit.exe -show`, or as a last resort delete `%LOCALAPPDATA%\IconCache.db` and restart Explorer.

The title bar and taskbar icon come from the exe itself (`main.py` sets no separate window icon), so fixing the `.ico` fixes both.

## Dummy template build

The runtime never compiles executables. It copies a prebuilt template, so rebuild the template after changing `templates/dummy_game.py`:

```cmd
python templates/build_dummy.py
```

This produces `templates/dist/DummyGame.exe`, which `DummyGenerator` copies and renames per game (see [Architecture](./architecture.md)). You can also point the generator at a custom template with the `DUMMYGAME_EXE` environment variable.

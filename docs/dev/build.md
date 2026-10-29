# Build and packaging

Two artifacts: the single-file `dcgl.exe` (PyInstaller, `dcgl.spec`) and the
dummy-game template (`templates/dist/DummyGame.exe`, built by
`templates/build_dummy.py`).

## dcgl.exe

From the repository root, with the virtual environment active:

```cmd
pyinstaller --clean --noconfirm dcgl.spec
```

The result is `dist/dcgl.exe`, one file of about 39 MB. That is the file users
download. Three inputs must exist first, and the spec stops with the command
that produces any that is missing:

| Input | Build it with |
| --- | --- |
| `frontend-dist/index.html` | `npm run build` in `frontend/` |
| `templates/dist/DummyGame.exe` | `python templates/build_dummy.py` |
| `assets/icon.ico` | Generated from `assets/dcgl.png` with Pillow |

`launcher/__init__.py` holds `__version__`; `main.py` shows it in the startup
banner and `dcgl.spec` turns it into the Windows version resource, so Explorer
Properties reports it and one edit covers both.

`console=False` means a frozen build has no stdout: `main.py` catches an early
exception, writes the log, and shows a message box with the error text.

## Single file or folder

The spec builds a single-file exe by default, unpacking into `%TEMP%` on launch,
which costs startup time. Measured on this machine, from launch until the page
answers:

| Layout | Command | Startup |
| --- | --- | --- |
| Single file | `pyinstaller --clean --noconfirm dcgl.spec` | 5.1 to 5.6 s |
| Folder | `set DCGL_ONEFILE=0`, then the same command | 3.5 s |

The folder build lands in `dist/dcgl/dcgl.exe` with its libraries beside it. Use
it while iterating; ship the single file. Both layouts read the frontend and the
dummy template from `sys._MEIPASS`.

## App icon

The exe embeds `assets/icon.ico`, generated from `assets/dcgl.png` with Pillow
because PyInstaller cannot use a PNG for an exe icon. A bare .NET-written `.ico`
is rejected at the "Copying icon" step.

If a rebuilt app still shows the old icon, regenerate the `.ico` (sizes 16 to
256, saved with Pillow), rebuild with `--clean`, and if it persists run
`ie4uinit.exe -show` or delete `%LOCALAPPDATA%\IconCache.db` and restart Explorer.
The title bar and taskbar icon come from the exe, so the `.ico` fixes both.

## Dummy template

The runtime never compiles executables. It copies a prebuilt template, so
rebuild it after changing `templates/dummy_game.py`:

```cmd
python templates/build_dummy.py
```

`templates/dist/DummyGame.exe` is what `DummyGenerator` copies and renames per
game (see [Architecture](./architecture.md)). `DUMMYGAME_EXE` points the
generator at a custom template.

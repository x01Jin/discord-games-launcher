# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for dcgl.exe.

Build the single-file executable users download:

    pyinstaller --clean --noconfirm dcgl.spec

For a folder build that starts faster while developing:

    set DCGL_ONEFILE=0
    pyinstaller --clean --noconfirm dcgl.spec

The version comes from launcher/__init__.py, so bump it there and rebuild.
"""

import os
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).resolve()
ONEFILE = os.environ.get("DCGL_ONEFILE", "1") != "0"

# Fail with the fix, not with a PyInstaller traceback three minutes in.
for required in (
    ROOT / "frontend-dist" / "index.html",
    ROOT / "templates" / "dist" / "DummyGame.exe",
    ROOT / "assets" / "icon.ico",
):
    if not required.is_file():
        raise SystemExit(
            f"Missing build input: {required}\n"
            "Build it first: 'npm run build' in frontend/, "
            "'python templates/build_dummy.py' for the dummy template."
        )

_version_source = (ROOT / "launcher" / "__init__.py").read_text(encoding="utf-8")
_match = re.search(r'__version__\s*=\s*"([0-9.]+)"', _version_source)
if _match is None:
    raise SystemExit("launcher/__init__.py has no __version__ string")
VERSION = _match.group(1)
_PARTS = [int(part) for part in VERSION.split(".")][:4]
VERSION_PARTS = tuple(_PARTS + [0] * (4 - len(_PARTS)))

# Windows shows this in the exe Properties, and the shell uses it for sorting.
# PyInstaller re-reads this file with eval(), so it has to stay in the
# documented plain-constructor form. repr() emits versioninfo.-prefixed
# constructors that eval() cannot resolve.
_version_file = ROOT / "build" / "version_info.txt"
_version_file.parent.mkdir(parents=True, exist_ok=True)
_version_file.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$VERSION_PARTS,
    prodvers=$VERSION_PARTS,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Discord Games Launcher'),
        StringStruct('FileDescription', 'Discord Games Launcher'),
        StringStruct('FileVersion', '$VERSION'),
        StringStruct('InternalName', 'dcgl'),
        StringStruct('OriginalFilename', 'dcgl.exe'),
        StringStruct('ProductName', 'Discord Games Launcher'),
        StringStruct('ProductVersion', '$VERSION')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""".replace("$VERSION_PARTS", str(VERSION_PARTS)).replace("$VERSION", VERSION),
    encoding="utf-8",
)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "templates" / "dist"), "templates/dist"),
        (str(ROOT / "frontend-dist"), "frontend-dist"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

_common = dict(
    name="dcgl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is not required and is not installed here; enabling it only prints
    # a warning. Flip to True if you actually want UPX compression.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "assets" / "icon.ico")],
    version=str(_version_file),
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **_common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **_common)
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="dcgl",
    )

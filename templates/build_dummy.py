#!/usr/bin/env python3
"""
Build script to create DummyGame.exe template.

This compiles the dummy_game.py into a standalone executable that can be
copied and renamed for each game. Only needs to be run once during development
or when the template changes.

Usage:
    python build_dummy.py
"""

import subprocess
import sys
import shutil
from pathlib import Path


def build_dummy():
    """Build DummyGame.exe using PyInstaller."""
    script_dir = Path(__file__).parent
    template_path = script_dir / "dummy_game.py"
    output_dir = script_dir / "dist"

    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        return False

    print("Building DummyGame.exe...")
    print(f"  Template: {template_path}")
    print(f"  Output:   {output_dir}")

    # Build command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name",
        "DummyGame",
        "--distpath",
        str(output_dir),
        "--workpath",
        str(script_dir / "build"),
        "--specpath",
        str(script_dir),
        # Include PyQt6 for GUI
        "--hidden-import",
        "PyQt6",
        "--hidden-import",
        "PyQt6.QtWidgets",
        "--hidden-import",
        "PyQt6.QtCore",
        "--hidden-import",
        "PyQt6.QtGui",
        str(template_path),
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print("\nERROR: PyInstaller failed!")
        return False

    # Verify output
    exe_path = output_dir / "DummyGame.exe"
    if not exe_path.exists():
        print(f"\nERROR: Expected output not found: {exe_path}")
        return False

    print(f"\n✓ Successfully built: {exe_path}")
    print(f"  Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Cleanup build artifacts
    build_dir = script_dir / "build"
    spec_file = script_dir / "DummyGame.spec"

    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("  Cleaned up build directory")

    if spec_file.exists():
        spec_file.unlink()
        print("  Cleaned up spec file")

    return True


if __name__ == "__main__":
    success = build_dummy()
    sys.exit(0 if success else 1)

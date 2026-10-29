#!/usr/bin/env python3

import shutil
import subprocess
import sys
from pathlib import Path


def build_dummy():
    script_dir = Path(__file__).parent
    template_path = script_dir / "dummy_game.py"
    output_dir = script_dir / "dist"

    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        return False

    print("Building DummyGame.exe...")
    print(f"  Template: {template_path}")
    print(f"  Output:   {output_dir}")

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
        str(template_path),
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=False, check=False)

    if result.returncode != 0:
        print("\nERROR: PyInstaller failed!")
        return False

    exe_path = output_dir / "DummyGame.exe"
    if not exe_path.exists():
        print(f"\nERROR: Expected output not found: {exe_path}")
        return False

    print(f"\nSuccessfully built: {exe_path}")
    print(f"  Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")

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

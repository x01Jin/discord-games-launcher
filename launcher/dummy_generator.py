"""Discord Games Launcher - Dummy Generator module.

Handles generation of dummy executables using PyInstaller.
These executables mimic real game processes to trigger Discord's "Playing" status.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import shutil


class DummyGenerationError(Exception):
    """Raised when dummy executable generation fails."""

    pass


class DummyGenerator:
    """Generates dummy executables that mimic game processes."""

    def __init__(self, output_dir: Path, template_path: Optional[Path] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Default template path
        if template_path is None:
            template_path = (
                Path(__file__).parent.parent / "templates" / "dummy_template.py"
            )
        self.template_path = template_path

    def generate_dummy(
        self, game_id: int, game_name: str, process_name: str
    ) -> Tuple[Path, str]:
        """Generate a dummy executable for a game.

        Args:
            game_id: Discord game ID
            game_name: Display name of the game
            process_name: Target process name (e.g., "overwatch.exe")

        Returns:
            Tuple of (path_to_exe, actual_process_name)

        Raises:
            DummyGenerationError: If PyInstaller fails
        """
        # Create game-specific directory
        game_dir = self.output_dir / str(game_id)
        game_dir.mkdir(parents=True, exist_ok=True)

        # Output path for the exe
        exe_path = game_dir / process_name

        # Check if already exists
        if exe_path.exists():
            return exe_path, process_name

        # Generate the dummy script
        temp_script = self._create_dummy_script(game_id, game_name, process_name)

        try:
            # Run PyInstaller
            self._run_pyinstaller(temp_script, exe_path, process_name)

            # PyInstaller creates it in dist/ subdirectory
            pyinstaller_output = exe_path.parent / "dist" / process_name

            # Move to final location if needed
            if pyinstaller_output.exists() and pyinstaller_output != exe_path:
                if exe_path.exists():
                    exe_path.unlink()
                pyinstaller_output.rename(exe_path)

            # Cleanup PyInstaller build artifacts
            self._cleanup_build_artifacts(game_dir)

            return exe_path, process_name

        except Exception as e:
            # Cleanup on failure
            if exe_path.exists():
                exe_path.unlink()
            raise DummyGenerationError(f"Failed to generate dummy: {e}")
        finally:
            # Clean up temp script
            if temp_script.exists():
                temp_script.unlink()

    def _create_dummy_script(
        self, game_id: int, game_name: str, process_name: str
    ) -> Path:
        """Create a temporary Python script for PyInstaller.

        The dummy does nothing but sleep in a loop to maintain the process.
        """
        # Use the template if available, otherwise create inline
        if self.template_path.exists():
            template = self.template_path.read_text()
            script_content = template.format(
                game_id=game_id, game_name=game_name, process_name=process_name
            )
        else:
            # Inline template
            script_content = f'''#!/usr/bin/env python3
"""Dummy process for Discord Games Launcher.

Game: {game_name} (ID: {game_id})
Process: {process_name}
"""

import time
import sys
from pathlib import Path

def main():
    """Keep process alive to trigger Discord's Playing status."""
    # Write PID file for tracking
    pid_file = Path(__file__).parent / ".pid"
    pid_file.write_text(str(sys.pid))
    
    try:
        # Keep process alive with minimal CPU usage
        while True:
            time.sleep(60)  # Sleep for 1 minute at a time
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup PID file
        if pid_file.exists():
            pid_file.unlink()

if __name__ == "__main__":
    main()
'''

        # Write to temp file
        temp_file = Path(tempfile.gettempdir()) / f"dummy_{game_id}_{process_name}.py"
        temp_file.write_text(script_content)
        return temp_file

    def _run_pyinstaller(
        self, script_path: Path, output_path: Path, process_name: str
    ) -> None:
        """Run PyInstaller to create the executable."""
        # Build PyInstaller command
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",  # Single executable file
            "--windowed",  # No console window
            "--noconfirm",  # Overwrite without asking
            "--clean",  # Clean PyInstaller cache
            "--name",
            str(Path(process_name).stem),  # Output name
            "--distpath",
            str(output_path.parent),  # Output directory
            "--workpath",
            str(output_path.parent / "build"),
            "--specpath",
            str(output_path.parent),
            str(script_path),
        ]

        # Run PyInstaller
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if result.returncode != 0:
            raise DummyGenerationError(f"PyInstaller failed: {result.stderr}")

    def _cleanup_build_artifacts(self, game_dir: Path) -> None:
        """Clean up PyInstaller build artifacts."""
        # Remove build directory
        build_dir = game_dir / "build"
        if build_dir.exists():
            shutil.rmtree(build_dir)

        # Remove .spec files
        for spec_file in game_dir.glob("*.spec"):
            spec_file.unlink()

    def remove_dummy(self, game_id: int, process_name: str) -> bool:
        """Remove a generated dummy executable.

        Returns:
            True if removed successfully, False if not found
        """
        game_dir = self.output_dir / str(game_id)
        exe_path = game_dir / process_name

        if not exe_path.exists():
            return False

        try:
            exe_path.unlink()

            # Remove parent directory if empty
            if game_dir.exists() and not any(game_dir.iterdir()):
                game_dir.rmdir()

            return True
        except OSError:
            return False

    def dummy_exists(self, game_id: int, process_name: str) -> bool:
        """Check if a dummy executable exists."""
        exe_path = self.output_dir / str(game_id) / process_name
        return exe_path.exists()

    def get_dummy_path(self, game_id: int, process_name: str) -> Path:
        """Get the expected path for a dummy executable."""
        return self.output_dir / str(game_id) / process_name

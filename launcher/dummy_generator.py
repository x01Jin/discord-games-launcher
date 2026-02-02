"""Discord Games Launcher - Dummy Generator module.

Handles generation of dummy executables using PyInstaller.
These executables mimic real game processes to trigger Discord's "Playing" status.
"""

import subprocess
import sys
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import shutil
from datetime import datetime


class DummyGenerationError(Exception):
    """Raised when dummy executable generation fails."""

    pass


class DummyGenerator:
    """Generates dummy executables that mimic game processes."""

    def __init__(
        self,
        output_dir: Path,
        template_path: Optional[Path] = None,
        use_gui: bool = True,
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gui = use_gui
        self.progress_callback = None  # For progress updates during compilation

        # Set up logging to file
        self._setup_logger()

        # Select template based on mode
        if template_path is None:
            if use_gui:
                template_path = (
                    Path(__file__).parent.parent / "templates" / "gui_dummy_template.py"
                )
            else:
                template_path = (
                    Path(__file__).parent.parent / "templates" / "dummy_template.py"
                )
        self.template_path = template_path

    def _setup_logger(self):
        """Set up file-based logger for PyInstaller compilation."""
        # Create logs directory in output_dir
        logs_dir = self.output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(f"DummyGenerator_{id(self)}")
        self.logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        self.logger.handlers.clear()

        # Create file handler with timestamp
        log_file = (
            logs_dir / f"pyinstaller_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # Add handler to logger
        self.logger.addHandler(file_handler)

        self.logger.info("=" * 80)
        self.logger.info("DummyGenerator initialized")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info("=" * 80)

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
            template = self.template_path.read_text(encoding="utf-8")
            script_content = template.replace("$game_id$", str(game_id))
            script_content = script_content.replace("$game_name$", game_name)
            script_content = script_content.replace("$process_name$", process_name)
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
        temp_file.write_text(script_content, encoding="utf-8")
        return temp_file

    def _get_python_executable(self) -> str:
        """Get the path to the Python interpreter.

        When running as a PyInstaller frozen executable, sys.executable points
        to the EXE itself, not Python. We need to find the actual Python.
        """
        # Check if we're running as a frozen PyInstaller executable
        if getattr(sys, "frozen", False):
            # Running as compiled EXE - need to find actual Python
            # Try common locations
            python_exe = self._find_system_python()
            if python_exe:
                return python_exe
            # Fall back to sys.executable if Python not found
            # (will fail gracefully later)
        return sys.executable

    def _find_system_python(self) -> Optional[str]:
        """Find the system Python interpreter."""
        # Check if python is in PATH
        try:
            result = subprocess.run(
                ["where", "python"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            if result.returncode == 0:
                # Get the first Python found in PATH
                python_path = result.stdout.strip().split("\n")[0].strip()
                if python_path and os.path.exists(python_path):
                    return python_path
        except Exception:
            pass

        # Try common installation paths
        common_paths = [
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
            r"C:\Python39\python.exe",
            r"C:\Program Files\Python311\python.exe",
            r"C:\Program Files\Python310\python.exe",
            r"C:\Program Files\Python39\python.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python39\python.exe"),
            os.path.expandvars(r"%USERPROFILE%\.pyenv\pyenv-win\shims\python.bat"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def _run_pyinstaller(
        self, script_path: Path, output_path: Path, process_name: str
    ) -> None:
        """Run PyInstaller to create the executable."""
        # Get the correct Python executable (handles frozen EXE case)
        python_exe = self._get_python_executable()

        if self.progress_callback:
            self.progress_callback(20, "Starting PyInstaller...")

        # Build PyInstaller command
        cmd = [
            python_exe,
            "-m",
            "PyInstaller",
            "--onefile",  # Single executable file
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
        ]

        # GUI mode: bundle PyQt6, don't hide console (helps debugging)
        if self.use_gui:
            cmd.extend(
                [
                    "--hidden-import",
                    "PyQt6",
                    "--hidden-import",
                    "PyQt6.QtWidgets",
                    "--hidden-import",
                    "PyQt6.QtCore",
                    "--hidden-import",
                    "PyQt6.QtGui",
                ]
            )
        else:
            # Background mode: hide console
            cmd.append("--windowed")

        cmd.append(str(script_path))

        if self.progress_callback:
            self.progress_callback(30, "Running PyInstaller (this may take a while)...")

        # Log command being run
        self.logger.info("Running PyInstaller command:")
        self.logger.info(f"  {' '.join(cmd)}")

        # Run PyInstaller
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout (increased from 2 minutes)
        )

        # Log result
        self.logger.info(f"PyInstaller returncode: {result.returncode}")
        if result.stdout:
            self.logger.info("PyInstaller stdout:")
            self.logger.info(result.stdout)
        if result.stderr:
            self.logger.warning("PyInstaller stderr:")
            self.logger.warning(result.stderr)

        if self.progress_callback:
            self.progress_callback(80, "PyInstaller completed, finalizing...")

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
        """Remove a generated dummy executable and its game directory.

        Returns:
            True if removed successfully, False if not found
        """
        game_dir = self.output_dir / str(game_id)
        exe_path = game_dir / process_name

        if not exe_path.exists() and not game_dir.exists():
            return False

        try:
            # Remove the executable
            if exe_path.exists():
                exe_path.unlink()

            # Remove PID file if it exists
            pid_file = game_dir / ".pid"
            if pid_file.exists():
                pid_file.unlink()

            # Remove any dist directory that might exist
            dist_dir = game_dir / "dist"
            if dist_dir.exists():
                shutil.rmtree(dist_dir)

            # Remove any build directory that might exist
            build_dir = game_dir / "build"
            if build_dir.exists():
                shutil.rmtree(build_dir)

            # Remove any .spec files
            for spec_file in game_dir.glob("*.spec"):
                spec_file.unlink()

            # Remove the entire game directory
            if game_dir.exists():
                shutil.rmtree(game_dir)

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

"""Discord Games Launcher - Dummy Generator module.

Handles creation of dummy executables by copying a pre-built template.
These executables mimic real game processes to trigger Discord's "Playing" status.

The approach is simple:
1. A pre-built DummyGame.exe template exists in templates/dist/
2. When a game is added, we copy the template and rename it to match the target process
3. When launched, the game name is passed as a command-line argument
"""

import shutil
import os
import sys
from pathlib import Path
from typing import Optional, Tuple


class DummyGeneratorError(Exception):
    """Raised when dummy executable operations fail."""

    pass


class DummyGenerator:
    """Manages dummy executables by copying pre-built template."""

    # Name of the pre-built template executable
    TEMPLATE_EXE_NAME = "DummyGame.exe"

    def __init__(self, output_dir: Path, template_exe_path: Optional[Path] = None):
        """Initialize the dummy generator.

        Args:
            output_dir: Directory where game dummy executables will be stored
            template_exe_path: Path to the pre-built DummyGame.exe template.
                              If not provided, looks in templates/dist/
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Find template executable
        if template_exe_path is not None:
            self.template_exe_path = template_exe_path
        else:
            self.template_exe_path = self._find_template_exe()

    def _find_template_exe(self) -> Path:
        """Find the DummyGame.exe template.

        Search order:
        1. templates/dist/DummyGame.exe (normal development/installed location)
        2. PyInstaller bundled location (_internal/templates/dist)
        3. DUMMYGAME_EXE environment variable
        4. Same directory as this script
        5. Output directory (in case it was placed there)
        """
        # Check templates/dist/ directory (development)
        project_root = Path(__file__).parent.parent
        template_path = project_root / "templates" / "dist" / self.TEMPLATE_EXE_NAME
        if template_path.exists():
            return template_path

        # Check PyInstaller _internal folder (when running as packaged executable)
        if getattr(sys, "frozen", False):
            # When running from packaged directory, the exe is at dist/dcgl/dcgl.exe
            # and _internal is at dist/dcgl/_internal/
            exe_dir = Path(sys.executable).parent
            pyinstaller_template = (
                exe_dir / "_internal" / "templates" / "dist" / self.TEMPLATE_EXE_NAME
            )
            if pyinstaller_template.exists():
                return pyinstaller_template

        # Check environment variable
        env_path = os.environ.get("DUMMYGAME_EXE")
        if env_path:
            env_template = Path(env_path)
            if env_template.exists():
                return env_template

        # Check same directory as this module
        module_dir_path = Path(__file__).parent / self.TEMPLATE_EXE_NAME
        if module_dir_path.exists():
            return module_dir_path

        # Check output directory (in case it was placed there)
        output_path = self.output_dir / self.TEMPLATE_EXE_NAME
        if output_path.exists():
            return output_path

        # Not found - return expected path for error messages
        return template_path

    def is_template_available(self) -> bool:
        """Check if the DummyGame.exe template is available."""
        return self.template_exe_path.exists()

    def get_template_path(self) -> Path:
        """Get the path to the template executable."""
        return self.template_exe_path

    def ensure_dummy_for_game(
        self, game_id: int, process_name: str
    ) -> Tuple[Path, str]:
        """Ensure a dummy executable exists for a game.

        If the executable doesn't exist, copies the template and renames it.
        If it already exists, returns the existing path.

        Args:
            game_id: Discord game ID (used for folder organization)
            process_name: Target process name (e.g., "minecraft.exe")

        Returns:
            Tuple of (path_to_exe, actual_process_name)

        Raises:
            DummyGeneratorError: If template not found or copy fails
        """
        if not self.is_template_available():
            raise DummyGeneratorError(
                f"DummyGame.exe template not found. Expected at: {self.template_exe_path}\n"
                "Run 'python templates/build_dummy.py' to build it, "
                "or set DUMMYGAME_EXE environment variable."
            )

        # Normalize the process name (handle paths like "_retail_/wow.exe")
        normalized_name = self._normalize_process_name(process_name)

        # Create game-specific directory: output_dir/game_id/
        game_dir = self.output_dir / str(game_id)
        game_dir.mkdir(parents=True, exist_ok=True)

        # Handle subdirectory in process name (e.g., "_retail_/wow.exe")
        exe_rel_path = Path(normalized_name)
        if exe_rel_path.parent != Path("."):
            # Process name has subdirectory - create it
            sub_dir = game_dir / exe_rel_path.parent
            sub_dir.mkdir(parents=True, exist_ok=True)
            exe_path = game_dir / exe_rel_path
        else:
            exe_path = game_dir / normalized_name

        # Copy template if it doesn't exist
        if not exe_path.exists():
            try:
                shutil.copy2(self.template_exe_path, exe_path)
            except Exception as e:
                raise DummyGeneratorError(f"Failed to copy template: {e}")

        return exe_path, normalized_name

    def _normalize_process_name(self, process_name: str) -> str:
        """Normalize a process name for filesystem use.

        Args:
            process_name: Original process name from Discord API

        Returns:
            Normalized name safe for filesystem
        """
        # Replace backslashes with forward slashes for consistency
        name = process_name.replace("\\", "/")

        # Ensure it ends with .exe
        if not name.lower().endswith(".exe"):
            name = name + ".exe"

        return name

    def remove_dummy(self, game_id: int, process_name: str) -> bool:
        """Remove a dummy executable and its game directory.

        Args:
            game_id: Discord game ID
            process_name: Process name of the executable

        Returns:
            True if removed successfully, False if not found
        """
        game_dir = self.output_dir / str(game_id)

        if not game_dir.exists():
            return False

        try:
            # Remove the entire game directory
            shutil.rmtree(game_dir)
            return True
        except OSError:
            return False

    def dummy_exists(self, game_id: int, process_name: str) -> bool:
        """Check if a dummy executable exists for a game."""
        normalized_name = self._normalize_process_name(process_name)
        exe_path = self.output_dir / str(game_id) / normalized_name
        return exe_path.exists()

    def get_dummy_path(self, game_id: int, process_name: str) -> Path:
        """Get the path where a dummy executable would be stored."""
        normalized_name = self._normalize_process_name(process_name)
        return self.output_dir / str(game_id) / normalized_name

    def get_working_directory(self, game_id: int, process_name: str) -> Path:
        """Get the working directory for launching a dummy executable."""
        exe_path = self.get_dummy_path(game_id, process_name)
        return exe_path.parent

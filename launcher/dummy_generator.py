import os
import shutil
import sys
from pathlib import Path


class DummyGeneratorError(Exception):
    pass


class DummyGenerator:
    TEMPLATE_EXE_NAME = "DummyGame.exe"

    def __init__(self, output_dir: Path, template_exe_path: Path | None = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if template_exe_path is not None:
            self.template_exe_path = template_exe_path
        else:
            self.template_exe_path = self._find_template_exe()

    def _find_template_exe(self) -> Path:
        project_root = Path(__file__).parent.parent
        template_path = project_root / "templates" / "dist" / self.TEMPLATE_EXE_NAME
        if template_path.exists():
            return template_path

        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                bundled_template = (
                    Path(meipass) / "templates" / "dist" / self.TEMPLATE_EXE_NAME
                )
                if bundled_template.exists():
                    return bundled_template

        env_path = os.environ.get("DUMMYGAME_EXE")
        if env_path:
            env_template = Path(env_path)
            if env_template.exists():
                return env_template

        module_dir_path = Path(__file__).parent / self.TEMPLATE_EXE_NAME
        if module_dir_path.exists():
            return module_dir_path

        output_path = self.output_dir / self.TEMPLATE_EXE_NAME
        if output_path.exists():
            return output_path

        return template_path

    def is_template_available(self) -> bool:
        return self.template_exe_path.exists()

    def get_template_path(self) -> Path:
        return self.template_exe_path

    def ensure_dummy_for_game(
        self, game_id: int, process_name: str
    ) -> tuple[Path, str]:
        if not self.is_template_available():
            raise DummyGeneratorError(
                f"DummyGame.exe template not found. Expected at: {self.template_exe_path}\n"
                "Run 'python templates/build_dummy.py' to build it, "
                "or set DUMMYGAME_EXE environment variable."
            )

        normalized_name = self._normalize_process_name(process_name)

        game_dir = self.output_dir / str(game_id)
        game_dir.mkdir(parents=True, exist_ok=True)

        exe_rel_path = Path(normalized_name)
        if exe_rel_path.parent != Path("."):
            sub_dir = game_dir / exe_rel_path.parent
            sub_dir.mkdir(parents=True, exist_ok=True)
            exe_path = game_dir / exe_rel_path
        else:
            exe_path = game_dir / normalized_name

        if not exe_path.exists():
            try:
                shutil.copy2(self.template_exe_path, exe_path)
            except OSError as e:
                raise DummyGeneratorError(f"Failed to copy template: {e}")

        return exe_path, normalized_name

    def _normalize_process_name(self, process_name: str) -> str:
        name = process_name.replace("\\", "/")

        if not name.lower().endswith(".exe"):
            name = name + ".exe"

        return name

    def remove_dummy(self, game_id: int, process_name: str) -> bool:
        game_dir = self.output_dir / str(game_id)

        if not game_dir.exists():
            return False

        try:
            shutil.rmtree(game_dir)
            return True
        except OSError:
            return False

    def dummy_exists(self, game_id: int, process_name: str) -> bool:
        normalized_name = self._normalize_process_name(process_name)
        exe_path = self.output_dir / str(game_id) / normalized_name
        return exe_path.exists()

    def get_dummy_path(self, game_id: int, process_name: str) -> Path:
        normalized_name = self._normalize_process_name(process_name)
        return self.output_dir / str(game_id) / normalized_name

    def get_working_directory(self, game_id: int, process_name: str) -> Path:
        exe_path = self.get_dummy_path(game_id, process_name)
        return exe_path.parent

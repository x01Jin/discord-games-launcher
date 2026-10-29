from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

from launcher.dummy_generator import DummyGeneratorError


class MaintenanceMixin:
    def startup_cleanup(self, reset_runtime: bool = True) -> dict[str, int]:
        summary = {
            "stale_processes": 0,
            "dangling_removed": 0,
            "orphan_dirs_removed": 0,
            "root_exes_removed": 0,
            "exes_recreated": 0,
            "icons_pruned": 0,
            "warnings": 0,
        }

        def warn(message: str) -> None:
            summary["warnings"] += 1
            if self.logger:
                self.logger.warning(message)

        if reset_runtime:
            try:
                summary["stale_processes"] = self.process_mgr.reset_runtime_state()
            except Exception as e:
                warn(f"Startup cleanup: could not reset runtime state: {e}")

        try:
            library_ids = self.db.get_library_ids()
            cached_ids = self.db.get_cached_game_ids()
        except (sqlite3.Error, OSError) as e:
            warn(f"Startup cleanup: could not read library/cache ids: {e}")
            return summary

        games_dir = self.dummy_gen.output_dir

        if cached_ids:
            dangling = library_ids - cached_ids
            purged: set[int] = set()
            for game_id in sorted(dangling):
                if self.process_mgr.is_running(game_id):
                    warn(
                        f"Startup cleanup: skipping dangling game {game_id}: "
                        f"process running."
                    )
                    continue
                try:
                    game_dir = games_dir / str(game_id)
                    if game_dir.is_dir():
                        shutil.rmtree(game_dir)
                except OSError as e:
                    warn(
                        f"Startup cleanup: could not remove dir for "
                        f"dangling game {game_id}: {e}"
                    )
                try:
                    self.db.remove_from_library(game_id)
                    purged.add(game_id)
                    summary["dangling_removed"] += 1
                except (sqlite3.Error, OSError) as e:
                    warn(
                        f"Startup cleanup: could not purge dangling game {game_id}: {e}"
                    )
            library_ids -= purged

        template_norm = os.path.normcase(
            os.path.abspath(self.dummy_gen.template_exe_path)
        )
        try:
            if games_dir.is_dir():
                for child in games_dir.iterdir():
                    if child.is_dir():
                        try:
                            dir_id: int | None = int(child.name)
                        except ValueError:
                            dir_id = None
                        if dir_id is not None and dir_id in library_ids:
                            continue
                        try:
                            shutil.rmtree(child)
                            summary["orphan_dirs_removed"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {child}: {e}")
                    elif child.is_file() and child.suffix.lower() == ".exe":
                        if os.path.normcase(os.path.abspath(child)) == template_norm:
                            continue
                        try:
                            child.unlink()
                            summary["root_exes_removed"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {child}: {e}")
        except OSError as e:
            warn(f"Startup cleanup: could not scan {games_dir}: {e}")

        template_missing_logged = False
        for game_id in sorted(library_ids):
            try:
                lib_game = self.db.get_library_game(game_id)
            except (sqlite3.Error, OSError) as e:
                warn(f"Startup cleanup: could not read library game {game_id}: {e}")
                continue
            if lib_game is None:
                continue
            exe_path = (
                Path(lib_game.executable_path) if lib_game.executable_path else None
            )
            if exe_path is not None and exe_path.exists():
                continue
            if not self.dummy_gen.is_template_available():
                if not template_missing_logged:
                    template_missing_logged = True
                    warn(
                        "Startup cleanup: DummyGame.exe template not found, "
                        "missing executables left as-is."
                    )
                continue
            candidate = lib_game.process_name
            if lib_game.executables:
                candidate = lib_game.executables[0].get("name", candidate)
            try:
                new_path, _actual = self.dummy_gen.ensure_dummy_for_game(
                    game_id=game_id, process_name=candidate
                )
            except (DummyGeneratorError, OSError) as e:
                warn(f"Startup cleanup: could not recreate exe for game {game_id}: {e}")
                continue
            try:
                self.db.add_to_library(
                    game_id,
                    str(new_path),
                    lib_game.process_name,
                    lib_game.normalized_process_name,
                    lib_game.executables,
                )
                summary["exes_recreated"] += 1
            except (sqlite3.Error, OSError) as e:
                warn(f"Startup cleanup: could not update row {game_id}: {e}")

        try:
            icons_dir = self.api.icons_dir
            if icons_dir.is_dir():
                for icon in icons_dir.glob("*.png"):
                    try:
                        icon_id: int | None = int(icon.stem.split("_")[0])
                    except ValueError:
                        icon_id = None
                    if icon_id is not None and icon_id not in cached_ids:
                        try:
                            icon.unlink()
                            summary["icons_pruned"] += 1
                        except OSError as e:
                            warn(f"Startup cleanup: could not remove {icon}: {e}")
        except OSError as e:
            warn(f"Startup cleanup: could not scan icons: {e}")

        if self.logger:
            self.logger.info(f"Startup cleanup: {summary}")
        return summary

    def refresh_library_candidates(
        self, drop_superseded: bool = True
    ) -> dict[str, int]:
        summary = {
            "refreshed": 0,
            "exes_replaced": 0,
            "skipped_running": 0,
            "no_win_exes": 0,
            "warnings": 0,
        }

        def warn(message: str) -> None:
            summary["warnings"] += 1
            if self.logger:
                self.logger.warning(message)

        try:
            library_ids = self.db.get_library_ids()
        except (sqlite3.Error, OSError) as e:
            warn(f"Refresh: could not read library ids: {e}")
            return summary

        for game_id in sorted(library_ids):
            try:
                game = self.db.get_game(game_id)
                lib_game = self.db.get_library_game(game_id)
            except (sqlite3.Error, OSError) as e:
                warn(f"Refresh: could not read game {game_id}: {e}")
                continue
            if game is None or lib_game is None:
                continue
            win_exes = self.api.get_best_win32_executables(game.executables)
            if not win_exes:
                summary["no_win_exes"] += 1
                warn(f"Refresh: {game.name} has no Windows executables in cache.")
                continue
            old_names = [e.get("name", "") for e in lib_game.executables]
            new_names = [e.get("name", "") for e in win_exes]
            if old_names == new_names:
                continue
            if self.process_mgr.is_running(game_id):
                summary["skipped_running"] += 1
                continue
            best = win_exes[0]["name"]
            normalized = self.api.normalize_process_name(best)
            old_path = (
                Path(lib_game.executable_path) if lib_game.executable_path else None
            )
            try:
                exe_path, _actual = self.dummy_gen.ensure_dummy_for_game(
                    game_id=game_id, process_name=best
                )
            except (DummyGeneratorError, OSError) as e:
                warn(f"Refresh: could not create exe for game {game_id}: {e}")
                continue
            try:
                self.db.add_to_library(
                    game_id, str(exe_path), normalized, normalized, win_exes
                )
            except (sqlite3.Error, OSError) as e:
                warn(f"Refresh: could not update library row {game_id}: {e}")
                continue
            summary["refreshed"] += 1
            if drop_superseded and old_path is not None and old_path != exe_path:
                try:
                    if old_path.is_file():
                        old_path.unlink()
                        summary["exes_replaced"] += 1
                        self._prune_empty_parents(
                            old_path.parent,
                            self.dummy_gen.output_dir / str(game_id),
                            warn,
                        )
                except OSError as e:
                    warn(f"Refresh: could not drop old exe {old_path}: {e}")

        if self.logger:
            self.logger.info(f"Refresh candidates: {summary}")
        return summary

    @staticmethod
    def _prune_empty_parents(start: Path, stop: Path, warn) -> None:
        current = start
        while True:
            if current != stop and stop not in current.parents:
                return
            try:
                current.rmdir()
            except OSError:
                return
            if current == stop:
                return
            current = current.parent

    def repair_library(self, startup: bool = False) -> dict[str, int]:
        summary = self.startup_cleanup(reset_runtime=startup)
        refresh = self.refresh_library_candidates()
        for key, value in refresh.items():
            if key == "warnings":
                summary["warnings"] += value
            else:
                summary[f"refresh_{key}"] = value
        if self.logger:
            self.logger.info(f"Repair library: {summary}")
        return summary

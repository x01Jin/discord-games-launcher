
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from launcher.database import Database

DISCORD_API_BASE = "https://discord.com/api"
STABLE_API_VERSION = "v10"
API_VERSION_CANDIDATES: tuple[str, ...] = (STABLE_API_VERSION,)
DETECTABLE_PATH = "applications/detectable"
PROBE_TIMEOUT = 10.0

DISCORD_API_URL = f"{DISCORD_API_BASE}/{STABLE_API_VERSION}/{DETECTABLE_PATH}"
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"


def detectable_url(version: str) -> str:
    return f"{DISCORD_API_BASE}/{version}/{DETECTABLE_PATH}"


class DiscordAPIError(Exception):
    pass


class DiscordAPIClient:

    def __init__(
        self,
        database: Database,
        cache_dir: Path,
        timeout: float = 30.0,
        logger=None,
    ):
        self.db = database
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.logger = logger
        self.icons_dir = cache_dir / "icons"
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        self.last_fetch_version: str | None = None

    def sync_cache(self, force: bool = False) -> tuple[bool, int, int]:
        if not force and not self.db.needs_sync():
            stats = self.db.get_cache_stats()
            return False, stats["cached_games"], 0

        games, skipped = self._fetch_all_games_cascade()
        saved_skipped = self.db.save_games(games)
        self.db.set_last_sync(datetime.now(timezone.utc))
        return True, len(games), skipped + saved_skipped

    def _ordered_versions(self) -> list[str]:
        versions = list(API_VERSION_CANDIDATES)
        preferred = self.db.get_metadata_value("last_working_api_version")
        if preferred in versions:
            versions.remove(preferred)
            versions.insert(0, preferred)
        elif preferred and self.logger:
            self.logger.warning(
                f"Ignoring stored API version {preferred!r}: not a known candidate"
            )
        return versions

    def _fetch_all_games_cascade(self) -> tuple[list[dict[str, Any]], int]:
        errors: list[str] = []
        versions = self._ordered_versions()
        for index, version in enumerate(versions):
            timeout = self.timeout if index == 0 else PROBE_TIMEOUT
            try:
                payload = self._fetch_version(version, timeout)
            except DiscordAPIError as e:
                errors.append(f"{version}: {e}")
                continue
            games, skipped, missing = self.sanitize_games(payload)
            self._report_drift(version, len(games), skipped, missing)
            self.last_fetch_version = version
            try:
                self.db.set_metadata_value("last_working_api_version", version)
            except Exception:
                if self.logger:
                    self.logger.warning("Could not persist last working API version")
            return games, skipped
        raise DiscordAPIError(
            "All Discord API versions failed (" + "; ".join(errors) + ")"
        )

    def _fetch_version(self, version: str, timeout: float) -> Any:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(detectable_url(version))
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise DiscordAPIError("Request timed out")
        except httpx.HTTPStatusError as e:
            raise DiscordAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise DiscordAPIError(f"Request failed: {e}")
        except Exception as e:
            raise DiscordAPIError(f"Unexpected error: {e}")

    def _fetch_all_games(self) -> list[dict[str, Any]]:
        games, _skipped = self._fetch_all_games_cascade()
        return games

    @staticmethod
    def sanitize_games(
        payload: Any,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        if not isinstance(payload, list):
            raise DiscordAPIError(
                f"Unexpected API payload: expected a list, got {type(payload).__name__}"
            )
        clean: list[dict[str, Any]] = []
        skipped = 0
        missing: dict[str, int] = {"id": 0, "name": 0, "executables": 0}
        for game in payload:
            if not isinstance(game, dict):
                skipped += 1
                continue
            raw_id = game.get("id")
            if isinstance(raw_id, bool):
                skipped += 1
                continue
            try:
                game_id = int(str(raw_id))
            except (TypeError, ValueError):
                skipped += 1
                missing["id"] += 1
                continue
            if game_id <= 0:
                skipped += 1
                missing["id"] += 1
                continue
            name = game.get("name")
            if not isinstance(name, str) or not name:
                missing["name"] += 1
                name = str(name) if name is not None else ""
            executables = game.get("executables", [])
            if not isinstance(executables, list):
                missing["executables"] += 1
                executables = []
            aliases = game.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []
            themes = game.get("themes", [])
            if not isinstance(themes, list):
                themes = []
            icon_hash = game.get("icon_hash")
            if icon_hash is not None and not isinstance(icon_hash, str):
                icon_hash = None
            clean.append(
                {
                    "id": game_id,
                    "name": name,
                    "aliases": aliases,
                    "executables": executables,
                    "icon_hash": icon_hash,
                    "themes": themes,
                    "isPublished": bool(game.get("isPublished", True)),
                }
            )
        return clean, skipped, missing

    def _report_drift(
        self,
        version: str,
        kept: int,
        skipped: int,
        missing: dict[str, int],
    ) -> None:
        if self.logger is None:
            return
        total = kept + skipped
        if skipped:
            self.logger.warning(
                f"Discord API {version}: skipped {skipped}/{total} malformed records"
            )
        if total and missing.get("executables", 0) > total // 2:
            self.logger.warning(
                f"Discord API {version}: {missing['executables']}/{total} records "
                "lack executables; the upstream schema may have changed"
            )

    async def _fetch_all_games_async(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(DISCORD_API_URL)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                raise DiscordAPIError("Request timed out")
            except httpx.HTTPStatusError as e:
                raise DiscordAPIError(f"HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                raise DiscordAPIError(f"Request failed: {e}")

    def get_icon_url(self, game_id: int, icon_hash: str, size: int = 128) -> str:
        return f"{DISCORD_CDN_URL}/{game_id}/{icon_hash}.png?size={size}"

    def download_icon(
        self, game_id: int, icon_hash: str, size: int = 128
    ) -> Path | None:
        icon_path = self.icons_dir / f"{game_id}_{icon_hash}_{size}.png"

        if icon_path.exists():
            return icon_path

        url = self.get_icon_url(game_id, icon_hash, size)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
                icon_path.write_bytes(response.content)
                return icon_path
        except (httpx.HTTPError, OSError):
            return None

    async def download_icon_async(
        self, game_id: int, icon_hash: str, size: int = 128
    ) -> Path | None:
        icon_path = self.icons_dir / f"{game_id}_{icon_hash}_{size}.png"

        if icon_path.exists():
            return icon_path

        url = self.get_icon_url(game_id, icon_hash, size)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                icon_path.write_bytes(response.content)
                return icon_path
        except (httpx.HTTPError, OSError):
            return None

    @staticmethod
    def get_best_win32_executables(
        executables: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        win_executables = []

        for exe in executables:
            if exe.get("os") != "win32":
                continue

            name = exe.get("name")
            if not name:
                args = exe.get("arguments", [])
                if args and len(args) > 0:
                    path = args[0]
                    name = Path(path).name

            if not name:
                continue

            exe_copy = dict(exe)
            exe_copy["name"] = name

            score = 0

            if not exe_copy.get("is_launcher", False):
                score += 1000

            score -= len(name) * 10

            if "/" not in name and "\\" not in name:
                score += 50

            if not name.startswith("_"):
                score += 20

            exe_copy["_score"] = score
            win_executables.append(exe_copy)

        win_executables.sort(key=lambda x: x["_score"], reverse=True)

        return win_executables

    @staticmethod
    def normalize_process_name(name: str) -> str:
        if "/" in name:
            return name.split("/")[-1]
        return name

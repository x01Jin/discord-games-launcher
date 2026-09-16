"""Discord Games Launcher - API Client module.

Handles fetching and caching data from Discord's applications/detectable API.
Uses httpx for modern HTTP handling with async support.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from launcher.database import Database

# Discord API endpoint for detectable applications.
#
# Version policy: v10 is the latest stable REST version (v9 available;
# v8/v7 deprecated; older discontinued). Candidates are ordered
# latest-first: prepend a newer version when Discord ships one and the
# cascade below starts trying it automatically, falling back through
# older entries down to the stable default.
DISCORD_API_BASE = "https://discord.com/api"
STABLE_API_VERSION = "v10"
API_VERSION_CANDIDATES: tuple[str, ...] = (STABLE_API_VERSION,)
DETECTABLE_PATH = "applications/detectable"
# Shorter timeout for non-preferred cascade probes so a dead version
# fails fast; the preferred/stable attempt uses the full timeout.
PROBE_TIMEOUT = 10.0

# Stable-default endpoint (kept as an alias for compatibility).
DISCORD_API_URL = f"{DISCORD_API_BASE}/{STABLE_API_VERSION}/{DETECTABLE_PATH}"
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"


def detectable_url(version: str) -> str:
    """Build the detectable-applications URL for an API version."""
    return f"{DISCORD_API_BASE}/{version}/{DETECTABLE_PATH}"


class DiscordAPIError(Exception):
    """Raised when Discord API request fails."""


class DiscordAPIClient:
    """Client for Discord's applications API with caching support."""

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
        # API version that served the last successful fetch (None before
        # the first sync). Read by the bridge for fallback notices.
        self.last_fetch_version: str | None = None

    def sync_cache(self, force: bool = False) -> tuple[bool, int, int]:
        """Sync cache with Discord API if needed.

        Args:
            force: Force sync even if cache is fresh

        Returns:
            Tuple of (was_synced, game_count, skipped_records).
            Malformed records are skipped and counted, never fatal.
        """
        if not force and not self.db.needs_sync():
            stats = self.db.get_cache_stats()
            return False, stats["cached_games"], 0

        games, skipped = self._fetch_all_games_cascade()
        saved_skipped = self.db.save_games(games)
        self.db.set_last_sync(datetime.now(timezone.utc))
        return True, len(games), skipped + saved_skipped

    def _ordered_versions(self) -> list[str]:
        """Cascade order: last-working version first, then latest-first."""
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
        """Fetch across API versions, latest first, down to stable.

        Returns the sanitized games plus the skipped-record count.
        Raises DiscordAPIError only when every candidate fails.
        """
        errors: list[str] = []
        versions = self._ordered_versions()
        for index, version in enumerate(versions):
            # First candidate (last-working or latest) gets the full
            # timeout; the rest are probes that must fail fast.
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
            except Exception:  # noqa: BLE001 - persistence must never fail a sync
                if self.logger:
                    self.logger.warning("Could not persist last working API version")
            return games, skipped
        raise DiscordAPIError(
            "All Discord API versions failed (" + "; ".join(errors) + ")"
        )

    def _fetch_version(self, version: str, timeout: float) -> Any:
        """Fetch the raw detectable payload for one API version."""
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
        # Translation boundary: any transport failure surfaces as DiscordAPIError.
        except Exception as e:  # noqa: BLE001
            raise DiscordAPIError(f"Unexpected error: {e}")

    def _fetch_all_games(self) -> list[dict[str, Any]]:
        """Fetch all detectable applications from Discord API (stable)."""
        games, _skipped = self._fetch_all_games_cascade()
        return games

    @staticmethod
    def sanitize_games(
        payload: Any,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        """Validate a raw detectable payload.

        Unknown fields are ignored; malformed records are skipped and
        counted so one bad record can never kill a 20k-game sync.

        Returns (clean_games, skipped_count, missing_key_counters).
        """
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
        """Log schema-drift signals; loud when the payload looks alien."""
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
                "lack executables — upstream schema may have changed"
            )

    async def _fetch_all_games_async(self) -> list[dict[str, Any]]:
        """Async version of fetch_all_games."""
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
        """Generate Discord CDN URL for game icon."""
        return f"{DISCORD_CDN_URL}/{game_id}/{icon_hash}.png?size={size}"

    def download_icon(
        self, game_id: int, icon_hash: str, size: int = 128
    ) -> Path | None:
        """Download and cache game icon.

        Returns:
            Path to cached icon file, or None if download failed
        """
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
        """Async version of download_icon."""
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
        """Get all Windows executables sorted by smart scoring.

        Discord's executables array contains objects with:
        - is_launcher: bool - CRITICAL: Discord ignores launchers!
        - name: str (process name like "minecraft.exe")
        - os: str ("win32", "darwin", or "linux")
        - arguments: List[str] (optional, sometimes contains path)

        Scoring system:
        - Non-launcher: +1000 (CRITICAL - Discord ignores launchers!)
        - Shorter name: -10 per character
        - No path separators: +50 (avoid "_retail_/bg3.exe")
        - No underscore prefix: +20 (avoid "_wow.exe")

        Returns:
            List of executables sorted by score (best first)
        """
        win_executables = []

        for exe in executables:
            if exe.get("os") != "win32":
                continue

            # Try to get name from various possible locations
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

            # CRITICAL: Check if launcher (Discord ignores these!)
            if not exe_copy.get("is_launcher", False):
                score += 1000

            # Prefer shorter names
            score -= len(name) * 10

            # Prefer names without path separators
            if "/" not in name and "\\" not in name:
                score += 50

            # Prefer names not starting with underscore
            if not name.startswith("_"):
                score += 20

            exe_copy["_score"] = score
            win_executables.append(exe_copy)

        # Sort by score (descending)
        win_executables.sort(key=lambda x: x["_score"], reverse=True)

        return win_executables

    @staticmethod
    def normalize_process_name(name: str) -> str:
        """Normalize process name for Discord detection.

        Some executables have path separators like "_retail_/wow-64.exe"
        We need to extract just the executable filename.
        """
        if "/" in name:
            return name.split("/")[-1]
        return name

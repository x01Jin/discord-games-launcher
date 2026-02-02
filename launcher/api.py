"""Discord Games Launcher - API Client module.

Handles fetching and caching data from Discord's applications/detectable API.
Uses httpx for modern HTTP handling with async support.
"""

import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from launcher.database import Database


# Discord API endpoint for detectable applications
DISCORD_API_URL = "https://discord.com/api/v10/applications/detectable"
DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons"


class DiscordAPIError(Exception):
    """Raised when Discord API request fails."""

    pass


class DiscordAPIClient:
    """Client for Discord's applications API with caching support."""

    def __init__(self, database: Database, cache_dir: Path, timeout: float = 30.0):
        self.db = database
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.icons_dir = cache_dir / "icons"
        self.icons_dir.mkdir(parents=True, exist_ok=True)

    def sync_cache(self, force: bool = False) -> bool:
        """Sync cache with Discord API if needed.

        Args:
            force: Force sync even if cache is fresh

        Returns:
            True if sync was performed, False if cache is up to date
        """
        if not force and not self.db.needs_sync():
            return False

        try:
            games = self._fetch_all_games()
            self.db.save_games(games)
            self.db.set_last_sync(datetime.now())
            return True
        except DiscordAPIError as e:
            raise DiscordAPIError(f"Failed to sync cache: {e}")

    def _fetch_all_games(self) -> List[Dict[str, Any]]:
        """Fetch all detectable applications from Discord API."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(DISCORD_API_URL)
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

    async def _fetch_all_games_async(self) -> List[Dict[str, Any]]:
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
    ) -> Optional[Path]:
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
    ) -> Optional[Path]:
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
        executables: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
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

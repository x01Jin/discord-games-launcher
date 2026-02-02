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
    def get_win32_executable(
        executables: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Get the first Windows executable from the list.

        Discord's executables array contains objects with:
        - is_launcher: bool
        - name: str (process name like "overwatch.exe")
        - os: str ("win32", "darwin", or "linux")
        - arguments: List[str] (optional)
        """
        for exe in executables:
            if exe.get("os") == "win32":
                return exe
        return None

    @staticmethod
    def normalize_process_name(name: str) -> str:
        """Normalize process name for Discord detection.

        Some executables have path separators like "_retail_/wow-64.exe"
        We need to extract just the executable filename.
        """
        # Handle cases like "_retail_/wow-64.exe"
        if "/" in name:
            return name.split("/")[-1]
        return name

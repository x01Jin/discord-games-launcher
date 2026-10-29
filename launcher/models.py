from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Game:

    id: int
    name: str
    aliases: list[str]
    executables: list[dict[str, Any]]
    icon_hash: str | None
    themes: list[str]
    is_published: bool
    cached_at: datetime


@dataclass
class LibraryGame:

    game_id: int
    executable_path: str | None
    process_name: str
    normalized_process_name: str
    executables: list[dict[str, Any]]
    added_at: datetime

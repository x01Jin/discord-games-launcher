from __future__ import annotations

import json
from typing import Any

from ..errors import DiscordNativeError


def parse_quest_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise DiscordNativeError("Discord returned an unreadable quest payload") from exc
    if not isinstance(value, dict):
        raise DiscordNativeError("Discord returned an unexpected quest payload")
    if not value.get("ok"):
        raise DiscordNativeError(str(value.get("error") or "Discord could not list quests"))
    if not isinstance(value.get("quests"), list):
        value["quests"] = []
    orbs = value.get("orbs")
    if isinstance(orbs, bool) or not isinstance(orbs, int) or orbs < 0:
        value["orbs"] = None
    return value

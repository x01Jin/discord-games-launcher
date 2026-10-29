from __future__ import annotations


class DiscordNativeError(Exception):
    pass


class QuestApiError(DiscordNativeError):

    def __init__(self, message: str, captcha: bool = False):
        super().__init__(message)
        self.captcha = bool(captcha)

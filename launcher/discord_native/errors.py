from __future__ import annotations


class DiscordNativeError(Exception):
    pass


class QuestApiError(DiscordNativeError):
    def __init__(
        self,
        message: str,
        captcha: bool = False,
        code: int | str | None = None,
        status: int | None = None,
    ):
        super().__init__(message)
        self.captcha = bool(captcha)

        self.code = code
        self.status = status

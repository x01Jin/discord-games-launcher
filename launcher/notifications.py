"""Windows toast notifications for quest events.

A quest finishing is the one event worth interrupting for: the run is over, the
reward is waiting, and the next quest may not start for a while. The app window
is usually in the background by then, so the notice goes to the Action Center
the same way a game's or Discord's own notifications do.

This is a Windows toast shown by Windows PowerShell 5.1, which is the only
PowerShell that can load the WinRT notification classes on a stock install.
`powershell.exe` is launched per notification with the whole script base64
encoded, so no quoting rules, no profile, and no window flash. The script itself
is built here and passed to a runner, which keeps the formatting testable
without spawning anything.
"""

from __future__ import annotations

import base64
import os
import subprocess
from xml.sax.saxutils import escape

# Must look like a packaged app id. Windows accepts an unregistered one for
# desktop toasts, and a stable value keeps every notice grouped under the app.
APP_ID = "DCGL.DiscordGamesLauncher"

_CREATE_NO_WINDOW = 0x08000000

_SCRIPT = """
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
__PAYLOAD__
'@)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('__APP_ID__').Show($toast)
"""

_PAYLOAD = (
    '<toast><visual><binding template="ToastGeneric">'
    "<text>__TITLE__</text><text>__BODY__</text>"
    "</binding></visual></toast>"
)


def build_payload(title: str, body: str) -> str:
    """The toast XML for one notice, with both lines escaped."""
    return _PAYLOAD.replace("__TITLE__", escape(title)).replace(
        "__BODY__", escape(body)
    )


def build_command(title: str, body: str) -> str:
    """The full `powershell.exe` argument list for one toast."""
    script = _SCRIPT.replace("__PAYLOAD__", build_payload(title, body)).replace(
        "__APP_ID__", APP_ID
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return encoded


def run_powershell(encoded: str) -> None:
    """Show the toast, then return.

    Windows PowerShell, not pwsh: the WinRT type syntax below does not resolve
    in PowerShell 7. Missing powershell.exe is an OSError the caller logs.
    """
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-EncodedCommand",
            encoded,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
    )


class Notifier:
    """Quest notifications. Every failure is logged, never raised."""

    def __init__(self, logger=None, runner=None):
        self.logger = logger
        self._runner = runner or run_powershell

    def quest_finished(self, quest_name: str, reward: str | None = None) -> None:
        name = (quest_name or "Quest").strip() or "Quest"
        body = name if not reward else f"{name} · {reward}"
        self._show("Quest finished", body)

    def _show(self, title: str, body: str) -> None:
        if os.name != "nt":
            return
        try:
            self._runner(build_command(title, body))
        except (OSError, ValueError) as exc:
            self._log("warning", f"Could not show a notification: {exc}")

    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        try:
            getattr(self.logger, level)(message)
        except (AttributeError, OSError):
            pass


__all__ = ["APP_ID", "Notifier", "build_command", "build_payload", "run_powershell"]

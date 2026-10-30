from __future__ import annotations

import random
import time
from typing import Any

from launcher import prefs as quest_prefs
from launcher.discord_native import DiscordNativeError
from launcher.rpc_activity import RpcError

from .model import (
    PLAY_BEAT_SECONDS,
    PLAY_STALL_BEATS,
    PLAY_TIMEOUT_SECONDS,
    TEST_MODE_BEATS,
    derive_executable_name,
)


def _credited_seconds(result: Any) -> int | None:
    value = (result or {}).get("credited")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


class PlayMixin:
    def _mode(self) -> str:
        try:
            mode = str(self.prefs().get(quest_prefs.RUN_MODE) or "")
        except (OSError, ValueError):
            return quest_prefs.MODE_ACTIVITY
        return mode if mode in quest_prefs.RUN_MODES else quest_prefs.MODE_ACTIVITY

    def _begin_play(
        self, quest: dict[str, Any], app_id: int
    ) -> tuple[bool, str]:
        quest_id = str(quest.get("id"))
        name = str(quest.get("name") or "")
        task_key = str(quest.get("task_key") or "")
        executable = str(
            quest.get("process_name")
            or derive_executable_name(name or quest.get("game_name") or "")
        )
        target = int(quest.get("target_seconds") or 0)
        now = time.monotonic()
        try:
            first = self.native.send_heartbeat(
                quest_id, app_id, executable, task_key=task_key or None
            )
        except (DiscordNativeError, OSError) as exc:
            return False, f"Discord would not credit that quest: {exc}"
        activity = False
        if self._mode() == quest_prefs.MODE_ACTIVITY:
            activity = self._show_game(app_id, name or executable)
        with self._run_lock:
            self._playing = quest_id
            self._playing_app = app_id
            self._playing_exe = executable
            self._playing_name = name or str(quest.get("game_name") or "")
            self._playing_reward = self._reward_label(quest)
            self._playing_target = max(0, target)
            self._playing_at = now
            self._playing_task = task_key
            self._beat_next = now + PLAY_BEAT_SECONDS
            self._beats = 1
            self._idle_beats = 0
            self._last_credited = _credited_seconds(first)
            self._activity_shown = activity
        credited = _credited_seconds(first)
        if credited is not None:
            self._track_progress(quest_id, credited, target, "play")
        self.invalidate()
        self._start_monitor()
        self._changed()
        self._log(
            "info",
            (
                f"Showing the play quest {name!r} as playing with heartbeats"
                if activity
                else f"Crediting the play quest {name!r} with heartbeats"
            ),
        )
        note = self._activity_note(app_id) if activity else ""
        return True, f"Showing {name} as playing{note}" if activity else f"Crediting {name}"

    def _show_game(self, app_id: int, display: str) -> bool:
        show = getattr(self.native, "show_game_activity", None)
        if show is not None:
            try:
                show(app_id, display)
                return True
            except (DiscordNativeError, OSError) as exc:
                self._log(
                    "warning",
                    f"Could not add the game to Discord's running-game store: {exc}",
                )
        try:
            self._rpc.show(app_id, display)
            return True
        except (RpcError, OSError) as exc:
            self._log("warning", f"Could not show the game as playing: {exc}")
            return False

    def _activity_note(self, app_id: int) -> str:
        state = getattr(self.native, "activity_state", None)
        if state is None:
            return ""
        try:
            values = state(app_id)
        except (DiscordNativeError, OSError, ValueError):
            return ""
        if not isinstance(values, dict) or values.get("shown") is not False:
            return ""
        self._log(
            "warning",
            f"Discord is not holding the playing game for application {app_id}, "
            "so the profile card stays empty",
        )
        return " · Discord did not take the game activity"

    def _check_play(self, now: float) -> None:
        with self._run_lock:
            quest_id = self._playing
            app_id = self._playing_app
            executable = self._playing_exe
            task_key = getattr(self, "_playing_task", "")
            target = self._playing_target
            started = self._playing_at
            beat_next = self._beat_next
        if quest_id is None or app_id is None:
            return
        if now - started > PLAY_TIMEOUT_SECONDS:
            self._stop_playing("Stopped the quest session after four hours")
            return
        if now < beat_next:
            return
        with self._run_lock:
            self._beat_next = now + PLAY_BEAT_SECONDS
        try:
            result = self.native.send_heartbeat(
                quest_id, app_id, executable, task_key=task_key or None
            )
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not beat the quest session: {exc}")
            return

        with self._run_lock:
            if self._playing != quest_id:
                return
        completed = bool(result.get("completed"))
        credited = _credited_seconds(result)
        if not completed and credited is not None and target > 0 and credited >= target:
            completed = True
        if credited is not None:
            self._track_progress(quest_id, credited, target, "play")
        with self._run_lock:
            self._beats = getattr(self, "_beats", 0) + 1
            beats = self._beats
            previous = self._last_credited

            if not completed and credited is not None and previous is not None:
                self._idle_beats = (
                    getattr(self, "_idle_beats", 0) + 1 if credited <= previous else 0
                )
            elif completed:
                self._idle_beats = 0
            idle_beats = getattr(self, "_idle_beats", 0)
            if credited is not None:
                self._last_credited = credited
            name = self._playing_name

        if completed:
            with self._run_lock:
                reward = self._playing_reward
            self._notify_finished(name, reward, quest_id)
            self._stop_playing("Quest finished, starting the next one", close=False)
            return

        if idle_beats >= PLAY_STALL_BEATS:
            self._log(
                "warning",
                f"Discord stopped crediting {name!r} after {beats} beat(s); "
                "stopping the run instead of waiting out the timeout",
            )
            self._stop_playing(
                "Discord is not crediting this quest", close=True, tail=False
            )
            return

        if self._test_mode() and beats >= TEST_MODE_BEATS:
            self._log(
                "info",
                f"Test mode: collected {beats} credited beat(s) for {name!r}, "
                "stopping before the quest finishes",
            )
            self._stop_playing("Test mode: quest left unfinished", close=True, tail=False)

    def _hide_activity(self) -> None:
        with self._run_lock:
            self._activity_shown = False
        self._clear_activity()

    def _clear_activity(self) -> None:
        clear = getattr(self.native, "clear_game_activity", None)
        if clear is not None:
            try:
                clear()
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Could not withdraw the running game: {exc}")
        try:
            self._rpc.hide()
        except OSError as exc:
            self._log("warning", f"Could not clear the playing activity: {exc}")

    def _stop_playing(
        self, message: str, close: bool = True, tail: bool = True
    ) -> None:
        with self._run_lock:
            quest_id = self._playing
            app_id = self._playing_app
            executable = self._playing_exe
            if quest_id is None:
                return
            shown = self._activity_shown
            self._playing = None
            self._playing_app = None
            self._playing_exe = ""
            self._playing_name = ""
            self._playing_reward = None
            self._playing_target = 0
            self._playing_at = 0.0
            self._playing_task = ""
            self._beat_next = 0.0
            self._beats = 0
            self._idle_beats = 0
            self._last_credited = None
            self._activity_shown = False
        self._forget_progress(quest_id)
        if shown:
            self._clear_activity()
        if close and app_id is not None:
            try:
                self.native.send_heartbeat(quest_id, app_id, executable, terminal=True)
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Could not close the quest session: {exc}")
        tail_minutes = int(self.prefs().get(quest_prefs.PLAY_SESSION_TAIL_MIN) or 0)
        if tail and tail_minutes > 0:
            upper = tail_minutes * 60.0
            self._play_ready_at = time.monotonic() + random.uniform(
                min(10.0, upper), upper
            )
        else:
            self._play_ready_at = 0.0
        self.invalidate()
        self._log("info", message)
        self._changed()
        self._pump()

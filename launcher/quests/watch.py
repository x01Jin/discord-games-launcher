from __future__ import annotations

import random

from launcher.discord_native import DiscordNativeError

from .model import TEST_MODE_VIDEO_POSTS, WATCH_REFRESH_SECONDS, WATCH_TIMEOUT_SECONDS


class WatchMixin:
    def _check_watch(self, now: float) -> None:
        with self._run_lock:
            quest_id = self._watching
            started = self._watching_at
            checked_at = self._watch_checked_at
        if quest_id is None:
            return
        if now - started > WATCH_TIMEOUT_SECONDS:
            self._stop_watching(
                quest_id, "Stopped waiting: the video quest did not finish"
            )
            return

        self._watch_step(now)
        with self._run_lock:
            if self._watching != quest_id:
                return
        if now - checked_at < WATCH_REFRESH_SECONDS:
            return
        with self._run_lock:
            self._watch_checked_at = now
        try:
            payload = self._refresh(force=True)
        except (DiscordNativeError, OSError):
            return
        quest = next(
            (
                raw
                for raw in payload.get("quests") or []
                if str(raw.get("id")) == quest_id
            ),
            None,
        )
        if quest is None:
            self._stop_watching(quest_id, "The waiting quest is gone from Discord")
            return
        try:
            target = int(quest.get("target") or 0)
            progress = int(quest.get("progress") or 0)
        except (TypeError, ValueError):
            return
        if quest.get("completedAt") or (target > 0 and progress >= target):
            with self._run_lock:
                name = self._watching_name
                reward = self._watching_reward
            self._notify_finished(name, reward, quest_id)
            self._stop_watching(quest_id, "Video quest finished, starting the next one")

    def _watch_step(self, now: float) -> None:
        with self._run_lock:
            quest_id = self._watching
            if quest_id is None or now < self._watch_next:
                return
            task_key = getattr(self, "_watching_task", "")
            target = getattr(self, "_watching_target", 0)
            elapsed = max(0.0, min(now - self._watch_last, 15.0))
            self._watch_last = now
            self._watch_seconds += elapsed
            self._watch_next = now + random.uniform(7.0, 9.5)
            self._watch_posts = getattr(self, "_watch_posts", 0) + 1
            posts = self._watch_posts
            seconds = self._watch_seconds
        try:
            result = self.native.send_video_progress(
                quest_id, seconds, task_key=task_key or None
            )
        except (DiscordNativeError, OSError) as exc:
            self._log("warning", f"Could not report video progress: {exc}")
            return
        credited = result.get("credited")
        self._track_progress(
            quest_id, credited if credited is not None else seconds, target, "video"
        )
        if result.get("completed"):
            with self._run_lock:
                name = self._watching_name
                reward = self._watching_reward
            self._notify_finished(name, reward, quest_id)
            self._stop_watching(quest_id, "Video quest finished, starting the next one")
            return
        if self._test_mode() and posts >= TEST_MODE_VIDEO_POSTS:
            with self._run_lock:
                name = self._watching_name
            self._log(
                "info",
                f"Test mode: posted {posts} video progress value(s) for {name!r}, "
                "stopping before the quest finishes",
            )
            self._stop_watching(quest_id, "Test mode: quest left unfinished")

    def _stop_watching(self, quest_id: str, message: str) -> None:
        with self._run_lock:
            if self._watching != quest_id:
                return
            self._watching = None
            self._watching_name = ""
            self._watching_reward = None
            self._watching_task = ""
            self._watching_target = 0
            self._watch_posts = 0
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0
        self._forget_progress(quest_id)
        self.invalidate()
        self._log("info", message)
        self._changed()
        self._pump()

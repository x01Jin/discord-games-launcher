from __future__ import annotations

import random
import time

from launcher.discord_native import DiscordNativeError


class QueueMixin:
    def _enqueue(self, quest_id: str) -> bool:
        with self._run_lock:
            if quest_id in self._queue:
                return False
            self._queue.append(quest_id)
        self.invalidate()
        return True

    def start_queue(self, quest_ids: list[str]) -> tuple[bool, str]:
        if not isinstance(quest_ids, (list, tuple)):
            return False, "Invalid quest selection"
        wanted: list[str] = []
        for raw in quest_ids:
            if not isinstance(raw, str):
                continue
            quest_id = raw.strip()
            if quest_id and quest_id not in wanted:
                wanted.append(quest_id)
        if not wanted:
            return False, "Select at least one quest"

        accepted: list[str] = []
        skipped = 0
        for quest_id in wanted:
            quest = self._find(quest_id)
            with self._run_lock:
                running = quest_id == self._watching or quest_id == self._playing
            if quest is None or running:
                skipped += 1
                continue
            kind = quest.get("kind")
            ready = quest.get("state") == "ready"
            can_play = kind == "play" and ready
            can_watch = kind in ("watch", "watch_mobile") and ready
            if can_play or can_watch:
                accepted.append(quest_id)
            else:
                skipped += 1

        if not accepted:
            return False, (
                "None of the selected quests can run. Pick unfinished play or "
                "video quests."
            )

        with self._run_lock:
            for quest_id in accepted:
                if quest_id not in self._queue:
                    self._queue.append(quest_id)
        self._pump()
        message = f"Queued {len(accepted)} quest(s)"
        if skipped:
            message += f", skipped {skipped} that cannot run"
        return True, message

    def clear_queue(self) -> int:
        with self._run_lock:
            count = len(self._queue) + (1 if self._watching else 0)
            self._queue.clear()
            self._watching = None
            self._watch_seconds = 0.0
            self._watch_last = 0.0
            self._watch_next = 0.0
            self._watch_checked_at = 0.0
        return count

    def skip_watch(self) -> tuple[bool, str]:
        with self._run_lock:
            quest_id = self._watching
        if quest_id is None:
            return False, "Nothing is waiting on a video"
        self._stop_watching(quest_id, "Skipped the waiting video")
        return True, "Skipped the video and moved on"

    def reorder_queue(self, quest_ids: list[str]) -> tuple[bool, str]:
        if not isinstance(quest_ids, (list, tuple)):
            return False, "Invalid queue order"
        with self._run_lock:
            current = list(self._queue)
            if not current:
                return False, "The queue is empty"
            order: list[str] = []
            for raw in quest_ids:
                if not isinstance(raw, str):
                    continue
                quest_id = raw.strip()
                if quest_id in current and quest_id not in order:
                    order.append(quest_id)
            if not order:
                return False, "No queued quest in that order"
            order.extend(quest_id for quest_id in current if quest_id not in order)
            if order == current:
                return True, "The queue is already in that order"
            self._queue[:] = order
        return True, "Queue reordered"

    def drop_queue_item(self, quest_id: str) -> tuple[bool, str]:
        with self._run_lock:
            if quest_id not in self._queue:
                return False, "That quest is not waiting in the queue"
            self._queue.remove(quest_id)
            left = len(self._queue)
        return True, f"Removed it from the queue, {left} left"

    def _next_queued(self, kind: str, skip: str | None = None) -> str | None:
        with self._run_lock:
            pending = list(self._queue)
        for quest_id in pending:
            if quest_id == skip:
                continue
            quest = self._find(quest_id)
            if quest is None:
                continue
            quest_kind = quest.get("kind")
            if quest_kind == kind or (kind == "watch" and quest_kind == "watch_mobile"):
                return quest_id
        return None

    def _pump(self) -> None:
        self._start_watching()
        self._start_playing()

    def _start_watching(self) -> bool:
        with self._run_lock:
            if self._watching is not None:
                return False
        quest_id = self._next_queued("watch")
        if quest_id is None:
            return False
        quest = self._find(quest_id) or {}
        if not quest.get("enrolled"):
            try:
                self.native.accept_quest(quest_id)
            except (DiscordNativeError, OSError) as exc:
                self._log("warning", f"Queued video quest could not be accepted: {exc}")
        now = time.monotonic()
        with self._run_lock:
            if quest_id in self._queue:
                self._queue.remove(quest_id)
            self._watching = quest_id
            self._watching_name = str(quest.get("name") or "")
            self._watching_reward = self._reward_label(quest)
            self._watching_at = now
            self._watch_seconds = 0.0
            self._watch_last = now
            self._watch_next = now + random.uniform(7.0, 9.5)
            self._watch_checked_at = now
        self.invalidate()
        self._start_monitor()
        self._log(
            "info",
            f"Watching the video quest {quest.get('name')!r} in the background",
        )
        self._changed()
        return True

    def _start_playing(self) -> bool:
        with self._run_lock:
            if self._playing is not None:
                return False
            if time.monotonic() < self._play_ready_at:
                return False
        quest_id = self._next_queued("play")
        if quest_id is None:
            return False
        try:
            ok, message = self.start_quest(quest_id)
        except (DiscordNativeError, OSError, ValueError) as exc:
            ok, message = False, str(exc)
        if ok:
            with self._run_lock:
                if quest_id in self._queue:
                    self._queue.remove(quest_id)
            return True
        self._log("warning", f"Queued quest did not start: {message}")
        return False

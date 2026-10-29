from __future__ import annotations

import threading
import time


class MonitorMixin:
    def _start_monitor(self) -> None:
        if not self._monitor_enabled:
            return
        with self._run_lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="dcgl-quest-run",
                daemon=True,
            )
            self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.is_set():
            with self._run_lock:
                busy = self._watching is not None or self._playing is not None
            if self._monitor_stop.wait(2.0 if busy else self.MONITOR_INTERVAL):
                break
            try:
                self._monitor_tick(time.monotonic())
            except Exception as exc:
                self._log("warning", f"Quest monitor error: {exc}")
            with self._run_lock:
                if (
                    self._playing is None
                    and not self._queue
                    and self._watching is None
                ):
                    break

    def _monitor_tick(self, now: float) -> None:
        self._check_play(now)
        self._check_watch(now)
        self._pump()


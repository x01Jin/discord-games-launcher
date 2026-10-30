from __future__ import annotations

import threading
import time


class MonitorMixin:
    MONITOR_INTERVAL = 20.0

    def _start_monitor(self) -> None:
        if not self._monitor_enabled:
            return
        with self._run_lock:
            thread = self._monitor_thread
            if thread is None or not thread.is_alive():
                self._monitor_stop.clear()
                self._monitor_thread = threading.Thread(
                    target=self._monitor_loop,
                    name="dcgl-quest-run",
                    daemon=True,
                )
                self._monitor_thread.start()

        self._monitor_wake.set()

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.is_set():
            with self._run_lock:
                busy = self._watching is not None or self._playing is not None
            self._monitor_wake.wait(1.0 if busy else self.MONITOR_INTERVAL)
            self._monitor_wake.clear()
            if self._monitor_stop.is_set():
                break
            try:
                self._monitor_tick(time.monotonic())
            except Exception as exc:
                self._log("warning", f"Quest monitor error: {exc}")

    def _monitor_tick(self, now: float) -> None:
        self._check_play(now)
        self._check_watch(now)
        self._pump()
        self._push_progress(now)

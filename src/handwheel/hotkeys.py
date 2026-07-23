from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable


def windows_f8_down() -> bool:
    if not hasattr(ctypes, "windll"):
        return False
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)


class EmergencyHotkeyMonitor(threading.Thread):
    """Poll F8 outside the GUI thread and directly invoke the neutral latch."""

    def __init__(
        self,
        on_emergency: Callable[[], None],
        *,
        key_reader: Callable[[], bool] = windows_f8_down,
        poll_seconds: float = 0.01,
    ) -> None:
        super().__init__(name="handwheel-emergency-hotkey", daemon=True)
        self._on_emergency = on_emergency
        self._key_reader = key_reader
        self._poll_seconds = poll_seconds
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        was_down = False
        while not self._stop_event.is_set():
            try:
                is_down = bool(self._key_reader())
                if is_down and not was_down:
                    self._on_emergency()
                was_down = is_down
            except Exception:
                was_down = False
            self._stop_event.wait(self._poll_seconds)

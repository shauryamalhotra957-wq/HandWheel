from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ControllerStatus:
    available: bool
    armed: bool
    message: str


def preview_only_requested() -> bool:
    if os.environ.get("HANDWHEEL_PREVIEW_ONLY") == "1":
        return True
    candidates = {Path.cwd() / ".preview-only"}
    try:
        candidates.add(Path(__file__).resolve().parents[2] / ".preview-only")
    except IndexError:
        pass
    return any(path.is_file() for path in candidates)


class ControllerLoop(threading.Thread):
    """Owns the virtual pad and applies a watchdog independently of camera FPS."""

    def __init__(self, rate_hz: float = 100.0, watchdog_seconds: float = 0.3):
        super().__init__(name="handwheel-controller", daemon=True)
        self._rate_hz = rate_hz
        self._watchdog_seconds = watchdog_seconds
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._target = 0.0
        self._last_publish = 0.0
        self._armed = False
        self._available = False
        self._message = "Controller is starting…"

    def status(self) -> ControllerStatus:
        with self._lock:
            return ControllerStatus(
                available=self._available,
                armed=self._armed,
                message=self._message,
            )

    def wait_until_ready(self, timeout: float = 3.0) -> ControllerStatus:
        self._ready_event.wait(timeout)
        return self.status()

    def publish(self, steering: float) -> None:
        with self._lock:
            self._target = max(-1.0, min(float(steering), 1.0))
            self._last_publish = time.monotonic()

    def set_armed(self, armed: bool) -> bool:
        with self._lock:
            self._armed = bool(armed and self._available)
            if not self._armed:
                self._target = 0.0
            return self._armed

    def toggle_armed(self) -> bool:
        with self._lock:
            self._armed = bool(self._available and not self._armed)
            if not self._armed:
                self._target = 0.0
            return self._armed

    def neutralize(self) -> None:
        with self._lock:
            self._target = 0.0
            self._armed = False

    def stop(self) -> None:
        self.neutralize()
        self._stop_event.set()

    def shutdown(self, timeout: float = 2.0) -> None:
        self.stop()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=timeout)

    def run(self) -> None:
        gamepad = None
        vg = None
        try:
            try:
                if preview_only_requested():
                    raise RuntimeError(
                        "controller output disabled by preview-only mode"
                    )
                import vgamepad as imported_vgamepad

                vg = imported_vgamepad
                gamepad = vg.VX360Gamepad()
                gamepad.reset()
                gamepad.update()
                with self._lock:
                    self._available = True
                    self._message = "Virtual Xbox controller ready"
            except Exception as error:
                with self._lock:
                    self._available = False
                    self._armed = False
                    self._message = (
                        "Preview only — virtual controller unavailable: "
                        f"{type(error).__name__}"
                    )
            finally:
                self._ready_event.set()

            period = 1.0 / self._rate_hz
            last_sent: float | None = None
            last_refresh = 0.0
            while not self._stop_event.is_set():
                started = time.monotonic()
                with self._lock:
                    armed = self._armed
                    target = self._target
                    last_publish = self._last_publish
                stale = started - last_publish > self._watchdog_seconds
                if armed and stale:
                    with self._lock:
                        self._armed = False
                        self._target = 0.0
                        self._message = (
                            "Output disarmed — camera/controller watchdog timed out"
                        )
                    armed = False
                output = target if armed and not stale else 0.0

                if gamepad is not None and (
                    last_sent is None
                    or abs(output - last_sent) >= 0.001
                    or started - last_refresh >= 0.1
                ):
                    gamepad.left_joystick_float(x_value_float=output, y_value_float=0.0)
                    gamepad.left_trigger_float(value_float=0.0)
                    gamepad.right_trigger_float(value_float=0.0)
                    gamepad.update()
                    last_sent = output
                    last_refresh = started

                elapsed = time.monotonic() - started
                self._stop_event.wait(max(0.0, period - elapsed))
        except Exception as error:
            with self._lock:
                self._available = False
                self._armed = False
                self._target = 0.0
                self._message = f"Controller stopped: {type(error).__name__}"
        finally:
            if gamepad is not None:
                try:
                    gamepad.reset()
                    gamepad.update()
                except Exception:
                    pass
            with self._lock:
                self._available = False
                self._armed = False
                self._target = 0.0

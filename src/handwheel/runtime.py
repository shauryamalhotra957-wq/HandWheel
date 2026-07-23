from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from handwheel.config import AppConfig, default_config_path, save_config
from handwheel.steering import TrackingState


@dataclass(frozen=True, slots=True)
class Telemetry:
    camera_running: bool = False
    tracking_state: TrackingState = TrackingState.LOST
    steering: float = 0.0
    target_steering: float = 0.0
    angle_deg: float | None = None
    hands_detected: int = 0
    fps: float = 0.0
    message: str = "Starting…"
    calibration_progress: float = 0.0
    calibrated: bool = False


class SharedState:
    def __init__(self, config: AppConfig, config_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._config = config.validated()
        self._config_path = config_path or default_config_path()
        self._telemetry = Telemetry(calibrated=self._config.calibrated)
        self._frame: Any | None = None
        self._frame_version = 0
        self._calibration_requested = threading.Event()
        self._notice = ""

    def config(self) -> AppConfig:
        with self._lock:
            return replace(self._config)

    def update_config(self, **changes: object) -> AppConfig:
        with self._lock:
            for key, value in changes.items():
                if not hasattr(self._config, key):
                    raise AttributeError(key)
                setattr(self._config, key, value)
            self._config = self._config.validated()
            return replace(self._config)

    def set_calibration(self, angle_rad: float, spacing: float) -> AppConfig:
        return self.update_config(
            neutral_angle_rad=angle_rad,
            neutral_spacing=spacing,
        )

    def save(self) -> Path:
        with self._save_lock:
            with self._lock:
                snapshot = replace(self._config)
            return save_config(snapshot, self._config_path)

    def request_calibration(self) -> None:
        self._calibration_requested.set()

    def consume_calibration_request(self) -> bool:
        if self._calibration_requested.is_set():
            self._calibration_requested.clear()
            return True
        return False

    def publish(
        self,
        telemetry: Telemetry,
        frame: Any | None = None,
    ) -> None:
        with self._lock:
            self._telemetry = telemetry
            if frame is not None:
                self._frame = frame
                self._frame_version += 1

    def snapshot(self) -> tuple[Telemetry, Any | None, int, str]:
        with self._lock:
            notice = self._notice
            self._notice = ""
            return (
                self._telemetry,
                self._frame,
                self._frame_version,
                notice,
            )

    def clear_frame(self) -> None:
        with self._lock:
            self._frame = None
            self._frame_version += 1

    def set_notice(self, message: str) -> None:
        with self._lock:
            self._notice = message

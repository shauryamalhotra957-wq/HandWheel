from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppConfig:
    camera_index: int = 0
    camera_width: int = 960
    camera_height: int = 540
    mirror: bool = True
    invert: bool = False
    steering_range_deg: float = 60.0
    deadzone: float = 0.04
    response_curve: float = 1.15
    smoothing_ms: float = 75.0
    min_hand_distance: float = 0.08
    grace_ms: float = 120.0
    center_return_ms: float = 280.0
    neutral_angle_rad: float | None = None
    neutral_spacing: float | None = None

    @property
    def calibrated(self) -> bool:
        return (
            self.neutral_angle_rad is not None
            and self.neutral_spacing is not None
            and self.neutral_spacing > 0
        )

    def validated(self) -> "AppConfig":
        config = replace(self)
        config.camera_index = max(0, min(int(config.camera_index), 10))
        config.camera_width = max(320, min(int(config.camera_width), 1920))
        config.camera_height = max(240, min(int(config.camera_height), 1080))
        config.steering_range_deg = max(
            25.0, min(float(config.steering_range_deg), 100.0)
        )
        config.deadzone = max(0.0, min(float(config.deadzone), 0.25))
        config.response_curve = max(0.6, min(float(config.response_curve), 2.0))
        config.smoothing_ms = max(10.0, min(float(config.smoothing_ms), 300.0))
        config.min_hand_distance = max(0.03, min(float(config.min_hand_distance), 0.3))
        config.grace_ms = max(0.0, min(float(config.grace_ms), 500.0))
        config.center_return_ms = max(50.0, min(float(config.center_return_ms), 1000.0))
        if config.neutral_angle_rad is not None and not math.isfinite(
            config.neutral_angle_rad
        ):
            config.neutral_angle_rad = None
        if config.neutral_spacing is not None and (
            not math.isfinite(config.neutral_spacing) or config.neutral_spacing <= 0
        ):
            config.neutral_spacing = None
        return config


def default_config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "HandWheel" / "config.json"
    return Path.cwd() / ".handwheel-config.json"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    if not target.exists():
        return AppConfig()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        allowed = {field.name for field in fields(AppConfig)}
        values: dict[str, Any] = {
            key: value for key, value in payload.items() if key in allowed
        }
        return AppConfig(**values).validated()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(asdict(config.validated()), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target

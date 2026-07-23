from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from handwheel.config import AppConfig


Point = tuple[float, float]
Vector = tuple[float, float]


class TrackingState(str, Enum):
    NEEDS_CALIBRATION = "NEEDS CALIBRATION"
    REACQUIRING = "REACQUIRING"
    TRACKING = "TRACKING"
    GRACE = "BRIEF LOSS"
    LOST = "TRACKING LOST"


@dataclass(frozen=True, slots=True)
class AxisMeasurement:
    angle_rad: float
    spacing: float
    vector: Vector


@dataclass(frozen=True, slots=True)
class SteeringOutput:
    value: float
    target: float
    angle_rad: float | None
    spacing: float | None
    state: TrackingState
    valid_hands: bool


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def signed_angle_delta(angle: float, reference: float) -> float:
    return (angle - reference + math.pi) % (2.0 * math.pi) - math.pi


def circular_mean(angles: Sequence[float]) -> float:
    if not angles:
        raise ValueError("at least one angle is required")
    sine = sum(math.sin(value) for value in angles)
    cosine = sum(math.cos(value) for value in angles)
    return math.atan2(sine, cosine)


def circular_deviation(angles: Sequence[float]) -> float:
    if len(angles) < 2:
        return 0.0
    center = circular_mean(angles)
    return statistics.pstdev(signed_angle_delta(value, center) for value in angles)


def apply_deadzone(value: float, deadzone: float) -> float:
    value = clamp(value, -1.0, 1.0)
    deadzone = clamp(deadzone, 0.0, 0.99)
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return math.copysign(scaled, value)


def measure_axis(
    points: Sequence[Point],
    *,
    reference_vector: Vector | None = None,
    min_distance: float = 0.08,
    expected_spacing: float | None = None,
) -> AxisMeasurement | None:
    if len(points) != 2:
        return None
    dx = points[1][0] - points[0][0]
    dy = points[1][1] - points[0][1]
    spacing = math.hypot(dx, dy)
    if spacing < min_distance:
        return None
    if expected_spacing is not None and (
        spacing < expected_spacing * 0.35 or spacing > expected_spacing * 2.8
    ):
        return None

    if reference_vector is not None:
        if dx * reference_vector[0] + dy * reference_vector[1] < 0:
            dx, dy = -dx, -dy
    elif dx < 0:
        dx, dy = -dx, -dy

    unit = (dx / spacing, dy / spacing)
    return AxisMeasurement(
        angle_rad=math.atan2(unit[1], unit[0]),
        spacing=spacing,
        vector=unit,
    )


class SteeringEngine:
    def __init__(self) -> None:
        self._last_timestamp: float | None = None
        self._last_valid_timestamp: float | None = None
        self._last_vector: Vector | None = None
        self._last_target = 0.0
        self._value = 0.0
        self._good_frames = 0
        self._recent_deltas: deque[float] = deque(maxlen=3)

    @property
    def value(self) -> float:
        return self._value

    def reset(self) -> None:
        self._last_timestamp = None
        self._last_valid_timestamp = None
        self._last_vector = None
        self._last_target = 0.0
        self._value = 0.0
        self._good_frames = 0
        self._recent_deltas.clear()

    def set_calibration(self, angle_rad: float, spacing: float) -> None:
        self._last_vector = (math.cos(angle_rad), math.sin(angle_rad))
        self._last_target = 0.0
        self._value = 0.0
        self._good_frames = 0
        self._recent_deltas.clear()

    def update(
        self,
        points: Sequence[Point] | None,
        timestamp: float,
        config: AppConfig,
    ) -> SteeringOutput:
        dt = (
            1.0 / 30.0
            if self._last_timestamp is None
            else clamp(timestamp - self._last_timestamp, 0.001, 0.25)
        )
        self._last_timestamp = timestamp

        reference = self._last_vector
        if reference is None and config.neutral_angle_rad is not None:
            reference = (
                math.cos(config.neutral_angle_rad),
                math.sin(config.neutral_angle_rad),
            )
        measurement = (
            measure_axis(
                points,
                reference_vector=reference,
                min_distance=config.min_hand_distance,
                expected_spacing=config.neutral_spacing,
            )
            if points is not None
            else None
        )

        if measurement is None:
            return self._on_tracking_loss(timestamp, dt, config)

        self._last_vector = measurement.vector
        self._last_valid_timestamp = timestamp
        self._good_frames += 1

        if not config.calibrated:
            self._value = 0.0
            self._last_target = 0.0
            return SteeringOutput(
                value=0.0,
                target=0.0,
                angle_rad=measurement.angle_rad,
                spacing=measurement.spacing,
                state=TrackingState.NEEDS_CALIBRATION,
                valid_hands=True,
            )

        delta = signed_angle_delta(
            measurement.angle_rad, float(config.neutral_angle_rad)
        )
        self._recent_deltas.append(delta)
        filtered_delta = statistics.median(self._recent_deltas)
        normalized = clamp(
            filtered_delta / math.radians(config.steering_range_deg), -1.0, 1.0
        )
        if config.invert:
            normalized = -normalized
        target = apply_deadzone(normalized, config.deadzone)
        target = math.copysign(abs(target) ** config.response_curve, target)

        if self._good_frames < 3:
            self._last_target = target
            return SteeringOutput(
                value=self._value,
                target=target,
                angle_rad=measurement.angle_rad,
                spacing=measurement.spacing,
                state=TrackingState.REACQUIRING,
                valid_hands=True,
            )

        speed = abs(target - self._last_target) / dt
        slow_tau = config.smoothing_ms / 1000.0
        fast_tau = max(0.018, slow_tau * 0.42)
        rapid_motion = clamp(speed / 4.0, 0.0, 1.0)
        tau = slow_tau + (fast_tau - slow_tau) * rapid_motion
        alpha = 1.0 - math.exp(-dt / max(tau, 0.001))
        self._value += alpha * (target - self._value)
        self._value = clamp(self._value, -1.0, 1.0)
        self._last_target = target

        return SteeringOutput(
            value=self._value,
            target=target,
            angle_rad=measurement.angle_rad,
            spacing=measurement.spacing,
            state=TrackingState.TRACKING,
            valid_hands=True,
        )

    def _on_tracking_loss(
        self, timestamp: float, dt: float, config: AppConfig
    ) -> SteeringOutput:
        self._good_frames = 0
        missing_for = (
            math.inf
            if self._last_valid_timestamp is None
            else timestamp - self._last_valid_timestamp
        )
        if missing_for <= config.grace_ms / 1000.0:
            state = TrackingState.GRACE
        else:
            state = TrackingState.LOST
            return_seconds = max(config.center_return_ms / 1000.0, 0.05)
            step = dt / return_seconds
            if abs(self._value) <= step:
                self._value = 0.0
            else:
                self._value -= math.copysign(step, self._value)
            self._last_target = 0.0
            self._recent_deltas.clear()
            if config.neutral_angle_rad is not None:
                self._last_vector = (
                    math.cos(config.neutral_angle_rad),
                    math.sin(config.neutral_angle_rad),
                )
            else:
                self._last_vector = None

        return SteeringOutput(
            value=self._value,
            target=self._last_target,
            angle_rad=None,
            spacing=None,
            state=state,
            valid_hands=False,
        )

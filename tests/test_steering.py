import math

import pytest

from handwheel.config import AppConfig
from handwheel.steering import (
    SteeringEngine,
    TrackingState,
    apply_deadzone,
    measure_axis,
    signed_angle_delta,
)


def point_pair(angle_deg: float, spacing: float = 0.4):
    angle = math.radians(angle_deg)
    return [
        (0.3, 0.5),
        (0.3 + math.cos(angle) * spacing, 0.5 + math.sin(angle) * spacing),
    ]


def calibrated_config(**updates):
    config = AppConfig(
        neutral_angle_rad=0.0,
        neutral_spacing=0.4,
        steering_range_deg=60.0,
        deadzone=0.0,
        response_curve=1.0,
        smoothing_ms=10.0,
    )
    for key, value in updates.items():
        setattr(config, key, value)
    return config


def test_signed_angle_delta_wraps_across_pi():
    result = signed_angle_delta(math.radians(-179), math.radians(179))
    assert math.degrees(result) == pytest.approx(2.0)


def test_axis_measurement_does_not_jump_when_detector_order_swaps():
    points = point_pair(30)
    first = measure_axis(points)
    assert first is not None
    swapped = measure_axis(list(reversed(points)), reference_vector=first.vector)
    assert swapped is not None
    assert swapped.angle_rad == pytest.approx(first.angle_rad)


def test_deadzone_is_removed_and_remaining_range_is_rescaled():
    assert apply_deadzone(0.04, 0.05) == 0.0
    assert apply_deadzone(-0.04, 0.05) == 0.0
    assert apply_deadzone(1.0, 0.05) == 1.0
    assert apply_deadzone(-1.0, 0.05) == -1.0


def test_clockwise_image_rotation_maps_to_positive_xinput():
    engine = SteeringEngine()
    config = calibrated_config()
    output = None
    for frame in range(8):
        output = engine.update(point_pair(30), frame / 30.0, config)
    assert output is not None
    assert output.state is TrackingState.TRACKING
    assert output.value > 0.35


def test_invert_option_reverses_output():
    engine = SteeringEngine()
    config = calibrated_config(invert=True)
    output = None
    for frame in range(8):
        output = engine.update(point_pair(30), frame / 30.0, config)
    assert output is not None
    assert output.value < -0.35


def test_tracking_loss_holds_briefly_then_returns_to_center():
    engine = SteeringEngine()
    config = calibrated_config(grace_ms=100, center_return_ms=200)
    for frame in range(8):
        output = engine.update(point_pair(50), frame / 30.0, config)
    before_loss = output.value

    brief = engine.update(None, 8 / 30.0, config)
    assert brief.state is TrackingState.GRACE
    assert brief.value == pytest.approx(before_loss)

    lost = engine.update(None, 0.5, config)
    assert lost.state is TrackingState.LOST
    for index in range(20):
        lost = engine.update(None, 0.5 + (index + 1) / 30.0, config)
    assert lost.value == 0.0


def test_reacquisition_does_not_emit_a_first_frame_jump():
    engine = SteeringEngine()
    config = calibrated_config(grace_ms=0, center_return_ms=100)
    engine.update(None, 0.0, config)
    first = engine.update(point_pair(55), 1.0, config)
    second = engine.update(point_pair(55), 1.0 + 1 / 30.0, config)
    third = engine.update(point_pair(55), 1.0 + 2 / 30.0, config)

    assert first.state is TrackingState.REACQUIRING
    assert second.state is TrackingState.REACQUIRING
    assert first.value == 0.0
    assert second.value == 0.0
    assert third.state is TrackingState.TRACKING
    assert 0.0 < third.value < 0.9


def test_long_loss_resets_endpoint_orientation_to_calibrated_axis():
    engine = SteeringEngine()
    config = calibrated_config(grace_ms=0, center_return_ms=100)
    for frame in range(5):
        engine.update(point_pair(45), frame / 30.0, config)
    for frame in range(20):
        engine.update(None, 0.5 + frame / 30.0, config)

    reversed_points = list(reversed(point_pair(-60)))
    first = engine.update(reversed_points, 2.0, config)
    second = engine.update(reversed_points, 2.0 + 1 / 30.0, config)
    third = engine.update(reversed_points, 2.0 + 2 / 30.0, config)

    assert first.value == 0.0
    assert second.value == 0.0
    assert third.state is TrackingState.TRACKING
    assert third.value < 0.0


def test_uncalibrated_engine_never_emits_steering():
    engine = SteeringEngine()
    output = engine.update(point_pair(25), 0.0, AppConfig())
    assert output.state is TrackingState.NEEDS_CALIBRATION
    assert output.value == 0.0

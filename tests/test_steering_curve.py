import pytest
from handwheel.steering_curve import SteeringCurveMapper

def test_deadzone_clamping():
    mapper = SteeringCurveMapper(deadzone=0.08)
    assert mapper.map_input(0.0) == 0.0
    assert mapper.map_input(0.05) == 0.0
    assert mapper.map_input(-0.07) == 0.0

def test_full_lock():
    mapper = SteeringCurveMapper(deadzone=0.05, max_output=1.0)
    assert mapper.map_input(1.0) == 1.0
    assert mapper.map_input(-1.0) == -1.0
    # Over-range input clamped
    assert mapper.map_input(1.5) == 1.0

def test_progressive_curve():
    mapper = SteeringCurveMapper(deadzone=0.0, exponent=2.0)
    # At half input (0.5), output should be 0.5^2 = 0.25 (progressive finesse)
    assert mapper.map_input(0.5) == 0.25
    assert mapper.map_input(-0.5) == -0.25

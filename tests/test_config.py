import json

from handwheel.config import AppConfig, load_config, save_config


def test_config_validation_clamps_unsafe_values():
    config = AppConfig(
        camera_index=-4,
        steering_range_deg=500,
        deadzone=-1,
        smoothing_ms=0,
    ).validated()
    assert config.camera_index == 0
    assert config.steering_range_deg == 100
    assert config.deadzone == 0
    assert config.smoothing_ms == 10


def test_config_round_trip(tmp_path):
    target = tmp_path / "config.json"
    original = AppConfig(
        invert=True,
        neutral_angle_rad=0.1,
        neutral_spacing=0.42,
    )
    save_config(original, target)
    loaded = load_config(target)
    assert loaded.invert is True
    assert loaded.neutral_angle_rad == 0.1
    assert loaded.neutral_spacing == 0.42


def test_unknown_config_fields_are_ignored(tmp_path):
    target = tmp_path / "config.json"
    target.write_text(json.dumps({"deadzone": 0.1, "future_option": 123}))
    loaded = load_config(target)
    assert loaded.deadzone == 0.1

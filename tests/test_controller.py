import sys
import time
import types

from handwheel.controller import ControllerLoop


class FakeGamepad:
    instances = []

    def __init__(self):
        self.values = []
        FakeGamepad.instances.append(self)

    def reset(self):
        self.values.append(0.0)

    def update(self):
        pass

    def left_joystick_float(self, *, x_value_float, y_value_float):
        assert y_value_float == 0.0
        self.values.append(x_value_float)

    def left_trigger_float(self, *, value_float):
        assert value_float == 0.0

    def right_trigger_float(self, *, value_float):
        assert value_float == 0.0


def wait_for(predicate, timeout=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_watchdog_neutralizes_and_latches_disarmed(monkeypatch):
    FakeGamepad.instances.clear()
    monkeypatch.delenv("HANDWHEEL_PREVIEW_ONLY", raising=False)
    monkeypatch.setitem(
        sys.modules, "vgamepad", types.SimpleNamespace(VX360Gamepad=FakeGamepad)
    )
    controller = ControllerLoop(rate_hz=200.0, watchdog_seconds=0.05)
    controller.start()
    try:
        assert controller.wait_until_ready().available
        controller.publish(0.8)
        assert controller.set_armed(True)
        assert wait_for(
            lambda: (
                FakeGamepad.instances
                and any(value > 0.7 for value in FakeGamepad.instances[0].values)
            )
        )
        assert wait_for(lambda: not controller.status().armed)
        assert FakeGamepad.instances[0].values[-1] == 0.0
    finally:
        controller.stop()
        controller.join(timeout=1.0)


def test_preview_only_environment_prevents_controller_creation(monkeypatch):
    FakeGamepad.instances.clear()
    monkeypatch.setenv("HANDWHEEL_PREVIEW_ONLY", "1")
    monkeypatch.setitem(
        sys.modules, "vgamepad", types.SimpleNamespace(VX360Gamepad=FakeGamepad)
    )
    controller = ControllerLoop()
    controller.start()
    try:
        status = controller.wait_until_ready()
        assert status.available is False
        assert status.armed is False
        assert FakeGamepad.instances == []
    finally:
        controller.stop()
        controller.join(timeout=1.0)


def test_preview_only_marker_prevents_controller_creation(monkeypatch, tmp_path):
    FakeGamepad.instances.clear()
    monkeypatch.delenv("HANDWHEEL_PREVIEW_ONLY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".preview-only").write_text("disabled")
    monkeypatch.setitem(
        sys.modules, "vgamepad", types.SimpleNamespace(VX360Gamepad=FakeGamepad)
    )
    controller = ControllerLoop()
    controller.start()
    try:
        status = controller.wait_until_ready()
        assert status.available is False
        assert FakeGamepad.instances == []
    finally:
        controller.stop()
        controller.join(timeout=1.0)

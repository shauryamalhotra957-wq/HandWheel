import sys
import types

from handwheel.camera import CameraWorker
from handwheel.steering import TrackingState


class FakeController:
    def __init__(self):
        self.neutralizations = 0

    def neutralize(self):
        self.neutralizations += 1


class FakeState:
    def __init__(self):
        self.telemetry = []
        self.frame_cleared = False
        self._config = types.SimpleNamespace(
            calibrated=True,
            camera_index=0,
            camera_width=640,
            camera_height=480,
            mirror=True,
        )

    def config(self):
        return self._config

    def publish(self, telemetry, frame=None):
        self.telemetry.append(telemetry)

    def clear_frame(self):
        self.frame_cleared = True


class FakeCapture:
    def __init__(self, *, opened, returns_frame=False):
        self.opened = opened
        self.returns_frame = returns_frame
        self.released = False

    def isOpened(self):
        return self.opened

    def set(self, *_args):
        return True

    def read(self):
        return self.returns_frame, object() if self.returns_frame else None

    def release(self):
        self.released = True


def assert_failed_safely(state, controller, message):
    assert controller.neutralizations == 1
    assert state.frame_cleared is True
    telemetry = state.telemetry[-1]
    assert telemetry.camera_running is False
    assert telemetry.tracking_state is TrackingState.LOST
    assert telemetry.steering == 0.0
    assert telemetry.message == message


def test_model_failure_neutralizes_output(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "mediapipe", types.SimpleNamespace())

    def fail_model(*_args, **_kwargs):
        raise RuntimeError("model failed")

    monkeypatch.setattr("handwheel.camera.ensure_model", fail_model)
    state = FakeState()
    controller = FakeController()

    CameraWorker(state, controller).run()

    assert_failed_safely(state, controller, "model failed")


def test_camera_open_failure_neutralizes_output_and_releases_captures(monkeypatch):
    captures = []

    def video_capture(*_args):
        capture = FakeCapture(opened=False)
        captures.append(capture)
        return capture

    fake_cv2 = types.SimpleNamespace(CAP_MSMF=1, VideoCapture=video_capture)
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", types.SimpleNamespace())
    monkeypatch.setattr("handwheel.camera.ensure_model", lambda **_kwargs: "model")
    state = FakeState()
    controller = FakeController()

    CameraWorker(state, controller).run()

    assert_failed_safely(
        state,
        controller,
        "Could not open camera 0. Close other camera apps and try again.",
    )
    assert len(captures) == 2
    assert all(capture.released for capture in captures)


def test_hand_tracking_failure_neutralizes_output_and_releases_camera(monkeypatch):
    capture = FakeCapture(opened=True, returns_frame=True)
    fake_cv2 = types.SimpleNamespace(
        CAP_MSMF=1,
        CAP_PROP_FRAME_WIDTH=2,
        CAP_PROP_FRAME_HEIGHT=3,
        CAP_PROP_FPS=4,
        CAP_PROP_BUFFERSIZE=5,
        COLOR_BGR2RGB=6,
        VideoCapture=lambda *_args: capture,
        flip=lambda frame, _axis: frame,
        cvtColor=lambda frame, _conversion: frame,
    )

    class FailingDetector:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def detect_for_video(self, *_args):
            raise RuntimeError("hand tracking failed")

    landmarker = types.SimpleNamespace(
        create_from_options=lambda _options: FailingDetector()
    )
    vision = types.SimpleNamespace(
        HandLandmarkerOptions=lambda **kwargs: kwargs,
        RunningMode=types.SimpleNamespace(VIDEO=1),
        HandLandmarker=landmarker,
    )
    fake_mp = types.SimpleNamespace(
        tasks=types.SimpleNamespace(
            BaseOptions=lambda **kwargs: kwargs,
            vision=vision,
        ),
        Image=lambda **kwargs: kwargs,
        ImageFormat=types.SimpleNamespace(SRGB=1),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", fake_mp)
    monkeypatch.setattr("handwheel.camera.ensure_model", lambda **_kwargs: "model")
    state = FakeState()
    controller = FakeController()

    CameraWorker(state, controller).run()

    assert_failed_safely(state, controller, "hand tracking failed")
    assert capture.released is True

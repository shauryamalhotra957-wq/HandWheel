from __future__ import annotations

import math
import statistics
import threading
import time
from collections import deque
from typing import Any

from handwheel.controller import ControllerLoop
from handwheel.model import ensure_model
from handwheel.runtime import SharedState, Telemetry
from handwheel.steering import (
    SteeringEngine,
    TrackingState,
    circular_deviation,
    circular_mean,
)


HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (5, 9),
    (9, 13),
    (13, 17),
)
PALM_INDICES = (0, 5, 9, 13, 17)


class CameraWorker(threading.Thread):
    def __init__(self, state: SharedState, controller: ControllerLoop):
        super().__init__(name="handwheel-camera", daemon=True)
        self._state = state
        self._controller = controller
        self._stop_event = threading.Event()
        self._engine = SteeringEngine()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = None
        failure_message: str | None = None
        try:
            import cv2
            import mediapipe as mp

            config = self._state.config()
            self._state.publish(
                Telemetry(
                    message="Loading hand-tracking model…",
                    calibrated=config.calibrated,
                )
            )
            path = ensure_model(download=True)

            cap = cv2.VideoCapture(config.camera_index, cv2.CAP_MSMF)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(config.camera_index)
            if not cap.isOpened():
                raise RuntimeError(
                    f"Could not open camera {config.camera_index}. "
                    "Close other camera apps and try again."
                )
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )

            started = time.monotonic()
            last_timestamp_ms = -1
            frame_times: deque[float] = deque(maxlen=30)
            calibration_angles: list[float] = []
            calibration_spacings: list[float] = []
            calibration_active = False
            calibration_started = 0.0
            calibration_message = ""

            with mp.tasks.vision.HandLandmarker.create_from_options(
                options
            ) as detector:
                while not self._stop_event.is_set():
                    ok, frame = cap.read()
                    now = time.monotonic()
                    if not ok or frame is None:
                        raise RuntimeError("The camera stopped returning frames.")

                    config = self._state.config()
                    tracking_frame = cv2.flip(frame, 1)
                    display_frame = tracking_frame if config.mirror else frame
                    rgb = cv2.cvtColor(tracking_frame, cv2.COLOR_BGR2RGB)
                    timestamp_ms = max(
                        last_timestamp_ms + 1, int((now - started) * 1000)
                    )
                    last_timestamp_ms = timestamp_ms
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = detector.detect_for_video(mp_image, timestamp_ms)

                    landmarks, centers = self._extract_hands(result)
                    output = self._engine.update(centers, now, config)
                    self._controller.publish(output.value)

                    if self._state.consume_calibration_request():
                        calibration_active = True
                        calibration_started = now
                        calibration_angles.clear()
                        calibration_spacings.clear()
                        calibration_message = "Hold your hands level and still"

                    if calibration_active:
                        if output.valid_hands and output.angle_rad is not None:
                            calibration_angles.append(output.angle_rad)
                            calibration_spacings.append(float(output.spacing))
                        if len(calibration_angles) >= 24:
                            recent_angles = calibration_angles[-24:]
                            if circular_deviation(recent_angles) <= math.radians(8.0):
                                neutral = circular_mean(recent_angles)
                                spacing = statistics.median(calibration_spacings[-24:])
                                config = self._state.set_calibration(neutral, spacing)
                                self._engine.set_calibration(neutral, spacing)
                                try:
                                    self._state.save()
                                except OSError:
                                    calibration_message = (
                                        "Center calibrated; settings could not be saved"
                                    )
                                calibration_active = False
                                if not calibration_message.startswith(
                                    "Center calibrated;"
                                ):
                                    calibration_message = "Center calibrated"
                            else:
                                calibration_angles = calibration_angles[-8:]
                                calibration_spacings = calibration_spacings[-8:]
                                calibration_message = "Keep both hands still"
                        elif now - calibration_started > 7.0:
                            calibration_active = False
                            calibration_message = (
                                "Calibration timed out — keep both hands visible"
                            )

                    frame_times.append(now)
                    fps = 0.0
                    if len(frame_times) >= 2:
                        duration = frame_times[-1] - frame_times[0]
                        if duration > 0:
                            fps = (len(frame_times) - 1) / duration

                    overlay = self._draw_overlay(
                        display_frame,
                        landmarks,
                        centers,
                        output.value,
                        output.state,
                        cv2,
                        flip_landmark_x=not config.mirror,
                    )
                    progress = (
                        min(len(calibration_angles) / 24.0, 1.0)
                        if calibration_active
                        else 0.0
                    )
                    message = calibration_message or self._state_message(output.state)
                    self._state.publish(
                        Telemetry(
                            camera_running=True,
                            tracking_state=output.state,
                            steering=output.value,
                            target_steering=output.target,
                            angle_deg=(
                                math.degrees(output.angle_rad)
                                if output.angle_rad is not None
                                else None
                            ),
                            hands_detected=len(landmarks),
                            fps=fps,
                            message=message,
                            calibration_progress=progress,
                            calibrated=config.calibrated,
                        ),
                        overlay,
                    )
                    calibration_message = (
                        calibration_message if calibration_active else ""
                    )
        except Exception as error:
            failure_message = str(error)
            self._controller.publish(0.0)
            config = self._state.config()
            self._state.publish(
                Telemetry(
                    camera_running=False,
                    tracking_state=TrackingState.LOST,
                    steering=0.0,
                    message=str(error),
                    calibrated=config.calibrated,
                )
            )
        finally:
            self._controller.publish(0.0)
            self._controller.set_armed(False)
            if cap is not None:
                cap.release()
            config = self._state.config()
            self._state.clear_frame()
            self._state.publish(
                Telemetry(
                    camera_running=False,
                    tracking_state=TrackingState.LOST,
                    steering=0.0,
                    message=failure_message or "Camera stopped",
                    calibrated=config.calibrated,
                )
            )

    @staticmethod
    def _extract_hands(
        result: Any,
    ) -> tuple[list[list[Any]], list[tuple[float, float]] | None]:
        accepted: list[list[Any]] = []
        for index, hand in enumerate(result.hand_landmarks):
            score = 1.0
            if index < len(result.handedness) and result.handedness[index]:
                score = float(result.handedness[index][0].score)
            if score >= 0.5:
                accepted.append(hand)

        centers: list[tuple[float, float]] | None = None
        if len(accepted) == 2:
            centers = []
            for hand in accepted:
                centers.append(
                    (
                        sum(hand[index].x for index in PALM_INDICES)
                        / len(PALM_INDICES),
                        sum(hand[index].y for index in PALM_INDICES)
                        / len(PALM_INDICES),
                    )
                )
        return accepted, centers

    @staticmethod
    def _state_message(state: TrackingState) -> str:
        return {
            TrackingState.NEEDS_CALIBRATION: "Two hands found — calibrate center",
            TrackingState.REACQUIRING: "Reacquiring both hands…",
            TrackingState.TRACKING: "Tracking both hands",
            TrackingState.GRACE: "Brief tracking loss",
            TrackingState.LOST: "Show both hands to the camera",
        }[state]

    @staticmethod
    def _draw_overlay(
        frame: Any,
        hands: list[list[Any]],
        centers: list[tuple[float, float]] | None,
        steering: float,
        state: TrackingState,
        cv2: Any,
        *,
        flip_landmark_x: bool = False,
    ) -> Any:
        height, width = frame.shape[:2]
        overlay = frame.copy()
        for hand in hands:
            pixels = [
                (
                    int(
                        (
                            1.0 - max(0.0, min(point.x, 1.0))
                            if flip_landmark_x
                            else max(0.0, min(point.x, 1.0))
                        )
                        * width
                    ),
                    int(max(0.0, min(point.y, 1.0)) * height),
                )
                for point in hand
            ]
            for start, end in HAND_CONNECTIONS:
                cv2.line(
                    overlay, pixels[start], pixels[end], (125, 230, 188), 2, cv2.LINE_AA
                )
            for point in pixels:
                cv2.circle(overlay, point, 3, (245, 249, 255), -1, cv2.LINE_AA)

        if centers is not None:
            center_pixels = [
                (
                    int((1.0 - point[0] if flip_landmark_x else point[0]) * width),
                    int(point[1] * height),
                )
                for point in centers
            ]
            cv2.line(
                overlay,
                center_pixels[0],
                center_pixels[1],
                (65, 180, 255),
                6,
                cv2.LINE_AA,
            )
            for point in center_pixels:
                cv2.circle(overlay, point, 11, (65, 180, 255), -1, cv2.LINE_AA)
                cv2.circle(overlay, point, 5, (255, 255, 255), -1, cv2.LINE_AA)

        gauge_left = 28
        gauge_right = width - 28
        gauge_y = height - 34
        cv2.line(
            overlay,
            (gauge_left, gauge_y),
            (gauge_right, gauge_y),
            (88, 97, 112),
            8,
            cv2.LINE_AA,
        )
        center_x = (gauge_left + gauge_right) // 2
        marker_x = int(center_x + steering * (gauge_right - gauge_left) / 2)
        cv2.circle(overlay, (marker_x, gauge_y), 11, (65, 180, 255), -1, cv2.LINE_AA)

        color = {
            TrackingState.TRACKING: (125, 230, 188),
            TrackingState.REACQUIRING: (65, 180, 255),
            TrackingState.NEEDS_CALIBRATION: (65, 180, 255),
            TrackingState.GRACE: (75, 196, 255),
            TrackingState.LOST: (99, 105, 230),
        }[state]
        cv2.rectangle(overlay, (20, 18), (260, 56), (18, 22, 30), -1)
        cv2.circle(overlay, (40, 37), 7, color, -1, cv2.LINE_AA)
        cv2.putText(
            overlay,
            state.value,
            (56, 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (240, 244, 250),
            1,
            cv2.LINE_AA,
        )
        return overlay

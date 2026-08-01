from __future__ import annotations

import atexit
import ctypes
import math
import signal
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from handwheel.camera import CameraWorker
from handwheel.config import load_config
from handwheel.controller import ControllerLoop
from handwheel.hotkeys import EmergencyHotkeyMonitor
from handwheel.runtime import SharedState
from handwheel.steering import TrackingState


BG = "#0f1218"
PANEL = "#171c25"
PANEL_2 = "#202735"
TEXT = "#f1f5fb"
MUTED = "#9aa6b6"
ACCENT = "#41b4ff"
GOOD = "#7de6bc"
WARN = "#ffc44b"
DANGER = "#e66970"


class SteeringGauge(tk.Canvas):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(
            master,
            width=310,
            height=96,
            bg=PANEL,
            highlightthickness=0,
        )
        self._value = 0.0
        self.bind("<Configure>", lambda _event: self._draw())

    def set_value(self, value: float) -> None:
        self._value = max(-1.0, min(float(value), 1.0))
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 310)
        center_x = width / 2
        center_y = 72
        radius = 57
        self.create_arc(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            start=20,
            extent=140,
            style="arc",
            outline="#3b4658",
            width=10,
        )
        angle = math.radians(90 - self._value * 70)
        needle_x = center_x + math.cos(angle) * (radius - 8)
        needle_y = center_y - math.sin(angle) * (radius - 8)
        self.create_line(
            center_x,
            center_y,
            needle_x,
            needle_y,
            fill=ACCENT,
            width=5,
            capstyle=tk.ROUND,
        )
        self.create_oval(
            center_x - 8,
            center_y - 8,
            center_x + 8,
            center_y + 8,
            fill=TEXT,
            outline="",
        )
        self.create_text(
            18,
            75,
            text="LEFT",
            anchor="w",
            fill=MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        self.create_text(
            width - 18,
            75,
            text="RIGHT",
            anchor="e",
            fill=MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        self.create_text(
            center_x,
            18,
            text=f"{self._value * 100:+.0f}%",
            fill=TEXT,
            font=("Segoe UI", 13, "bold"),
        )


class HandWheelApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HandWheel")
        self.root.configure(bg=BG)
        self.root.geometry("1280x780")
        self.root.minsize(1040, 680)

        self.config = load_config()
        self.state = SharedState(self.config)
        self.controller = ControllerLoop()
        self.controller.start()
        self.controller.wait_until_ready()
        self.camera_worker: CameraWorker | None = None
        self._last_frame_version = -1
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._save_after: str | None = None
        self._closing = False
        self._f9_down = False
        self.emergency_hotkey: EmergencyHotkeyMonitor | None = None

        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if not hasattr(ctypes, "windll"):
            self.root.bind("<F8>", lambda _event: self._emergency_neutral())
            self.root.bind("<F9>", lambda _event: self._calibrate())
        else:
            self.emergency_hotkey = EmergencyHotkeyMonitor(self._emergency_neutral)
            self.emergency_hotkey.start()
        self.root.after(100, self.start_camera)
        self.root.after(33, self._poll)
        self.root.after(70, self._poll_global_hotkeys)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TScale",
            background=PANEL,
            troughcolor="#30394a",
            sliderthickness=18,
        )
        style.configure(
            "TCheckbutton",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 10),
        )
        style.map(
            "TCheckbutton",
            background=[("active", PANEL)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=ACCENT,
            troughcolor="#30394a",
            bordercolor="#30394a",
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BG, height=74)
        header.pack(fill="x", padx=26, pady=(18, 10))
        tk.Label(
            header,
            text="HANDWHEEL",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 23, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="WEBCAM → XBOX STEERING",
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(14, 0), pady=(10, 0))
        self.controller_label = tk.Label(
            header,
            text="CHECKING CONTROLLER",
            bg=PANEL_2,
            fg=MUTED,
            padx=13,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        )
        self.controller_label.pack(side="right", pady=7)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 22))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        preview_panel = tk.Frame(body, bg=PANEL)
        preview_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        preview_panel.grid_rowconfigure(0, weight=1)
        preview_panel.grid_columnconfigure(0, weight=1)
        self.preview_label = tk.Label(
            preview_panel,
            text="Starting camera…",
            bg="#090c11",
            fg=MUTED,
            font=("Segoe UI", 15),
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        footer = tk.Frame(preview_panel, bg=PANEL)
        footer.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 15))
        footer.grid_columnconfigure(1, weight=1)
        self.status_dot = tk.Label(
            footer, text="●", bg=PANEL, fg=DANGER, font=("Segoe UI", 14)
        )
        self.status_dot.grid(row=0, column=0, sticky="w")
        self.status_label = tk.Label(
            footer,
            text="Starting…",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        self.status_label.grid(row=0, column=1, sticky="ew", padx=(7, 12))
        self.fps_label = tk.Label(
            footer,
            text="0 FPS",
            bg=PANEL,
            fg=MUTED,
            font=("Cascadia Mono", 9),
        )
        self.fps_label.grid(row=0, column=2, sticky="e")
        self.calibration_progress = ttk.Progressbar(
            footer,
            mode="determinate",
            maximum=1.0,
            style="Horizontal.TProgressbar",
        )
        self.calibration_progress.grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(9, 0)
        )

        controls = tk.Frame(body, bg=PANEL, width=350)
        controls.grid(row=0, column=1, sticky="ns")
        controls.grid_propagate(False)
        controls.grid_columnconfigure(0, weight=1)

        self.gauge = SteeringGauge(controls)
        self.gauge.grid(row=0, column=0, sticky="ew", padx=20, pady=(13, 0))

        action_frame = tk.Frame(controls, bg=PANEL)
        action_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 14))
        action_frame.grid_columnconfigure((0, 1), weight=1)
        self.calibrate_button = self._button(
            action_frame, "CALIBRATE", self._calibrate, secondary=True
        )
        self.calibrate_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.arm_button = self._button(
            action_frame, "ARM OUTPUT", self._toggle_arm, secondary=False
        )
        self.arm_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.camera_button = self._button(
            controls, "STOP CAMERA", self._toggle_camera, secondary=True
        )
        self.camera_button.grid(row=2, column=0, sticky="ew", padx=20)

        camera_row = tk.Frame(controls, bg=PANEL)
        camera_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 0))
        camera_row.grid_columnconfigure(0, weight=1)
        tk.Label(
            camera_row,
            text="CAMERA INDEX  ·  RESTART TO APPLY",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.camera_index_var = tk.IntVar(value=self.config.camera_index)
        camera_picker = ttk.Spinbox(
            camera_row,
            from_=0,
            to=10,
            width=4,
            justify="center",
            textvariable=self.camera_index_var,
            command=self._camera_changed,
        )
        camera_picker.grid(row=0, column=1, sticky="e")
        camera_picker.bind("<Return>", lambda _event: self._camera_changed())
        camera_picker.bind("<FocusOut>", lambda _event: self._camera_changed())

        divider = tk.Frame(controls, bg="#30394a", height=1)
        divider.grid(row=4, column=0, sticky="ew", padx=20, pady=15)

        self.range_var = tk.DoubleVar(value=self.config.steering_range_deg)
        self.deadzone_var = tk.DoubleVar(value=self.config.deadzone * 100)
        self.smoothing_var = tk.DoubleVar(value=self.config.smoothing_ms)
        self.curve_var = tk.DoubleVar(value=self.config.response_curve)
        row = 5
        row = self._slider(
            controls,
            row,
            "STEERING RANGE",
            self.range_var,
            25,
            100,
            lambda value: f"{float(value):.0f}°",
            "steering_range_deg",
        )
        row = self._slider(
            controls,
            row,
            "CENTER DEAD ZONE",
            self.deadzone_var,
            0,
            20,
            lambda value: f"{float(value):.0f}%",
            "deadzone",
            scale=0.01,
        )
        row = self._slider(
            controls,
            row,
            "SMOOTHING",
            self.smoothing_var,
            10,
            220,
            lambda value: f"{float(value):.0f} ms",
            "smoothing_ms",
        )
        row = self._slider(
            controls,
            row,
            "RESPONSE CURVE",
            self.curve_var,
            0.7,
            1.8,
            lambda value: f"{float(value):.2f}",
            "response_curve",
        )

        toggles = tk.Frame(controls, bg=PANEL)
        toggles.grid(row=row, column=0, sticky="ew", padx=20, pady=(5, 0))
        self.invert_var = tk.BooleanVar(value=self.config.invert)
        self.mirror_var = tk.BooleanVar(value=self.config.mirror)
        ttk.Checkbutton(
            toggles,
            text="Invert steering",
            variable=self.invert_var,
            command=lambda: self._update_setting("invert", bool(self.invert_var.get())),
        ).pack(side="left")
        ttk.Checkbutton(
            toggles,
            text="Mirror camera",
            variable=self.mirror_var,
            command=lambda: self._update_setting("mirror", bool(self.mirror_var.get())),
        ).pack(side="right")

        self.help_label = tk.Label(
            controls,
            text="F8  emergency neutral\nF9  recalibrate center",
            justify="left",
            bg=PANEL_2,
            fg=MUTED,
            padx=14,
            pady=11,
            font=("Cascadia Mono", 9),
        )
        self.help_label.grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(16, 0))

    def _button(
        self,
        master: tk.Misc,
        text: str,
        command: object,
        *,
        secondary: bool,
    ) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=PANEL_2 if secondary else ACCENT,
            fg=TEXT if secondary else "#071018",
            activebackground="#2a3444" if secondary else "#76caff",
            activeforeground=TEXT if secondary else "#071018",
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _slider(
        self,
        master: tk.Misc,
        row: int,
        title: str,
        variable: tk.DoubleVar,
        minimum: float,
        maximum: float,
        formatter: object,
        config_key: str,
        *,
        scale: float = 1.0,
    ) -> int:
        header = tk.Frame(master, bg=PANEL)
        header.grid(row=row, column=0, sticky="ew", padx=20)
        header.grid_columnconfigure(0, weight=1)
        tk.Label(
            header,
            text=title,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8, "bold"),
        ).grid(row=0, column=0, sticky="w")
        value_label = tk.Label(
            header,
            text=formatter(variable.get()),
            bg=PANEL,
            fg=TEXT,
            font=("Cascadia Mono", 9, "bold"),
        )
        value_label.grid(row=0, column=1, sticky="e")

        def changed(raw_value: str) -> None:
            numeric = float(raw_value)
            value_label.configure(text=formatter(numeric))
            self._update_setting(config_key, numeric * scale)

        ttk.Scale(
            master,
            from_=minimum,
            to=maximum,
            variable=variable,
            command=changed,
            orient="horizontal",
        ).grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(2, 10))
        return row + 2

    def start_camera(self) -> None:
        if self.camera_worker is not None and self.camera_worker.is_alive():
            return
        self.camera_worker = CameraWorker(self.state, self.controller)
        self.camera_worker.start()
        self.camera_button.configure(text="STOP CAMERA")

    def stop_camera(self) -> None:
        self.controller.neutralize()
        if self.camera_worker is not None:
            worker = self.camera_worker
            worker.stop()
            worker.join(timeout=2.0)
            if worker.is_alive():
                self.state.set_notice(
                    "Camera is still shutting down; wait before restarting it."
                )
            else:
                self.camera_worker = None
                self.state.clear_frame()
        if self.camera_worker is None:
            self.camera_button.configure(text="START CAMERA")

    def _toggle_camera(self) -> None:
        if self.camera_worker is not None and self.camera_worker.is_alive():
            self.stop_camera()
        else:
            self.start_camera()

    def _camera_changed(self) -> None:
        try:
            camera_index = max(0, min(int(self.camera_index_var.get()), 10))
        except (tk.TclError, ValueError):
            camera_index = self.state.config().camera_index
        self.camera_index_var.set(camera_index)
        self._update_setting("camera_index", camera_index)
        self.state.set_notice(
            f"Camera {camera_index} selected. Restart the camera to apply."
        )

    def _calibrate(self) -> None:
        if self.camera_worker is None or not self.camera_worker.is_alive():
            self.state.set_notice("Start the camera before calibrating.")
            return
        self.controller.set_armed(False)
        self.state.request_calibration()
        self.state.set_notice("Hold both hands level and still.")

    def _toggle_arm(self) -> None:
        telemetry, _frame, _version, _notice = self.state.snapshot()
        controller = self.controller.status()
        if controller.armed:
            self.controller.set_armed(False)
            self.state.set_notice("Output neutralized.")
            return
        if not controller.available:
            self.state.set_notice(
                "Virtual controller unavailable. Install ViGEmBus 1.22, then restart."
            )
            return
        if not telemetry.camera_running:
            self.state.set_notice("Start the camera before arming.")
            return
        if not telemetry.calibrated:
            self.state.set_notice("Calibrate center before arming.")
            return
        if telemetry.tracking_state is not TrackingState.TRACKING:
            self.state.set_notice(
                "Keep both hands visible until status is TRACKING, then arm."
            )
            return
        self.controller.set_armed(True)
        self.state.set_notice("Controller output armed. Press F8 to neutralize.")

    def _emergency_neutral(self) -> None:
        self.controller.neutralize()
        self.state.set_notice("Emergency neutral — controller output disarmed.")

    def _update_setting(self, key: str, value: object) -> None:
        self.state.update_config(**{key: value})
        if self._save_after is not None:
            self.root.after_cancel(self._save_after)
        self._save_after = self.root.after(350, self._save_settings)

    def _save_settings(self) -> None:
        self._save_after = None
        try:
            self.state.save()
        except OSError:
            self.state.set_notice("Could not save settings.")

    def _poll(self) -> None:
        if self._closing:
            return
        telemetry, frame, version, notice = self.state.snapshot()
        controller = self.controller.status()
        self.gauge.set_value(telemetry.steering)

        status_color = {
            TrackingState.TRACKING: GOOD,
            TrackingState.REACQUIRING: WARN,
            TrackingState.NEEDS_CALIBRATION: WARN,
            TrackingState.GRACE: WARN,
            TrackingState.LOST: DANGER,
        }[telemetry.tracking_state]
        self.status_dot.configure(fg=status_color)
        self.status_label.configure(text=notice or telemetry.message)
        self.fps_label.configure(
            text=f"{telemetry.fps:>4.0f} FPS  ·  {telemetry.hands_detected} HANDS"
        )
        self.calibration_progress["value"] = telemetry.calibration_progress

        if controller.armed:
            self.arm_button.configure(
                text="NEUTRALIZE", bg=DANGER, activebackground="#f28b91"
            )
        else:
            self.arm_button.configure(
                text="ARM OUTPUT", bg=ACCENT, activebackground="#76caff"
            )

        if controller.available:
            self.controller_label.configure(text="●  XBOX OUTPUT", fg=GOOD, bg=PANEL_2)
        else:
            self.controller_label.configure(text="●  PREVIEW ONLY", fg=WARN, bg=PANEL_2)

        if not telemetry.camera_running and (
            self.camera_worker is None or not self.camera_worker.is_alive()
        ):
            self.camera_button.configure(text="START CAMERA")

        if frame is not None and version != self._last_frame_version:
            self._last_frame_version = version
            self._display_frame(frame)
        elif not telemetry.camera_running and frame is None:
            self.preview_label.configure(text=telemetry.message, image="")

        self.root.after(33, self._poll)

    def _display_frame(self, frame: object) -> None:
        try:
            import cv2

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            box_width = max(self.preview_label.winfo_width() - 16, 320)
            box_height = max(self.preview_label.winfo_height() - 16, 240)
            image.thumbnail((box_width, box_height), Image.Resampling.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self._preview_photo, text="")
        except Exception as error:
            self.preview_label.configure(text=f"Preview error: {error}", image="")

    def _poll_global_hotkeys(self) -> None:
        if self._closing:
            return
        if hasattr(ctypes, "windll"):
            try:
                f9_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x78) & 0x8000)
                if f9_down and not self._f9_down:
                    self._calibrate()
                self._f9_down = f9_down
            except Exception:
                pass
        self.root.after(70, self._poll_global_hotkeys)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.controller.neutralize()
        if self.emergency_hotkey is not None:
            self.emergency_hotkey.stop()
            self.emergency_hotkey.join(timeout=1.0)
        self.stop_camera()
        self.controller.shutdown(timeout=2.0)
        try:
            self.state.save()
        except OSError:
            pass
        self.root.destroy()


def _enable_windows_dpi_awareness() -> None:
    if hasattr(ctypes, "windll"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main() -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    app = HandWheelApp(root)
    atexit.register(app.controller.shutdown)

    def handle_signal(_signum: int, _frame: object) -> None:
        root.after(0, app.close)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    root.mainloop()


if __name__ == "__main__":
    main()

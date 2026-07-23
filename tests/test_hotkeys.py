import threading
import time

from handwheel.hotkeys import EmergencyHotkeyMonitor


def test_emergency_hotkey_runs_without_gui_event_loop():
    pressed = False
    fired = threading.Event()

    def key_reader():
        return pressed

    monitor = EmergencyHotkeyMonitor(
        fired.set, key_reader=key_reader, poll_seconds=0.002
    )
    monitor.start()
    try:
        pressed = True
        assert fired.wait(0.25)
    finally:
        monitor.stop()
        monitor.join(timeout=1.0)


def test_held_key_fires_only_once_until_released():
    pressed = False
    count = 0
    lock = threading.Lock()
    release_observed = threading.Event()
    second_fire = threading.Event()

    def key_reader():
        if not pressed:
            release_observed.set()
        return pressed

    def on_emergency():
        nonlocal count
        with lock:
            count += 1
            if count == 2:
                second_fire.set()

    monitor = EmergencyHotkeyMonitor(
        on_emergency, key_reader=key_reader, poll_seconds=0.002
    )
    monitor.start()
    try:
        pressed = True
        time.sleep(0.03)
        with lock:
            assert count == 1
        release_observed.clear()
        pressed = False
        assert release_observed.wait(0.25)
        pressed = True
        assert second_fire.wait(0.25)
        with lock:
            assert count == 2
    finally:
        monitor.stop()
        monitor.join(timeout=1.0)

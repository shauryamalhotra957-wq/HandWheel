# HandWheel

[![CI](https://github.com/shauryamalhotra957-wq/HandWheel/actions/workflows/ci.yml/badge.svg)](https://github.com/shauryamalhotra957-wq/HandWheel/actions) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


HandWheel turns a two-hand “air steering wheel” gesture into the left stick of a
virtual Xbox 360 controller. It is designed for Windows racing games that accept
XInput controllers.

The camera frames and hand landmarks stay on your computer. Nothing is uploaded.

## What it does

- Tracks two hands locally with MediaPipe.
- Uses palm centers, so moving your fingers does not disturb steering.
- Calibrates your natural neutral hand position.
- Includes steering range, dead-zone, response, smoothing, inversion, and mirror controls.
- Sends steering at 100 Hz independently of the camera frame rate.
- Holds through a very short missed frame, then returns safely to center.
- Starts disarmed and has a dedicated global **F8 emergency-neutral** monitor
  that does not depend on the preview window staying responsive.
- Runs in preview-only mode when the virtual-controller driver is unavailable.

This emulates an Xbox controller's left stick. It does **not** emulate a 900°
steering wheel and cannot provide force feedback. This first version controls
steering only; keep using your keyboard, pedals, or another control method for
acceleration and braking.

## Requirements

- Windows 10 or 11.
- A webcam.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) or 64-bit
  Python 3.11.
- Internet access during the first setup, to install packages and download the
  official MediaPipe model.
- For game input: the final **ViGEmBus 1.22** virtual-controller driver.

ViGEmBus is retired and no longer receives updates. Use only its final official
1.22 release, which removed the retired updater. Preview mode needs no driver.

## Install

1. If you want game input, download and install
   [ViGEmBus 1.22 from its official archived release](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0).
   Restart Windows if the installer asks.
2. Open PowerShell in this folder.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\setup.ps1
   ```

   For camera preview without a virtual controller, use:

   ```powershell
   .\setup.ps1 -PreviewOnly
   ```

   This writes a local preview-only marker so controller creation remains
   disabled even if `vgamepad` was installed previously. Running the normal
   `.\setup.ps1` removes that marker.

4. Launch HandWheel:

   ```powershell
   .\start.ps1
   ```

For the same normal setup without typing PowerShell commands, double-click
**Install HandWheel.bat** once, then use **Run HandWheel.bat**.

The setup script prefers `uv` when available. Otherwise it uses Python 3.11.
It installs a pinned revision of the official `vgamepad` source with its old
bundled driver installer disabled, which is why ViGEmBus 1.22 is a separate
manual step.

## First drive

1. Place the webcam near the center of your monitor in a well-lit room.
2. Hold both hands as if gripping a steering wheel at roughly 9 and 3 o'clock.
3. Click **Calibrate** and keep both hands level and still for about one second.
4. Turn your hands and confirm the on-screen gauge moves the same direction.
   Enable **Invert steering** if it does not.
5. Click **Arm output**.
6. Start the game after HandWheel so the virtual controller is easy to identify.

Begin in a menu, free-roam, or another safe offline mode. Press **F8** at any
time to neutralize output.

Suggested game settings:

- Input device: Controller / Gamepad.
- Steering inner dead zone: near zero, because HandWheel already applies one.
- Steering outer dead zone: maximum range.
- Steering assists: tune to preference; simulation steering will feel more direct.

## Controls

| Control | Action |
|---|---|
| F8 | Immediately neutralize and disarm controller output |
| F9 | Start center calibration |
| Calibrate | Capture the current two-hand position as center |
| Camera index | Choose another webcam, then stop/start the camera |
| Steering range | Smaller value reaches full lock with less hand rotation |
| Center dead zone | Removes small movements around center |
| Smoothing | Higher value reduces jitter but adds some lag |
| Response curve | Above 1.0 gives finer control near center |

## Verify the virtual controller

Press `Win + R`, enter `joy.cpl`, and open the virtual Xbox 360 controller's
properties. Arm HandWheel and turn your hands. The X axis should move. Neutralize
with F8 before closing the test.

## Troubleshooting

**The app says “Preview only.”**

Install ViGEmBus 1.22, then restart HandWheel. If `joy.cpl` still shows no
virtual controller, restart Windows.

**The camera will not open.**

Close Teams, Zoom, OBS, browser camera tabs, or Windows Camera. Then click
**Start camera**. Windows camera privacy settings must allow desktop apps.

**Steering is backwards.**

Enable **Invert steering**. Mirroring changes the preview, while inversion
changes controller direction.

**Steering jitters.**

Use brighter, even lighting; keep both palms visible; increase Smoothing slightly;
and raise the Center dead zone to 5–7%.

**The game ignores the controller.**

Start HandWheel before the game, verify movement in `joy.cpl`, and select a
controller input profile in the game. Controller ordering can matter. Some games
or anti-cheat systems may reject virtual devices; follow each game's rules,
especially online.

## Development

Install the test tools and run the unit tests:

```powershell
.\setup.ps1 -PreviewOnly -WithDevTools
.\.venv\Scripts\python.exe -m pytest
```

The hand tracking follows Google's current
[MediaPipe Hand Landmarker Python API](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python).
Controller output uses the
[vgamepad Xbox 360 API](https://github.com/yannbouteiller/vgamepad).
See the project's [ViGEm end-of-life notice](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)
before relying on the legacy driver.
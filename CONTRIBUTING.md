# Contributing to HandWheel

HandWheel controls a virtual steering input, so changes must preserve the safe default: output starts disarmed and returns to neutral when tracking is unreliable.

## Development setup

On Windows, install the project in preview-only mode with development tools:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1 -PreviewOnly -WithDevTools
.\.venv\Scripts\python.exe -m pytest
```

Preview-only mode is the default for contributor work because it avoids creating a virtual controller while testing camera and hand-tracking changes.

## Change guidelines

- Keep camera frames and landmarks local; do not add telemetry or uploads without an explicit privacy review.
- Preserve the F8 emergency-neutral path and the disarmed startup state.
- Test steering changes with both normal tracking and temporarily missing hands. Lost tracking must settle safely at centre.
- Treat the ViGEmBus driver and the pinned `vgamepad` source revision as compatibility-sensitive. Do not change them casually.
- Add or update focused tests for calibration, smoothing, dead zones, controller output, or hotkey behaviour when changing those areas.

## Before opening a pull request

1. Run the test suite in preview-only mode.
2. Check that the README instructions still match the scripts.
3. Describe the Windows version, camera setup, and whether the change was tested only in preview mode or also with `joy.cpl`.
4. Never test new controller behaviour in an online game or a safety-critical setting.

param(
    [switch]$PreviewOnly,
    [switch]$WithDevTools
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$previewMarker = Join-Path $projectRoot ".preview-only"
$vgamepadSource = "https://github.com/yannbouteiller/vgamepad/archive/3f910aa8bbde49a576683db74ad5e4a0879f8a80.zip"
Set-Location -LiteralPath $projectRoot

function Assert-NativeSuccess {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host "HandWheel setup" -ForegroundColor Cyan

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -ne $uvCommand) {
    Write-Host "Preparing Python 3.11 with uv..."
    & uv python install 3.11
    Assert-NativeSuccess "Python installation"
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        & uv venv $venvPath --python 3.11
        Assert-NativeSuccess "Virtual environment creation"
    }

    $installTarget = if ($WithDevTools) { ".[dev]" } else { "." }
    & uv pip install --python $pythonPath --editable $installTarget
    Assert-NativeSuccess "HandWheel dependency installation"

    if (-not $PreviewOnly) {
        try {
            $env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = "true"
            & uv pip install --python $pythonPath $vgamepadSource
            Assert-NativeSuccess "Virtual controller library installation"
        }
        finally {
            Remove-Item Env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL -ErrorAction SilentlyContinue
        }
    }
}
else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        & py -3.11 -m venv $venvPath
        Assert-NativeSuccess "Virtual environment creation"
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python 3.11 or uv is required. Install Python from https://www.python.org/downloads/"
        }
        & python -m venv $venvPath
        Assert-NativeSuccess "Virtual environment creation"
    }

    & $pythonPath -m pip install --upgrade pip
    Assert-NativeSuccess "pip upgrade"
    $installTarget = if ($WithDevTools) { ".[dev]" } else { "." }
    & $pythonPath -m pip install --editable $installTarget
    Assert-NativeSuccess "HandWheel dependency installation"

    if (-not $PreviewOnly) {
        try {
            $env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = "true"
            & $pythonPath -m pip install $vgamepadSource
            Assert-NativeSuccess "Virtual controller library installation"
        }
        finally {
            Remove-Item Env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Downloading the official MediaPipe hand model..."
& $pythonPath -m handwheel.model --download
Assert-NativeSuccess "Hand model download"

if ($PreviewOnly) {
    Set-Content -LiteralPath $previewMarker -Value "Controller output disabled by setup.ps1 -PreviewOnly."
}
elseif (Test-Path -LiteralPath $previewMarker) {
    Remove-Item -LiteralPath $previewMarker -Force
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
if ($PreviewOnly) {
    Write-Host "Preview-only mode was installed; controller output is unavailable."
}
else {
    Write-Host "For game input, install the final ViGEmBus 1.22 driver before starting HandWheel."
    Write-Host "Official release: https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0"
}
Write-Host "Launch with: .\start.ps1"

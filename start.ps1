$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$previewMarker = Join-Path $projectRoot ".preview-only"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "HandWheel is not set up yet. Run .\setup.ps1 first."
}

Set-Location -LiteralPath $projectRoot
try {
    if (Test-Path -LiteralPath $previewMarker) {
        $env:HANDWHEEL_PREVIEW_ONLY = "1"
    }
    & $pythonPath -m handwheel
}
finally {
    Remove-Item Env:HANDWHEEL_PREVIEW_ONLY -ErrorAction SilentlyContinue
}

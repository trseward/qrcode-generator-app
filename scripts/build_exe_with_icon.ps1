$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
Write-Host "Generating icon files..." -ForegroundColor Cyan
python .\make_icon.py

.\scripts\build_exe.ps1
}
finally {
  Pop-Location
}

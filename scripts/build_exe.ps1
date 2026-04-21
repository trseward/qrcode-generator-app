Write-Host "Building onefile executable with embedded icon and bundled icon assets..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
  python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "QR Code Generator" `
    --icon ".\icon_neon.ico" `
    --add-data ".\icon_neon.ico;." `
    --add-data ".\icon_neon.png;." `
    .\main_app.py
}
finally {
  Pop-Location
}

Write-Host "Build complete: .\dist\QR Code Generator.exe" -ForegroundColor Green
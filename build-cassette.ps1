param([string]$Python = "$PSScriptRoot/.venv/Scripts/python.exe")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed --additional-hooks-dir packaging/hooks --name TBMCassettePlayer --add-data "ui;ui" --add-data "assets;assets" --add-data "vorbis_templates.json;." --add-data "song_metadata.json;." --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick --exclude-module tkinter main.py
    if ($LASTEXITCODE -ne 0) { throw "Cassette build failed (exit $LASTEXITCODE)." }
    Write-Host "Ready: $PSScriptRoot/dist/TBMCassettePlayer/TBMCassettePlayer.exe"
} finally {
    Pop-Location
}

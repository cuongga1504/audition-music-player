param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name TBMPlayer-Offline --add-data "vorbis_templates.json;." --add-data "song_metadata.json;." player.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}

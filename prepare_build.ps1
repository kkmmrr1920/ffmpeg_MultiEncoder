$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install pyinstaller

Write-Host "Environment is ready. Run the next command to build EXE:" -ForegroundColor Green
Write-Host ' .\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name ffmpeg_multi_encoder app.py --add-binary "ffmpeg/bin/ffmpeg.exe;ffmpeg/bin"'

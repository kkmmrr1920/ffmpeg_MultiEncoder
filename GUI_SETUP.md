# PySide6 GUI Setup

## 1. Prepare environment

```powershell
powershell -ExecutionPolicy Bypass -File .\prepare_build.ps1
```

This creates `.venv` and installs `PySide6` and `PyInstaller`.

## 2. Run the app

```powershell
.\.venv\Scripts\python app.py
```

App behavior:

- Encoder is fixed to `libx265` (CPU encoding only).
- Input videos support drag-and-drop into the large input list.
- Multiple input files are encoded sequentially (no parallel encoding).
- Preset is selectable (default `slow`) and has a hover tooltip.
- CRF is controlled by a slider (default `20`) and has a hover tooltip.
- Log panel is collapsible and starts collapsed.
- Process priority is selectable (default `Below Normal` / `通常以下`).

## 3. EXE build command (run when you are ready)

```powershell
.\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name ffmpeg_multi_encoder app.py --add-binary "ffmpeg/bin/ffmpeg.exe;ffmpeg/bin"
```

Output EXE:

- `dist/ffmpeg_multi_encoder.exe`

## Notes

- Keep ffmpeg license obligations in mind when redistributing binaries.
# FFmpeg MultiEncoder

> **English** | [日本語](#日本語)

---

## English

A Windows GUI application for batch video encoding using **x265 (CPU)** via `ffmpeg`.

### Features

- Batch input registration (file picker / drag & drop / recursive folder scan)
- Sequential encoding (no parallel processing)
- Encoding settings
  - Codec: `libx265` (fixed)
  - `CRF` slider (0–51, default: `20`)
  - `preset` selector (default: `slow`)
  - Process priority selector
- Output settings
  - Output to the same folder as the input file
  - Output to a custom folder (with reset button)
  - Filename suffix option
- Safe overwrite handling
  - Encodes to a temp file when output name conflicts with input
  - Moves existing files to the Recycle Bin before replacing
- Progress display
  - Overall progress bar
  - Per-file: elapsed time / estimated remaining time / fps / bitrate
- Collapsible log panel
- Queue save on stop / restore on next launch
- Summary report after completion
  - Success/failure counts
  - Total size before/after encoding
  - Size reduction ratio (`+/-`)
- Dark mode style for better readability on Windows

### Requirements

| Item | Details |
|------|---------|
| OS | Windows 10/11 |
| Python | 3.10 or later (for running from source) |
| Dependency | `PySide6` (see `requirements.txt`) |
| ffmpeg | `ffmpeg.exe` required (see setup below) |

### Setup

#### 1. Clone the repository

```powershell
git clone https://github.com/your-username/ffmpeg_MultiEncoder.git
cd ffmpeg_MultiEncoder
```

#### 2. Download ffmpeg

Download from the official build:
- **URL**: https://github.com/BtbN/FFmpeg-Builds/releases
- Recommended: `ffmpeg-master-latest-win64-gpl.zip`

Extract and place `ffmpeg.exe` (and optionally `ffprobe.exe`, `ffplay.exe`) into:
```
ffmpeg/bin/ffmpeg.exe
```

Or point to any existing ffmpeg installation from the GUI.

#### 3. Set up Python environment

```powershell
# Auto-setup script (creates .venv and installs dependencies)
powershell -ExecutionPolicy Bypass -File .\prepare_build.ps1
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Running

```powershell
.\.venv\Scripts\python.exe app.py
```

### Usage

1. Confirm the `ffmpeg` folder path (use "Browse" if needed)
2. Set `CRF`, `preset`, and `priority`
3. Configure output folder and suffix
4. Add videos to the input list
5. Click "Start Encoding"
6. Use "Stop" to pause (the queue is saved and can be restored on next launch)

### Building an EXE

```powershell
# Prepare build environment first
powershell -ExecutionPolicy Bypass -File .\prepare_build.ps1

# Then build
.\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name ffmpeg_multi_encoder app.py --add-binary "ffmpeg/bin/ffmpeg.exe;ffmpeg/bin"
```

Output: `dist/ffmpeg_multi_encoder.exe`

### Project Structure

| File | Description |
|------|-------------|
| `app.py` | Entry point |
| `main_window.py` | Main UI and encoding logic |
| `widgets.py` | Input table widget |
| `utils.py` | Helper functions (ffmpeg detection, drag & drop, dark mode, etc.) |
| `constants.py` | Constants, regex patterns, display labels |
| `requirements.txt` | Python dependencies |
| `prepare_build.ps1` | Environment setup script |
| `ffmpeg_multi_encoder.spec` | PyInstaller build spec |

### Settings File

`settings.json` is generated at runtime next to the executable (or script).
It stores:
- Last used UI settings (CRF, preset, output folder, etc.)
- Pending queue at the time of "Stop"

> `settings.json` is excluded from version control (`.gitignore`) because it contains local paths.

### Notes

- When the output filename matches the input filename, the existing file is moved to the Recycle Bin before replacement.
- Check ffmpeg's license and redistribution terms before distributing binaries.
- `ffmpeg/bin/` and `ffmpeg/doc/` are excluded from this repository. Download ffmpeg separately.

---

## 日本語

Windowsで `ffmpeg` を使って複数の動画を **x265 (CPU)** で一括エンコードするGUIアプリケーションです。

### 主な機能

- 複数動画の一括登録（ファイル選択 / ドラッグ＆ドロップ / フォルダ再帰探索）
- 逐次エンコード（同時並列なし）
- エンコード設定
  - コーデック: `libx265` 固定
  - `CRF` スライダー（0〜51、デフォルト: `20`）
  - `preset` 選択（デフォルト: `slow`）
  - プロセス優先度選択
- 出力設定
  - 入力と同じフォルダへ出力
  - 任意フォルダへ出力（リセットボタンあり）
  - ファイル名サフィックス付与
- 安全な上書き処理
  - 出力と入力が同名の場合は一時ファイルへ出力
  - 既存ファイルはゴミ箱へ移動してから置換
- 進捗表示
  - 全体進捗バー
  - 現在ファイルの 経過時間 / 残り時間(推定) / fps / bitrate
- ログ表示（折りたたみ可能）
- 停止時キュー保存 / 次回起動時の復元
- 処理結果サマリー
  - 成功件数・失敗件数
  - 合計サイズ（処理前 / 処理後）
  - 削減率（`+/-` 表示）
- Windowsダークモード時の可読性向上スタイル

### 動作環境

| 項目 | 内容 |
|------|------|
| OS | Windows 10/11 |
| Python | 3.10 以上（ソースから起動する場合） |
| 依存パッケージ | `PySide6`（`requirements.txt` 参照） |
| ffmpeg | `ffmpeg.exe` が必要（下記セットアップ参照） |

### セットアップ

#### 1. リポジトリをクローン

```powershell
git clone https://github.com/your-username/ffmpeg_MultiEncoder.git
cd ffmpeg_MultiEncoder
```

#### 2. ffmpegをダウンロード

公式ビルドからダウンロードしてください:
- **URL**: https://github.com/BtbN/FFmpeg-Builds/releases
- 推奨: `ffmpeg-master-latest-win64-gpl.zip`

解凍後、`ffmpeg.exe`（任意で `ffprobe.exe`, `ffplay.exe`）を以下に配置:
```
ffmpeg/bin/ffmpeg.exe
```

または、GUIからすでにインストール済みのffmpegフォルダを指定することもできます。

#### 3. Python環境のセットアップ

```powershell
# 自動セットアップスクリプト（.venv作成 + 依存パッケージインストール）
powershell -ExecutionPolicy Bypass -File .\prepare_build.ps1
```

手動で行う場合:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 起動

```powershell
.\.venv\Scripts\python.exe app.py
```

### 使い方

1. `ffmpeg` フォルダを確認（必要なら「参照」で指定）
2. `CRF / preset / 優先度` を設定
3. 出力先とサフィックスを設定
4. 動画を入力リストへ追加
5. 「エンコード開始」を押す
6. 「停止」で中断可能（キューは保存され、次回起動時に復元を選択できます）

### EXEビルド

```powershell
# まずビルド環境を準備
powershell -ExecutionPolicy Bypass -File .\prepare_build.ps1

# EXEをビルド
.\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name ffmpeg_multi_encoder app.py --add-binary "ffmpeg/bin/ffmpeg.exe;ffmpeg/bin"
```

出力先: `dist/ffmpeg_multi_encoder.exe`

### プロジェクト構成

| ファイル | 説明 |
|----------|------|
| `app.py` | エントリーポイント |
| `main_window.py` | メインUIとエンコード制御 |
| `widgets.py` | 入力テーブルウィジェット |
| `utils.py` | 補助関数（ffmpeg探索、D&D処理、ダークモードなど） |
| `constants.py` | 定数・正規表現・表示定義 |
| `requirements.txt` | Python依存パッケージ |
| `prepare_build.ps1` | 環境セットアップスクリプト |
| `ffmpeg_multi_encoder.spec` | PyInstallerビルド設定 |

### 設定ファイル

`settings.json` は実行時にEXE（またはスクリプト）の隣に自動生成されます。
保存内容:
- 直近のUI設定（CRF、preset、出力先など）
- 「停止」時点での未処理キュー情報

> `settings.json` はローカルパスを含むため、バージョン管理対象外（`.gitignore` に記載）です。

### 注意事項

- 入力動画と同名で出力する場合は、既存ファイルがゴミ箱へ移動されてから置換されます。
- ffmpegのバイナリを再配布する際は、ライセンスおよび配布条件を確認してください。
- `ffmpeg/bin/` と `ffmpeg/doc/` はリポジトリに含まれていません。ffmpegは別途ダウンロードしてください。

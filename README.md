# FFmpeg MultiEncoder

Windows向けの動画一括エンコードGUIアプリです。  
`ffmpeg` を使って、複数動画を **x265(CPU)** で順番に変換できます。

## 主な機能
- 複数動画の一括登録（ファイル選択 / ドラッグ＆ドロップ / フォルダ再帰探索）
- 逐次エンコード（同時並列なし）
- エンコード設定
  - コーデック: `libx265` 固定
  - `CRF` スライダー
  - `preset` 選択（既定: `slow`）
  - プロセス優先度選択
- 出力設定
  - 入力と同じフォルダへ出力
  - 任意フォルダへ出力（リセットあり）
  - ファイル名サフィックス付与
- 安全な上書き処理
  - 同名出力時は一時ファイルへ出力
  - 既存ファイルはゴミ箱へ移動してから置換
- 進捗表示
  - 全体進捗バー
  - 現在ファイルの `経過時間 / 残り時間(推定) / fps / bitrate`
- ログ表示（折りたたみ可能）
- 停止時キュー保存 / 次回起動時の復元
- 処理結果サマリー
  - 成功件数・失敗件数
  - 合計サイズ（処理前 / 処理後）
  - 削減率（`+/-` 表示）
- Windowsダークモード時の可読性向上スタイル

## 動作環境
- OS: Windows
- Python: 3.10 以上推奨
- 依存: `PySide6`（`requirements.txt`）
- `ffmpeg.exe`
  - 同梱フォルダ `ffmpeg/bin/ffmpeg.exe` を自動検出
  - またはGUIから `ffmpeg.exe` のあるフォルダを指定

## セットアップ
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 起動
```powershell
.\.venv\Scripts\python.exe app.py
```

## 使い方
1. `ffmpeg` フォルダを確認（必要なら「参照」で指定）
2. `CRF / preset / 優先度` を設定
3. 出力先とサフィックスを設定
4. 動画を入力リストへ追加
5. 「エンコード開始」を押す
6. 必要なら「停止」で中断（キューは保存され、次回復元可能）

## EXEビルド
`build_exe_command.txt` にビルドコマンドを保存しています。

例:
```powershell
.\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name ffmpeg_multi_encoder app.py --add-binary "ffmpeg/bin/ffmpeg.exe;ffmpeg/bin"
```

## 設定ファイル
- `settings.json`（実行場所に生成）
  - 直近のUI設定（CRF / preset / 出力先など）
  - 停止時の未処理キュー情報

## プロジェクト構成
- `app.py`: エントリーポイント
- `main_window.py`: メインUIとエンコード制御
- `widgets.py`: テーブルウィジェット
- `utils.py`: 補助関数（ffmpeg探索、D&D処理、ダークモードなど）
- `constants.py`: 定数・正規表現・表示定義

## 注意事項
- 入力動画と同名で出力する場合は既存ファイルがゴミ箱へ移動されます。
- ffmpegのライセンス・配布条件は各配布元の規約を確認してください。

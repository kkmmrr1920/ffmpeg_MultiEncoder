"""
constants.py - Application-wide constants and display definitions
             / アプリケーション全体で使用する定数・表示定義
"""

import re

from PySide6.QtGui import QColor

# ---------------------------------------------------------------------------
# Supported video file extensions / 対応する動画ファイルの拡張子
# ---------------------------------------------------------------------------
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".mts", ".m2ts"
}

# File filter string for QFileDialog / QFileDialog 用のファイルフィルタ文字列
VIDEO_FILTER = (
    "Video Files (" + " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS)) + ")"
    ";;All Files (*.*)"
)

# ---------------------------------------------------------------------------
# x265 encoder presets / x265 エンコーダのプリセット一覧
# Faster presets trade quality/size for speed; slower presets compress better.
# プリセットが速いほどエンコードは速いが圧縮効率が落ちる。遅いほど高圧縮。
# ---------------------------------------------------------------------------
X265_PRESETS = [
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow", "placebo",
]

# ---------------------------------------------------------------------------
# Windows process priority classes / Windows プロセス優先度クラス
# Values are Win32 PROCESS_CREATION flags / 値は Win32 プロセス作成フラグ
# ---------------------------------------------------------------------------
PRIORITY_CLASSES = {
    "低":       0x00000040,  # IDLE_PRIORITY_CLASS
    "通常以下": 0x00004000,  # BELOW_NORMAL_PRIORITY_CLASS
    "通常":     0x00000020,  # NORMAL_PRIORITY_CLASS
    "通常以上": 0x00008000,  # ABOVE_NORMAL_PRIORITY_CLASS
    "高":       0x00000080,  # HIGH_PRIORITY_CLASS
}
DEFAULT_PRIORITY = "通常以下"  # Below Normal / 通常以下

# ---------------------------------------------------------------------------
# Settings file name / 設定ファイル名
# Saved next to the executable or script at runtime.
# 実行時にEXE・スクリプトの隣に自動生成される。
# ---------------------------------------------------------------------------
CONFIG_FILENAME = "settings.json"

# ---------------------------------------------------------------------------
# Table column indices / テーブル列インデックス
# ---------------------------------------------------------------------------
COL_NAME   = 0  # File name / ファイル名
COL_BEFORE = 1  # Size before encoding / 処理前サイズ
COL_AFTER  = 2  # Size after encoding / 処理後サイズ
COL_RATIO  = 3  # Size change ratio / 変化率
COL_RESULT = 4  # Encoding result / 結果
COL_PATH   = 5  # Full path of input file / 入力動画のフルパス

# Column header labels / 列ヘッダーのラベル
HEADER_LABELS = ("ファイル名", "処理前サイズ", "処理後サイズ", "変化率(%)", "結果", "パス")

# Column header tooltips / 列ヘッダーのツールチップ
HEADER_TOOLTIPS = (
    "入力動画のファイル名",
    "エンコード前のファイルサイズ",
    "エンコード後のファイルサイズ",
    "処理前に対するサイズ変化率（マイナスで削減、プラスで増加）",
    "エンコード結果（完了またはエラー内容）",
    "入力動画のフルパス",
)

# ---------------------------------------------------------------------------
# Regular expressions for parsing ffmpeg stderr output
# ffmpeg stderr 出力パース用正規表現
# ---------------------------------------------------------------------------
FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
FFMPEG_TIME_RE     = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
FFMPEG_FPS_RE      = re.compile(r"fps=\s*([0-9.]+)")
FFMPEG_BITRATE_RE  = re.compile(r"bitrate=\s*([^\s]+)")

# ---------------------------------------------------------------------------
# Size change ratio colors (readable on both light and dark themes)
# 変化率カラー（ライト・ダーク両テーマで視認可能な色）
# ---------------------------------------------------------------------------
COLOR_RATIO_INCREASE = QColor("#FF6B6B")  # Size increased (bad)  / サイズ増加（悪） → 明るい赤
COLOR_RATIO_DECREASE = QColor("#66BB6A")  # Size decreased (good) / サイズ削減（良） → 明るい緑

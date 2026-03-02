import re

from PySide6.QtGui import QColor

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".mts", ".m2ts"
}
VIDEO_FILTER = (
    "Video Files (" + " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS)) + ")"
    ";;All Files (*.*)"
)

X265_PRESETS = [
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow", "placebo",
]

PRIORITY_CLASSES = {
    "低": 0x00000040,
    "通常以下": 0x00004000,
    "通常": 0x00000020,
    "通常以上": 0x00008000,
    "高": 0x00000080,
}
DEFAULT_PRIORITY = "通常以下"

CONFIG_FILENAME = "settings.json"

# テーブル列インデックス
COL_NAME = 0
COL_BEFORE = 1
COL_AFTER = 2
COL_RATIO = 3
COL_PATH = 4

HEADER_LABELS = ("ファイル名", "処理前サイズ", "処理後サイズ", "変化率(%)", "パス")
HEADER_TOOLTIPS = (
    "入力動画のファイル名",
    "エンコード前のファイルサイズ",
    "エンコード後のファイルサイズ",
    "処理前に対するサイズ変化率（マイナスで削減、プラスで増加）",
    "入力動画のフルパス",
)

# ffmpeg stderr パーサ用正規表現
FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
FFMPEG_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
FFMPEG_FPS_RE = re.compile(r"fps=\s*([0-9.]+)")
FFMPEG_BITRATE_RE = re.compile(r"bitrate=\s*([^\s]+)")

# 変化率カラー: ライト・ダーク両テーマで視認可能な色
COLOR_RATIO_INCREASE = QColor("#FF6B6B")  # サイズ増加（悪）→ 明るい赤
COLOR_RATIO_DECREASE = QColor("#66BB6A")  # サイズ削減（良）→ 明るい緑

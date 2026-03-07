"""
FFmpeg MultiEncoder - Entry Point / エントリーポイント

Launches the PySide6 GUI application for batch x265 video encoding.
PySide6 GUIアプリケーションを起動する。複数動画をx265で一括エンコードできる。
"""

import sys

from PySide6.QtWidgets import QApplication

from src.main_window import MainWindow
from src.utils import apply_dark_mode_readable_style

if __name__ == "__main__":
    # Initialize the Qt application / Qt アプリケーションを初期化
    app = QApplication(sys.argv)
    app.setApplicationName("FFmpeg MultiEncoder")

    # Apply dark mode readable style if Windows dark theme is active
    # Windows ダークテーマが有効な場合に視認性を向上させるスタイルを適用
    apply_dark_mode_readable_style(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow
from utils import apply_dark_mode_readable_style

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FFmpeg MultiEncoder")
    apply_dark_mode_readable_style(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

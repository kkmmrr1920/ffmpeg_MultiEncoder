import ctypes
import sys
import winreg
from pathlib import Path

from PySide6.QtWidgets import QApplication

from constants import VIDEO_EXTENSIONS


def resolve_launch_dir() -> Path:
    """起動バイナリ(OneFile EXE含む)基準のディレクトリ。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ffmpeg(custom_dir: str = "") -> str:
    """
    ffmpeg実行ファイルのパスを解決する。見つからなければ空文字を返す。
    custom_dir が指定されている場合はそのフォルダのみを探索する。
    """
    if custom_dir:
        candidate = Path(custom_dir) / "ffmpeg.exe"
        return str(candidate) if candidate.exists() else ""

    # カスタムパス未指定のときはバンドル・スクリプト隣接パスを自動検索
    script_dir = Path(__file__).resolve().parent
    app_dir = Path(getattr(sys, "_MEIPASS", script_dir))
    for candidate in dict.fromkeys([
        app_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
        script_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]):
        if candidate.exists():
            return str(candidate)
    return ""


def translate_ffmpeg_error(error_line: str, code: int) -> str:
    """ffmpegのエラー行を日本語の短いメッセージに変換する。"""
    lower = error_line.lower()
    patterns = [
        ("no such file",         "ファイルが見つかりません"),
        ("invalid data",         "無効なデータです"),
        ("invalid argument",     "無効な引数です"),
        ("encoder not found",    "エンコーダが見つかりません"),
        ("codec not found",      "コーデックが見つかりません"),
        ("decoder (codec",       "デコーダが見つかりません"),
        ("permission denied",    "アクセスが拒否されました"),
        ("no space left",        "ディスク容量が不足しています"),
        ("disk full",            "ディスク容量が不足しています"),
        ("out of memory",        "メモリが不足しています"),
        ("moov atom not found",  "動画ヘッダが見つかりません（ファイル破損の可能性）"),
        ("end of file",          "ファイルが途中で終了しています"),
        ("broken pipe",          "パイプエラーが発生しました"),
        ("conversion failed",    "変換に失敗しました"),
        ("error while decoding", "デコードエラーが発生しました"),
        ("error while opening",  "ファイルを開けませんでした"),
        ("unable to open",       "ファイルを開けませんでした"),
        ("could not find tag",   "タグが見つかりません"),
    ]
    for pattern, japanese in patterns:
        if pattern in lower:
            return japanese
    return f"エンコードエラー (終了コード: {code})"


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def extract_video_paths(urls) -> list[Path]:
    """ドロップ対象URLから動画ファイルを重複なく抽出（フォルダは再帰探索）。"""
    found: list[Path] = []
    seen: set[str] = set()
    for url in urls:
        if not url.isLocalFile():
            continue
        dropped = Path(url.toLocalFile())
        candidates = dropped.rglob("*") if dropped.is_dir() else [dropped]
        for candidate in candidates:
            if is_video_file(candidate) and (key := str(candidate.resolve())) not in seen:
                found.append(candidate)
                seen.add(key)
    return found


def format_bytes(size: int | None) -> str:
    if size is None:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def parse_hhmmss_to_seconds(hh: str, mm: str, ss: str) -> float:
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def format_seconds_as_hms(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--:--"
    total = int(seconds)
    return f"{total // 3600:02}:{(total % 3600) // 60:02}:{total % 60:02}"


def move_to_recycle_bin(path: Path) -> tuple[bool, str]:
    """既存ファイルをゴミ箱へ移動する。Windows以外では通常削除にフォールバック。"""
    if not path.exists():
        return True, ""

    if sys.platform != "win32":
        try:
            path.unlink()
            return True, ""
        except OSError as exc:
            return False, str(exc)

    # SHFileOperationW で「削除」ではなく「ゴミ箱へ移動」を行う
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", ctypes.c_bool),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 0x0003
    # 確認ダイアログなし、サイレント、取り消し可能(ゴミ箱)で処理
    FOF_FLAGS = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI

    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = str(path) + "\0\0"
    op.pTo = None
    op.fFlags = FOF_FLAGS
    op.hwnd = None
    op.hNameMappings = None
    op.lpszProgressTitle = None

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0:
        return False, f"SHFileOperationW error={result}"
    if op.fAnyOperationsAborted:
        return False, "操作が中断されました"
    return True, ""


def is_windows_dark_mode() -> bool:
    """Windowsのアプリテーマがダークかどうかを判定する。"""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except OSError:
        return False


def apply_dark_mode_readable_style(app: QApplication) -> None:
    """ダークモード時に文字を見やすくする配色を適用する。"""
    if not is_windows_dark_mode():
        return

    app.setStyleSheet("""
        QWidget {
            color: #F2F2F2;
        }
        QMainWindow, QWidget {
            background-color: #1E1E1E;
        }
        QLabel, QCheckBox, QGroupBox, QHeaderView::section {
            color: #F2F2F2;
        }
        QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
            color: #F8F8F8;
            background-color: #252526;
            border: 1px solid #5E5E5E;
            selection-background-color: #3A6EA5;
            selection-color: #FFFFFF;
        }
        QPushButton {
            color: #FFFFFF;
            background-color: #2D2D30;
            border: 1px solid #808080;
            padding: 4px 8px;
        }
        QPushButton:disabled {
            color: #B0B0B0;
            background-color: #3A3A3A;
        }
        QGroupBox {
            border: 1px solid #6A6A6A;
            margin-top: 8px;
            padding-top: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #FFFFFF;
        }
        QProgressBar {
            color: #FFFFFF;
            background-color: #252526;
            border: 1px solid #5E5E5E;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #4D88C7;
        }
    """)


def accept_url_drag(event) -> None:
    if event.mimeData().hasUrls():
        event.acceptProposedAction()
    else:
        event.ignore()

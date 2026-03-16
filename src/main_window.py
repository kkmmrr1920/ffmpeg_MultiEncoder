"""
main_window.py - Main window and encoding controller for FFmpeg MultiEncoder
               / メインウィンドウとエンコード制御

Manages the entire GUI, settings persistence, ffmpeg process execution,
progress tracking, and queue management.
GUI全体・設定の保存/復元・ffmpegプロセス実行・進捗追跡・キュー管理を担う。
"""

import ctypes
from collections import deque
import json
from pathlib import Path
import shlex
import sys
import time
import os

from PySide6.QtCore import QProcess, Qt, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.constants import (
    CONFIG_FILENAME, DEFAULT_PRIORITY, PRIORITY_CLASSES, VIDEO_FILTER, X265_PRESETS,
    FFMPEG_DURATION_RE, FFMPEG_TIME_RE, FFMPEG_FPS_RE, FFMPEG_BITRATE_RE,
)
from src.utils import (
    accept_url_drag, find_ffmpeg, format_bytes,
    format_seconds_as_hms, move_to_recycle_bin, parse_hhmmss_to_seconds,
    resolve_launch_dir, translate_ffmpeg_error,
)
from src.widgets import InputTableWidget

# Message shown when ffmpeg.exe cannot be found
# ffmpeg.exe が見つからない場合に表示するガイドメッセージ
_FFMPEG_DOWNLOAD_GUIDE = (
    "ffmpeg.exe が見つかりません。\n\n"
    "以下のサイトからffmpegをダウンロードし、\n"
    "フォルダパスを指定してください。\n\n"
    "【ダウンロード先】\n"
    "https://github.com/BtbN/FFmpeg-Builds/releases\n"
    "（ffmpeg-master-latest-win64-gpl.zip を推奨）\n\n"
    "解凍後の bin フォルダを指定してください。"
)


class MainWindow(QMainWindow):
    """
    Main application window.
    アプリケーションのメインウィンドウ。

    Responsibilities / 責務:
    - Build and wire up all UI widgets / 全UIウィジェットの構築・接続
    - Load and save settings (settings.json) / 設定の読み書き（settings.json）
    - Manage the encoding queue via QProcess / QProcess を使ったエンコードキュー管理
    - Display per-file and overall progress / ファイル単位・全体の進捗表示
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FFmpeg MultiEncoder")
        self.resize(1200, 860)

        # Default output dir: <launch_dir>/outputs/
        # デフォルト出力先: <起動フォルダ>/outputs/
        self.default_output_dir = self._ensure_default_output_dir()
        self.ffmpeg_exe_path = ""  # Resolved in _load_settings → _update_ffmpeg_exe_path

        # QProcess for running ffmpeg / ffmpeg 実行用 QProcess
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)

        # Queue execution state / キュー実行状態
        self.pending_inputs: deque[Path] = deque()
        self.current_input: Path | None = None
        self.current_output: Path | None = None
        self.current_temp_output: Path | None = None
        self.current_error_lines: deque[str] = deque(maxlen=60)
        self.stop_requested = False
        self.resume_queue_paths: list[str] = []

        # Per-file progress state / 現在処理中ファイルの進捗情報
        self.current_start_time = 0.0
        self.current_duration_sec: float | None = None
        self.current_encoded_sec = 0.0
        self.current_fps_text = "-"
        self.current_bitrate_text = "-"

        # Summary counters / 結果集計カウンタ
        self.total_count = 0
        self.success_count = 0
        self.failed_items: list[tuple[str, str]] = []

        self._build_ui()
        self._connect_signals()
        self._reset_output_dir()
        self._load_settings()
        self._update_ffmpeg_exe_path()
        self._toggle_output_dir_mode(self.same_as_input_dir_check.isChecked())
        self._toggle_suffix_mode(self.suffix_check.isChecked())
        self._restore_resume_queue_if_available()

    # ──────────────────────────────────────────
    # UI construction / UI構築
    # ──────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build and lay out all widgets in the main window.
        メインウィンドウの全ウィジェットを構築・配置する。"""
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QGridLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(8)

        # ── ffmpeg folder row / ffmpeg フォルダ行 ──
        ffmpeg_dir_label = QLabel("ffmpeg フォルダ")
        ffmpeg_dir_label.setToolTip("ffmpeg.exeを含むフォルダのパスです。")
        self.ffmpeg_dir_edit = QLineEdit()
        self.ffmpeg_dir_edit.setPlaceholderText("ffmpeg.exe を含むフォルダを選択してください")
        self.ffmpeg_dir_edit.setToolTip("ffmpeg.exeを含むフォルダのパスです。")
        self.ffmpeg_dir_browse_btn = QPushButton("参照")
        self.ffmpeg_dir_browse_btn.setToolTip("ffmpeg.exeを含むフォルダを選択します。")

        # ── Encoder / preset / priority row / エンコーダ・プリセット・優先度行 ──
        encoder_title = QLabel("エンコーダ")
        encoder_title.setToolTip("本アプリはCPU版x265固定です。")
        self.encoder_label = QLabel("libx265 (CPU固定)")

        preset_title = QLabel("プリセット")
        preset_title.setToolTip("x265のプリセットを選択します。速度と圧縮効率のバランスが変わります。")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(X265_PRESETS)
        self.preset_combo.setCurrentText("slow")
        self.preset_combo.setToolTip("プリセットを変更すると、エンコード速度と圧縮効率が変わります。")

        priority_title = QLabel("優先度")
        priority_title.setToolTip("エンコード処理のプロセス優先度を設定します。")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(list(PRIORITY_CLASSES.keys()))
        self.priority_combo.setCurrentText(DEFAULT_PRIORITY)
        self.priority_combo.setToolTip("低くすると他アプリを優先しやすく、高くすると変換を優先します。")

        # ── CRF row / CRF行 ──
        crf_title = QLabel("CRF")
        crf_title.setToolTip("画質と容量のバランスを決める値です。")
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(20)
        self.crf_slider.setSingleStep(1)
        self.crf_slider.setPageStep(1)
        self.crf_slider.setToolTip("小さいほど高画質・大容量、大きいほど低画質・小容量です。")
        self.crf_value_label = QLabel("20")
        self.crf_value_label.setToolTip("現在のCRF値です。")

        # ── Output folder row / 出力フォルダ行 ──
        self.same_as_input_dir_check = QCheckBox("入力ファイルと同じフォルダに出力")
        self.same_as_input_dir_check.setChecked(True)
        self.same_as_input_dir_check.setToolTip("オンの場合は入力動画と同じフォルダへ出力します。")

        output_title = QLabel("出力フォルダ")
        output_title.setToolTip("同じフォルダ出力がオフのときに使う出力先です。")
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setToolTip("出力先フォルダのパスです。")
        self.output_dir_btn = QPushButton("出力フォルダ選択")
        self.output_dir_btn.setToolTip("出力先フォルダを選択します。")
        self.output_dir_reset_btn = QPushButton("リセット")
        self.output_dir_reset_btn.setToolTip("出力先フォルダを初期値に戻します。")

        # ── Suffix row / サフィックス行 ──
        self.suffix_check = QCheckBox("ファイル名にサフィックスを付ける")
        self.suffix_check.setChecked(True)
        self.suffix_check.setToolTip("オンの場合は出力ファイル名にサフィックスを付与します。")
        suffix_title = QLabel("サフィックス")
        suffix_title.setToolTip("出力ファイル名の末尾に追加する文字列です。")
        self.suffix_edit = QLineEdit("_x265")
        self.suffix_edit.setPlaceholderText("例: _x265")
        self.suffix_edit.setToolTip("例: _x265 -> input.mp4 が input_x265.mp4 になります。")

        # ── Input list / 入力リスト ──
        input_title = QLabel("入力リスト（ヘッダクリックで並び替え / ドラッグで列幅変更）")
        input_title.setToolTip("列ヘッダーをクリックすると昇順/降順を切り替えて並び替えできます。")
        self.input_table = InputTableWidget()
        self.input_table.dropped.connect(self._on_dropped)
        self.input_table.rightClicked.connect(self._on_right_clicked)
        self.input_table.setMinimumHeight(380)

        self.add_input_btn = QPushButton("動画を追加")
        self.add_input_btn.setToolTip("動画ファイルを追加します。フォルダは再帰的に探索されます。")
        self.remove_input_btn = QPushButton("選択を削除")
        self.remove_input_btn.setToolTip("選択中の行を入力リストから削除します。")
        self.clear_input_btn = QPushButton("すべて削除")
        self.clear_input_btn.setToolTip("入力リストをすべて削除します。")

        # ── Action buttons / 実行ボタン ──
        self.run_btn = QPushButton("エンコード開始")
        self.run_btn.setToolTip("入力リストを上から順番に逐次エンコードします。")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("実行中のエンコードを停止し、残りのキューを中止します。")

        # ── Progress & log / 進捗・ログ ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setToolTip("エンコードの進行状況を表示します。")
        self.stats_label = QLabel("経過: --:--:-- / 残り(推定): --:--:-- / fps: - / bitrate: -")
        self.stats_label.setToolTip("現在処理中ファイルの進捗詳細です。")

        self.log_group = QGroupBox("ログ（展開して表示）")
        self.log_group.setCheckable(True)
        self.log_group.setChecked(False)
        self.log_group.setToolTip("ログ表示を折りたたみ/展開します。")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setVisible(False)
        self.log.setToolTip("ffmpegの出力・エラーと処理結果を表示します。")
        log_layout = QVBoxLayout(self.log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.addWidget(self.log)

        # ── Grid layout / グリッド配置 ──
        row = 0
        layout.addWidget(ffmpeg_dir_label, row, 0)
        layout.addWidget(self.ffmpeg_dir_edit, row, 1, 1, 4)
        layout.addWidget(self.ffmpeg_dir_browse_btn, row, 5)

        row += 1
        layout.addWidget(encoder_title, row, 0)
        layout.addWidget(self.encoder_label, row, 1)
        layout.addWidget(preset_title, row, 2)
        layout.addWidget(self.preset_combo, row, 3)
        layout.addWidget(priority_title, row, 4)
        layout.addWidget(self.priority_combo, row, 5)

        row += 1
        layout.addWidget(crf_title, row, 0)
        layout.addWidget(self.crf_slider, row, 1, 1, 4)
        layout.addWidget(self.crf_value_label, row, 5)

        row += 1
        layout.addWidget(self.same_as_input_dir_check, row, 0, 1, 6)

        row += 1
        layout.addWidget(output_title, row, 0)
        layout.addWidget(self.output_dir_edit, row, 1, 1, 3)
        layout.addWidget(self.output_dir_btn, row, 4)
        layout.addWidget(self.output_dir_reset_btn, row, 5)

        row += 1
        layout.addWidget(self.suffix_check, row, 0, 1, 2)
        layout.addWidget(suffix_title, row, 2)
        layout.addWidget(self.suffix_edit, row, 3, 1, 3)

        row += 1
        layout.addWidget(input_title, row, 0, 1, 6)

        row += 1
        layout.addWidget(self.input_table, row, 0, 1, 6)

        row += 1
        input_buttons = QHBoxLayout()
        input_buttons.addWidget(self.add_input_btn)
        input_buttons.addWidget(self.remove_input_btn)
        input_buttons.addWidget(self.clear_input_btn)
        input_buttons.addStretch(1)
        layout.addLayout(input_buttons, row, 0, 1, 6)

        row += 1
        run_buttons = QHBoxLayout()
        run_buttons.addWidget(self.run_btn)
        run_buttons.addWidget(self.stop_btn)
        run_buttons.addStretch(1)
        layout.addLayout(run_buttons, row, 0, 1, 6)

        row += 1
        layout.addWidget(self.progress, row, 0, 1, 6)

        row += 1
        layout.addWidget(self.stats_label, row, 0, 1, 6)

        row += 1
        layout.addWidget(self.log_group, row, 0, 1, 6)

    def _connect_signals(self) -> None:
        """Connect all Qt signals to their handler slots.
        全 Qt シグナルをハンドラスロットに接続する。"""
        self.ffmpeg_dir_browse_btn.clicked.connect(self._select_ffmpeg_dir)
        self.ffmpeg_dir_edit.editingFinished.connect(self._update_ffmpeg_exe_path)

        self.output_dir_btn.clicked.connect(self._select_output_dir)
        self.output_dir_reset_btn.clicked.connect(self._reset_output_dir)
        self.same_as_input_dir_check.toggled.connect(self._toggle_output_dir_mode)
        self.suffix_check.toggled.connect(self._toggle_suffix_mode)

        self.add_input_btn.clicked.connect(self._select_input_files)
        self.remove_input_btn.clicked.connect(self.input_table.remove_selected_rows)
        self.clear_input_btn.clicked.connect(lambda: self.input_table.setRowCount(0))

        self.run_btn.clicked.connect(self.start_encode)
        self.stop_btn.clicked.connect(self.stop_encode)
        self.crf_slider.valueChanged.connect(self._update_crf_label)
        self.log_group.toggled.connect(self._toggle_log)

        self.process.started.connect(self._apply_process_priority)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._handle_finished)

    # ──────────────────────────────────────────
    # ffmpeg path management / ffmpeg パス管理
    # ──────────────────────────────────────────

    def _select_ffmpeg_dir(self) -> None:
        """Open a folder picker dialog for the ffmpeg directory.
        ffmpegフォルダ選択ダイアログを開く。"""
        directory = QFileDialog.getExistingDirectory(
            self, "ffmpeg.exeを含むフォルダを選択",
            self.ffmpeg_dir_edit.text().strip() or "",
        )
        if directory:
            self.ffmpeg_dir_edit.setText(directory)
            self._update_ffmpeg_exe_path()

    def _update_ffmpeg_exe_path(self) -> None:
        """Resolve and validate the ffmpeg executable path from the directory field.
        ffmpeg_dir_edit の内容から ffmpeg 実行ファイルパスを解決・検証する。"""
        custom_dir = self.ffmpeg_dir_edit.text().strip()
        exe = find_ffmpeg(custom_dir)

        # If no custom dir is given but auto-detection found one, show it in the field.
        # フォルダ未指定かつ自動検出できた場合はフォルダをフィールドへ反映
        if not custom_dir and exe:
            self.ffmpeg_dir_edit.blockSignals(True)
            self.ffmpeg_dir_edit.setText(str(Path(exe).parent))
            self.ffmpeg_dir_edit.blockSignals(False)

        self.ffmpeg_exe_path = exe
        tooltip = f"ffmpeg.exe: {exe}" if exe else "ffmpeg.exeが見つかりません。参照ボタンでフォルダを選択してください。"
        self.ffmpeg_dir_edit.setToolTip(tooltip)

    def _validate_ffmpeg(self) -> bool:
        """Check that ffmpeg is available; show a guide dialog if not.
        ffmpegが使用可能かチェックし、見つからなければ案内ダイアログを表示する。"""
        if self.ffmpeg_exe_path:
            return True
        QMessageBox.warning(self, "ffmpegが見つかりません", _FFMPEG_DOWNLOAD_GUIDE)
        return False

    # ──────────────────────────────────────────
    # Settings save / load / 設定の保存・読み込み
    # ──────────────────────────────────────────

    def _ensure_default_output_dir(self) -> Path:
        """Create and return the default output directory (<launch_dir>/outputs/).
        デフォルト出力ディレクトリ (<起動フォルダ>/outputs/) を作成して返す。"""
        outputs_dir = resolve_launch_dir() / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        return outputs_dir

    def _reset_output_dir(self) -> None:
        """Reset the output directory field to the default path.
        出力先フォルダフィールドをデフォルト値に戻す。"""
        self.output_dir_edit.setText(str(self.default_output_dir))

    def _load_settings(self) -> None:
        """Load UI settings from settings.json. Silently uses defaults on failure.
        settings.json からUI設定を読み込む。失敗時はデフォルト値のまま起動する。"""
        config_path = resolve_launch_dir() / CONFIG_FILENAME
        data: dict = {}
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            pass  # Use defaults on any error / エラー時はデフォルトで起動

        # ffmpeg folder: use saved value, or auto-detect if absent
        # ffmpeg フォルダ: 保存値があればそれを使い、なければ自動検出して表示
        ffmpeg_dir = data.get("ffmpeg_dir", "")
        if ffmpeg_dir:
            self.ffmpeg_dir_edit.setText(ffmpeg_dir)
        else:
            auto_exe = find_ffmpeg()
            if auto_exe:
                self.ffmpeg_dir_edit.setText(str(Path(auto_exe).parent))

        if (preset := data.get("preset", "")) in X265_PRESETS:
            self.preset_combo.setCurrentText(preset)

        if (priority := data.get("priority", "")) in PRIORITY_CLASSES:
            self.priority_combo.setCurrentText(priority)

        if isinstance(crf := data.get("crf"), int) and 0 <= crf <= 51:
            self.crf_slider.setValue(crf)

        if "same_as_input_dir" in data:
            self.same_as_input_dir_check.setChecked(bool(data["same_as_input_dir"]))

        if (output_dir := data.get("output_dir", "")) and Path(output_dir).is_dir():
            self.output_dir_edit.setText(output_dir)

        if "suffix_enabled" in data:
            self.suffix_check.setChecked(bool(data["suffix_enabled"]))

        if isinstance(suffix := data.get("suffix"), str):
            self.suffix_edit.setText(suffix)

        if isinstance(resume_queue := data.get("resume_queue", []), list):
            self.resume_queue_paths = [str(p) for p in resume_queue if isinstance(p, str)]

    def _save_settings(self) -> None:
        """Persist current UI settings to settings.json.
        現在のUI設定を settings.json に保存する。"""
        config_path = resolve_launch_dir() / CONFIG_FILENAME
        data = {
            "ffmpeg_dir":        self.ffmpeg_dir_edit.text().strip(),
            "preset":            self.preset_combo.currentText(),
            "priority":          self.priority_combo.currentText(),
            "crf":               self.crf_slider.value(),
            "same_as_input_dir": self.same_as_input_dir_check.isChecked(),
            "output_dir":        self.output_dir_edit.text().strip(),
            "suffix_enabled":    self.suffix_check.isChecked(),
            "suffix":            self.suffix_edit.text(),
            "resume_queue":      self.resume_queue_paths,
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _set_resume_queue(self, paths: list[Path]) -> None:
        """Save a list of paths as the resume queue and persist settings.
        再開キューをパスリストとして保存し、設定をファイルに書き出す。"""
        self.resume_queue_paths = [str(p.resolve()) for p in paths if p.exists()]
        self._save_settings()

    def _clear_resume_queue(self) -> None:
        """Clear the resume queue and persist settings.
        再開キューをクリアし、設定をファイルに書き出す。"""
        self.resume_queue_paths = []
        self._save_settings()

    def _restore_resume_queue_if_available(self) -> None:
        """If a saved resume queue exists, prompt to restore it to the input list.
        前回停止時のキューが保存されていれば、入力リストへ復元するか確認する。"""
        if not self.resume_queue_paths:
            return

        # Filter to paths that still exist / 存在するパスだけ復元候補とする
        restore_candidates = [Path(p) for p in self.resume_queue_paths if Path(p).exists()]
        if not restore_candidates:
            self._clear_resume_queue()
            return

        answer = QMessageBox.question(
            self,
            "前回停止したキュー",
            f"前回停止時のキューが {len(restore_candidates)} 件あります。入力リストへ復元しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return

        self.input_table.add_paths(restore_candidates)
        self._append_log(f"[INFO] 前回停止時のキュー {len(restore_candidates)} 件を復元しました。")
        self._clear_resume_queue()

    def closeEvent(self, event) -> None:
        """Save settings when the window is closed.
        ウィンドウを閉じる際に設定を保存する。"""
        self._save_settings()
        super().closeEvent(event)

    # ──────────────────────────────────────────
    # Drag & drop / ドラッグ＆ドロップ
    # ──────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        accept_url_drag(event)

    def dragMoveEvent(self, event) -> None:
        accept_url_drag(event)

    # ──────────────────────────────────────────
    # Log & UI state helpers / ログ・UIの制御
    # ──────────────────────────────────────────

    @staticmethod
    def _decode_output(qba) -> str:
        """Decode QByteArray output from ffmpeg to a string.
        ffmpeg の QByteArray 出力を文字列にデコードする。"""
        return bytes(qba).decode("utf-8", errors="replace")

    def _on_dropped(self, added: int) -> None:
        """Handle files dropped onto the input table.
        入力テーブルにファイルがドロップされたときの処理。"""
        self._append_log(f"[INFO] ドロップで {added} 件追加しました。")

    def _on_right_clicked(self, input_path: Path, pos: QPoint) -> None:
        """Handle right-click on input table to show folder open menu.
        入力テーブル右クリックでフォルダを開くメニューを表示。"""
        menu = QMenu(self)
        open_input_folder_action = QAction("入力元のフォルダを開く", self)
        open_input_folder_action.triggered.connect(lambda: os.startfile(str(input_path.parent)))
        menu.addAction(open_input_folder_action)

        base_dir = Path(self.output_dir_edit.text()) if self.output_dir_edit.text() else input_path.parent
        open_output_folder_action = QAction("出力先のフォルダを開く", self)
        open_output_folder_action.triggered.connect(lambda: os.startfile(str(base_dir)))
        menu.addAction(open_output_folder_action)

        menu.exec(pos)

    def _append_log(self, text: str) -> None:
        """Append text to the log panel and scroll to the bottom if visible.
        ログパネルにテキストを追記し、表示中であれば最下部へスクロールする。"""
        self.log.appendPlainText(text.rstrip())
        if self.log.isVisible():
            bar = self.log.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _toggle_log(self, expanded: bool) -> None:
        """Show or hide the log text area and update the group title.
        ログテキストエリアの表示/非表示を切り替えてグループタイトルを更新する。"""
        self.log.setVisible(expanded)
        self.log_group.setTitle("ログ（クリックで折りたたみ）" if expanded else "ログ（展開して表示）")

    def _toggle_output_dir_mode(self, checked: bool) -> None:
        """Enable or disable the custom output dir widgets based on the checkbox.
        チェックボックス状態に応じてカスタム出力フォルダウィジェットを有効/無効にする。"""
        enabled = not checked
        for w in (self.output_dir_edit, self.output_dir_btn, self.output_dir_reset_btn):
            w.setEnabled(enabled)

    def _toggle_suffix_mode(self, checked: bool) -> None:
        """Enable or disable the suffix text field based on the checkbox.
        チェックボックス状態に応じてサフィックステキストフィールドを有効/無効にする。"""
        self.suffix_edit.setEnabled(checked)

    def _update_crf_label(self, value: int) -> None:
        """Update the CRF value display label when the slider changes.
        スライダーの変更に合わせてCRF値表示ラベルを更新する。"""
        self.crf_value_label.setText(str(value))

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Disable settings/input widgets during encoding; re-enable after.
        エンコード中は設定・入力系UIを無効化し、終了後に再度有効化する。"""
        for w in (
            self.ffmpeg_dir_edit, self.ffmpeg_dir_browse_btn,
            self.preset_combo, self.priority_combo, self.crf_slider,
            self.same_as_input_dir_check, self.suffix_check,
            self.add_input_btn, self.remove_input_btn, self.clear_input_btn,
        ):
            w.setEnabled(enabled)
        self.input_table.setAcceptDrops(enabled)
        self.setAcceptDrops(enabled)

        if enabled:
            self._toggle_output_dir_mode(self.same_as_input_dir_check.isChecked())
            self._toggle_suffix_mode(self.suffix_check.isChecked())
        else:
            for w in (self.output_dir_edit, self.output_dir_btn, self.output_dir_reset_btn, self.suffix_edit):
                w.setEnabled(False)

    # ──────────────────────────────────────────
    # Progress display / 進捗表示
    # ──────────────────────────────────────────

    def _reset_current_progress_stats(self, *, start_now: bool = False) -> None:
        """Reset per-file progress state. Optionally record the start time.
        ファイル単位の進捗状態をリセットする。start_now=True で開始時刻も記録する。"""
        self.current_start_time = time.monotonic() if start_now else 0.0
        self.current_duration_sec = None
        self.current_encoded_sec = 0.0
        self.current_fps_text = "-"
        self.current_bitrate_text = "-"
        self._render_current_progress_stats()

    def _render_current_progress_stats(self) -> None:
        """Update the stats label with elapsed time, ETA, fps, and bitrate.
        経過時間・残り時間推定・fps・bitrateを統計ラベルに反映する。"""
        elapsed = max(0.0, time.monotonic() - self.current_start_time) if self.current_start_time > 0 else 0.0

        eta_text = "--:--:--"
        if self.current_duration_sec and self.current_encoded_sec > 0:
            ratio = self.current_encoded_sec / self.current_duration_sec
            if 0 < ratio < 1:
                eta_text = format_seconds_as_hms((elapsed / ratio) - elapsed if elapsed > 0 else None)
            elif ratio >= 1:
                eta_text = "00:00:00"

        self.stats_label.setText(
            f"経過: {format_seconds_as_hms(elapsed)} / "
            f"残り(推定): {eta_text} / "
            f"fps: {self.current_fps_text} / "
            f"bitrate: {self.current_bitrate_text}"
        )

    def _update_progress_from_line(self, line: str) -> None:
        """Parse a single line of ffmpeg stderr and update the progress display.
        ffmpeg stderr の1行を解析して進捗表示を更新する。
        Extracts: Duration, current time, fps, bitrate.
        抽出対象: Duration・現在時刻・fps・bitrate
        """
        if (m := FFMPEG_DURATION_RE.search(line)) and self.current_duration_sec is None:
            self.current_duration_sec = parse_hhmmss_to_seconds(m.group(1), m.group(2), m.group(3))

        if m := FFMPEG_TIME_RE.search(line):
            self.current_encoded_sec = parse_hhmmss_to_seconds(m.group(1), m.group(2), m.group(3))

        if m := FFMPEG_FPS_RE.search(line):
            self.current_fps_text = m.group(1)

        if m := FFMPEG_BITRATE_RE.search(line):
            self.current_bitrate_text = m.group(1)

        self._render_current_progress_stats()

    # ──────────────────────────────────────────
    # Input / output folder selection
    # 入力・出力フォルダ選択
    # ──────────────────────────────────────────

    def _select_output_dir(self) -> None:
        """Open a folder picker for the custom output directory.
        カスタム出力フォルダ選択ダイアログを開く。"""
        directory = QFileDialog.getExistingDirectory(self, "出力フォルダを選択", self.output_dir_edit.text().strip() or "")
        if directory:
            self.output_dir_edit.setText(directory)

    def _select_input_files(self) -> None:
        """Open a file picker for input video files.
        入力動画ファイル選択ダイアログを開く。"""
        paths, _ = QFileDialog.getOpenFileNames(self, "入力動画を選択", "", VIDEO_FILTER)
        if not paths:
            return
        added = self.input_table.add_paths([Path(p) for p in paths])
        if added == 0:
            self._append_log("[INFO] 追加可能な新規動画はありませんでした。")

    # ──────────────────────────────────────────
    # Validation & path construction
    # バリデーション・パス構築
    # ──────────────────────────────────────────

    def _validate_before_start(self) -> bool:
        """Validate input list and output directory before starting encoding.
        エンコード開始前に入力リストと出力フォルダを検証する。"""
        if self.input_table.rowCount() == 0:
            QMessageBox.warning(self, "入力エラー", "入力リストに動画を追加してください。")
            return False

        if self.same_as_input_dir_check.isChecked():
            return True

        output_dir_text = self.output_dir_edit.text().strip()
        if not output_dir_text:
            QMessageBox.warning(self, "出力エラー", "出力フォルダを指定してください。")
            return False

        if not (output_dir := Path(output_dir_text)).exists() or not output_dir.is_dir():
            QMessageBox.warning(self, "出力エラー", "有効な出力フォルダを指定してください。")
            return False

        return True

    def _has_suffix(self) -> bool:
        """Return True if a non-empty suffix is enabled.
        有効で空でないサフィックスが設定されていれば True を返す。"""
        return self.suffix_check.isChecked() and bool(self.suffix_edit.text().strip())

    def _confirm_overwrite_risk(self) -> bool:
        """Warn the user when no suffix is set and overwrite is likely.
        サフィックスがない場合に上書きリスクを警告し、続行を確認する。"""
        if self._has_suffix():
            return True

        answer = QMessageBox.warning(
            self,
            "上書き注意",
            "サフィックスが無効または空です。\n"
            "出力ファイル名が入力と同名になり、上書きされる可能性があります。\n"
            "このまま続行しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _build_output_path(self, input_path: Path) -> Path:
        """Construct the final output file path for a given input.
        入力パスに対する最終出力ファイルパスを構築する。"""
        output_dir = input_path.parent if self.same_as_input_dir_check.isChecked() else Path(self.output_dir_edit.text().strip())
        suffix = self.suffix_edit.text().strip() if self.suffix_check.isChecked() else ""
        stem = f"{input_path.stem}{suffix}" if suffix else input_path.stem
        return output_dir / f"{stem}{input_path.suffix}"

    def _build_args(self, input_path: Path, output_path: Path) -> list[str]:
        """Build the ffmpeg command-line arguments for a single encode job.
        1ファイル分のエンコードに使う ffmpeg コマンドライン引数を構築する。"""
        return [
            "-y", "-i", str(input_path),
            "-c:v", "libx265",
            "-preset", self.preset_combo.currentText(),
            "-crf", str(self.crf_slider.value()),
            "-c:a", "copy",
            str(output_path),
        ]

    # ──────────────────────────────────────────
    # Encoding execution / エンコード実行
    # ──────────────────────────────────────────

    def start_encode(self) -> None:
        """Start sequential encoding of all files in the input list.
        入力リストの全ファイルを逐次エンコードする処理を開始する。"""
        if self.process.state() != QProcess.NotRunning:
            return
        if not self._validate_ffmpeg():
            return
        if not self._validate_before_start() or not self._confirm_overwrite_risk():
            return

        self._clear_resume_queue()
        self.pending_inputs = deque(self.input_table.paths_in_display_order())
        if not self.pending_inputs:
            QMessageBox.warning(self, "入力エラー", "存在する入力動画がありません。")
            return

        self.total_count = len(self.pending_inputs)
        self.success_count = 0
        self.failed_items = []
        self.stop_requested = False

        self._set_controls_enabled(False)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setRange(0, self.total_count)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m 件 (%p%)")
        self.progress.setVisible(True)
        self._reset_current_progress_stats()

        self._append_log(f"[INFO] {self.total_count} 件の逐次エンコードを開始します。")
        self._start_next_encode()

    def _start_next_encode(self) -> None:
        """Dequeue and start encoding the next file, or finish if queue is empty.
        次のファイルをキューから取り出してエンコード開始する。キューが空なら完了処理へ。"""
        if not self.pending_inputs:
            self._finish_all()
            return

        self.current_input = self.pending_inputs.popleft()
        self.input_table.set_current_encoding_path(self.current_input)
        self.current_output = self._build_output_path(self.current_input)
        self.current_temp_output = self.current_output.with_suffix(f".tmp{self.current_output.suffix}")

        output_path = self.current_temp_output

        args = self._build_args(self.current_input, output_path)
        self.current_error_lines.clear()
        self._reset_current_progress_stats(start_now=True)

        self._append_log("")
        self._append_log(f"[INFO] 開始: {self.current_input.name}")
        self._append_log(f"[INFO] 出力: {output_path}")
        self._append_log("$ " + self.ffmpeg_exe_path + " " + " ".join(shlex.quote(a) for a in args))

        self.process.start(self.ffmpeg_exe_path, args)

    def _apply_process_priority(self) -> None:
        """Set the Windows process priority class for the running ffmpeg process.
        実行中の ffmpeg プロセスに Windows プロセス優先度クラスを設定する。
        No-op on non-Windows platforms. / Windows以外では何もしない。"""
        if sys.platform != "win32":
            return

        pid = int(self.process.processId())
        if pid <= 0:
            return

        priority_name = self.priority_combo.currentText()
        priority_class = PRIORITY_CLASSES.get(priority_name, PRIORITY_CLASSES[DEFAULT_PRIORITY])

        # Open process handle with SET_INFORMATION access right
        # SET_INFORMATION アクセス権でプロセスハンドルを開く
        handle = ctypes.windll.kernel32.OpenProcess(0x0200, False, pid)
        if not handle:
            self._append_log(f"[WARN] 優先度設定に失敗しました (OpenProcess): PID={pid}")
            return

        try:
            if ctypes.windll.kernel32.SetPriorityClass(handle, priority_class):
                self._append_log(f"[INFO] 優先度を '{priority_name}' に設定しました。")
            else:
                self._append_log(f"[WARN] 優先度設定に失敗しました (SetPriorityClass): PID={pid}")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def stop_encode(self) -> None:
        """Stop the current encode and save the remaining queue for resume.
        現在のエンコードを停止し、残りのキューを次回起動時の再開用に保存する。"""
        self.stop_requested = True
        # Save current input + remaining queue for resume
        # 現在処理中ファイル + 残りキューを再開用に保存
        queued_paths = list(self.pending_inputs)
        if self.current_input is not None:
            queued_paths.insert(0, self.current_input)
        self._set_resume_queue(queued_paths)
        self.pending_inputs.clear()
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self._append_log("[INFO] エンコードを停止しました。")
        else:
            self._finish_all()

    # ──────────────────────────────────────────
    # Process output reading & completion
    # プロセス出力の読み取り・完了処理
    # ──────────────────────────────────────────

    def _read_stdout(self) -> None:
        """Read and log stdout from the ffmpeg process.
        ffmpeg プロセスの stdout を読み込んでログに追記する。"""
        if data := self._decode_output(self.process.readAllStandardOutput()):
            self._append_log(data)

    def _read_stderr(self) -> None:
        """Read stderr from ffmpeg, log it, and update per-file progress.
        ffmpeg の stderr を読み込み、ログ追記と進捗更新を行う。"""
        if not (data := self._decode_output(self.process.readAllStandardError())):
            return
        self._append_log(data)
        for line in data.splitlines():
            if stripped := line.strip():
                self.current_error_lines.append(stripped)
                self._update_progress_from_line(stripped)

    def _handle_finished(self, code: int, _status) -> None:
        """Handle ffmpeg process completion: finalize output, update table, continue queue.
        ffmpeg プロセス完了時の処理: 出力の確定・テーブル更新・次のキュー処理を行う。"""
        if self.current_input is None:
            if self.stop_requested:
                self._finish_all()
            else:
                self._start_next_encode()
            return

        final_output = self.current_output

        if code == 0:
            # Success: move original to recycle bin and rename temp to final
            # 成功: 元ファイルをゴミ箱へ、一時ファイルを最終名に
            try:
                if self.current_output.exists():
                    ok, reason = move_to_recycle_bin(self.current_output)
                    if not ok:
                        raise OSError(f"既存ファイルをゴミ箱へ移動できませんでした: {reason}")
                self.current_temp_output.replace(self.current_output)
                self.input_table.update_encode_success(self.current_input, self.current_output)
                self.success_count += 1
                self._append_log(f"[OK] 完了: {self.current_input.name}")
            except OSError as exc:
                reason = f"一時ファイルの置換に失敗: {exc}"
                self.failed_items.append((self.current_input.name, reason))
                self._append_log(f"[ERROR] 失敗: {self.current_input.name} - {reason}")
                self.input_table.set_result_error(self.current_input, "ファイルの置換に失敗しました")
                self.progress.setValue(self.success_count + len(self.failed_items))
                self._cleanup_temp_output()
                self._clear_current_io_state()
                self._next_or_finish()
                return
        elif self.stop_requested:
            # User-requested stop / ユーザーによる停止
            self._append_log(f"[INFO] 停止: {self.current_input.name}")
            self._cleanup_temp_output()
            self.progress.setValue(self.success_count + len(self.failed_items))
            self._clear_current_io_state()
            self._finish_all()
            return
        else:
            # Encoding error / エンコードエラー
            reason = self._extract_failure_reason(code)
            self.failed_items.append((self.current_input.name, reason))
            self._append_log(f"[ERROR] 失敗: {self.current_input.name} - {reason}")
            self.input_table.set_result_error(self.current_input, translate_ffmpeg_error(reason, code))
            self._cleanup_temp_output()

        self.progress.setValue(self.success_count + len(self.failed_items))
        self._clear_current_io_state()
        self._next_or_finish()

    def _next_or_finish(self) -> None:
        """Continue to the next file or finalize if stop was requested.
        停止要求がなければ次のファイルへ、あれば完了処理へ進む。"""
        if self.stop_requested:
            self._finish_all()
        else:
            self._start_next_encode()

    def _extract_failure_reason(self, code: int) -> str:
        """Extract the most relevant error line from recent ffmpeg stderr output.
        直近の ffmpeg stderr から最も関連性の高いエラー行を抽出する。"""
        fallback: str | None = None
        for line in reversed(self.current_error_lines):
            lower = line.lower()
            if any(kw in lower for kw in ("error", "failed", "invalid", "could not")):
                return line
            if fallback is None and line:
                fallback = line
        return fallback or f"ffmpeg終了コード: {code}"

    def _cleanup_temp_output(self) -> None:
        """Remove the temporary output file if it exists.
        一時出力ファイルが存在すれば削除する。"""
        if self.current_temp_output and self.current_temp_output.exists():
            try:
                self.current_temp_output.unlink()
            except OSError:
                pass

    def _clear_current_io_state(self) -> None:
        """Reset current input/output path references and progress stats.
        現在の入出力パス参照と進捗情報をリセットする。"""
        self._cleanup_temp_output()
        self.current_input = None
        self.current_output = None
        self.current_temp_output = None
        self._reset_current_progress_stats()
        self.input_table.set_current_encoding_path(None)

    def _finish_all(self) -> None:
        """Finalize the encoding session: re-enable UI, show summary dialog.
        エンコードセッションを終了する: UIを再有効化してサマリーダイアログを表示する。"""
        self._set_controls_enabled(True)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setValue(self.progress.maximum())
        self.progress.setVisible(False)
        self._reset_current_progress_stats()

        failed_count = len(self.failed_items)
        processed_count = self.success_count + failed_count
        total_before_size, total_after_size = self.input_table.aggregate_sizes()
        reduction_ratio = (
            ((total_after_size - total_before_size) / total_before_size) * 100.0
            if total_before_size > 0 else 0.0
        )

        # Log the summary / サマリーをログに出力
        self._append_log("")
        self._append_log("[INFO] 処理サマリー")
        self._append_log(f"[INFO] 変換成功: {self.success_count} 件")
        self._append_log(f"[INFO] 変換失敗: {failed_count} 件")
        self._append_log(f"[INFO] 合計(処理前): {format_bytes(total_before_size)}")
        self._append_log(f"[INFO] 合計(処理後): {format_bytes(total_after_size)}")
        self._append_log(f"[INFO] 削減率: {reduction_ratio:+.2f}%")

        # Log failure details (dialog shows count only)
        # 失敗詳細はログのみへ（ダイアログには件数だけ表示）
        if failed_count > 0:
            self._append_log("[INFO] 失敗理由一覧:")
            for name, reason in self.failed_items:
                self._append_log(f"  - {name}: {reason}")

        summary_lines = [
            f"変換成功: {self.success_count} 件",
            f"変換失敗: {failed_count} 件",
            f"処理対象: {self.total_count} 件",
            f"処理完了: {processed_count} 件",
            f"合計(処理前): {format_bytes(total_before_size)}",
            f"合計(処理後): {format_bytes(total_after_size)}",
            f"削減率: {reduction_ratio:+.2f}%",
        ]
        if failed_count > 0:
            summary_lines.append(f"\n※ エラー詳細はリストの「結果」列またはログをご確認ください。")

        title = "処理結果（停止）" if self.stop_requested else "処理結果"
        QMessageBox.information(self, title, "\n".join(summary_lines))

        # Clean up session state / セッション状態をクリーンアップ
        self.pending_inputs.clear()
        self._clear_current_io_state()
        self.current_error_lines.clear()
        if not self.stop_requested:
            self._clear_resume_queue()
        self.stop_requested = False

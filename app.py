import ctypes
import shlex
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".ts",
    ".mts",
    ".m2ts",
}

X265_PRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
    "placebo",
]

PRIORITY_CLASSES = {
    "Low": 0x00000040,
    "Below Normal": 0x00004000,
    "Normal": 0x00000020,
    "Above Normal": 0x00008000,
    "High": 0x00000080,
}


def find_ffmpeg() -> str:
    app_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = [
        app_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(__file__).resolve().parent / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return "ffmpeg"


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


class InputListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        paths: list[Path] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            candidate = Path(url.toLocalFile())
            if is_video_file(candidate):
                paths.append(candidate)

        self.add_paths(paths)
        event.acceptProposedAction()

    def add_paths(self, paths: list[Path]) -> int:
        existing = {self.item(i).data(Qt.UserRole) for i in range(self.count())}
        added = 0
        for path in paths:
            normalized = str(path.resolve())
            if normalized in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setToolTip(normalized)
            item.setData(Qt.UserRole, normalized)
            self.addItem(item)
            existing.add(normalized)
            added += 1
        return added


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FFmpeg MultiEncoder")
        self.resize(1080, 800)

        self.ffmpeg_path = find_ffmpeg()
        self.pending_inputs: list[Path] = []
        self.current_input: Path | None = None
        self.stop_requested = False

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)

        self._build_ui()
        self._connect_signals()
        self.toggle_output_dir_mode(self.same_as_input_dir_check.isChecked())
        self.toggle_suffix_mode(self.suffix_check.isChecked())

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QGridLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(8)

        self.encoder_label = QLabel("libx265 (CPU)")

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(X265_PRESETS)
        self.preset_combo.setCurrentText("slow")
        self.preset_combo.setToolTip(
            "x265 preset controls speed vs compression efficiency. "
            "Faster presets encode quickly but are less efficient. "
            "Slower presets are more efficient but take longer."
        )

        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(20)
        self.crf_slider.setSingleStep(1)
        self.crf_slider.setPageStep(1)
        self.crf_slider.setToolTip(
            "CRF controls quality vs size. "
            "Lower = higher quality / larger files. "
            "Higher = lower quality / smaller files."
        )
        self.crf_value_label = QLabel("20")

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(list(PRIORITY_CLASSES.keys()))
        self.priority_combo.setCurrentText("Below Normal")
        self.priority_combo.setToolTip("Process priority used for ffmpeg encoding.")

        self.same_as_input_dir_check = QCheckBox("入力ファイルと同じフォルダに出力")
        self.same_as_input_dir_check.setChecked(True)

        self.output_dir_edit = QLineEdit()
        self.output_dir_btn = QPushButton("出力フォルダ")

        self.suffix_check = QCheckBox("ファイル名にサフィックスを付ける")
        self.suffix_check.setChecked(True)
        self.suffix_edit = QLineEdit("_x265")
        self.suffix_edit.setPlaceholderText("例: _x265")

        self.input_list = InputListWidget()
        self.input_list.setMinimumHeight(320)

        self.add_input_btn = QPushButton("動画を追加")
        self.remove_input_btn = QPushButton("選択を削除")
        self.clear_input_btn = QPushButton("すべて削除")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        self.run_btn = QPushButton("エンコード開始")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)

        self.log_group = QGroupBox("ログ（展開して表示）")
        self.log_group.setCheckable(True)
        self.log_group.setChecked(False)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setVisible(False)

        log_layout = QVBoxLayout(self.log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.addWidget(self.log)

        row = 0
        layout.addWidget(QLabel("ffmpeg"), row, 0)
        layout.addWidget(QLabel(self.ffmpeg_path), row, 1, 1, 5)

        row += 1
        layout.addWidget(QLabel("Encoder"), row, 0)
        layout.addWidget(self.encoder_label, row, 1)
        layout.addWidget(QLabel("Preset"), row, 2)
        layout.addWidget(self.preset_combo, row, 3)
        layout.addWidget(QLabel("Priority"), row, 4)
        layout.addWidget(self.priority_combo, row, 5)

        row += 1
        layout.addWidget(QLabel("CRF"), row, 0)
        layout.addWidget(self.crf_slider, row, 1, 1, 4)
        layout.addWidget(self.crf_value_label, row, 5)

        row += 1
        layout.addWidget(self.same_as_input_dir_check, row, 0, 1, 6)

        row += 1
        layout.addWidget(QLabel("出力フォルダ"), row, 0)
        layout.addWidget(self.output_dir_edit, row, 1, 1, 4)
        layout.addWidget(self.output_dir_btn, row, 5)

        row += 1
        layout.addWidget(self.suffix_check, row, 0, 1, 2)
        layout.addWidget(QLabel("サフィックス"), row, 2)
        layout.addWidget(self.suffix_edit, row, 3, 1, 3)

        row += 1
        layout.addWidget(QLabel("入力リスト（ドラッグ&ドロップ可）"), row, 0, 1, 6)

        row += 1
        layout.addWidget(self.input_list, row, 0, 1, 6)

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
        layout.addWidget(self.log_group, row, 0, 1, 6)

    def _connect_signals(self) -> None:
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        self.same_as_input_dir_check.toggled.connect(self.toggle_output_dir_mode)
        self.suffix_check.toggled.connect(self.toggle_suffix_mode)

        self.add_input_btn.clicked.connect(self.select_input_files)
        self.remove_input_btn.clicked.connect(self.remove_selected_inputs)
        self.clear_input_btn.clicked.connect(self.input_list.clear)

        self.run_btn.clicked.connect(self.start_encode)
        self.stop_btn.clicked.connect(self.stop_encode)
        self.crf_slider.valueChanged.connect(self.update_crf_label)
        self.log_group.toggled.connect(self.toggle_log)

        self.process.started.connect(self.apply_process_priority)
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.handle_finished)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text.rstrip())
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def toggle_log(self, expanded: bool) -> None:
        self.log.setVisible(expanded)
        self.log_group.setTitle("ログ（クリックで折りたたみ）" if expanded else "ログ（展開して表示）")

    def toggle_output_dir_mode(self, checked: bool) -> None:
        self.output_dir_edit.setEnabled(not checked)
        self.output_dir_btn.setEnabled(not checked)

    def toggle_suffix_mode(self, checked: bool) -> None:
        self.suffix_edit.setEnabled(checked)

    def update_crf_label(self, value: int) -> None:
        self.crf_value_label.setText(str(value))

    def select_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "出力フォルダを選択", self.output_dir_edit.text().strip() or "")
        if directory:
            self.output_dir_edit.setText(directory)

    def select_input_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "入力動画を選択",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.ts *.mts *.m2ts);;All Files (*.*)",
        )
        if not paths:
            return
        added = self.input_list.add_paths([Path(p) for p in paths])
        if added == 0:
            self.append_log("[INFO] 追加可能な新規動画はありませんでした。")

    def remove_selected_inputs(self) -> None:
        for item in self.input_list.selectedItems():
            self.input_list.takeItem(self.input_list.row(item))

    def _validate(self) -> bool:
        if self.input_list.count() == 0:
            QMessageBox.warning(self, "入力エラー", "入力リストに動画を追加してください。")
            return False

        if not self.same_as_input_dir_check.isChecked():
            output_dir_text = self.output_dir_edit.text().strip()
            if not output_dir_text:
                QMessageBox.warning(self, "出力エラー", "出力フォルダを指定してください。")
                return False

            output_dir = Path(output_dir_text)
            if not output_dir.exists() or not output_dir.is_dir():
                QMessageBox.warning(self, "出力エラー", "有効な出力フォルダを指定してください。")
                return False

        return True

    def has_suffix(self) -> bool:
        return self.suffix_check.isChecked() and bool(self.suffix_edit.text().strip())

    def confirm_overwrite_risk(self) -> bool:
        if self.has_suffix():
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

    def build_output_path(self, input_path: Path) -> Path:
        output_dir = input_path.parent if self.same_as_input_dir_check.isChecked() else Path(self.output_dir_edit.text().strip())

        suffix = self.suffix_edit.text().strip() if self.suffix_check.isChecked() else ""
        output_stem = f"{input_path.stem}{suffix}" if suffix else input_path.stem
        return output_dir / f"{output_stem}{input_path.suffix}"

    def build_args(self, input_path: Path, output_path: Path) -> list[str]:
        preset = self.preset_combo.currentText()
        crf = self.crf_slider.value()
        return [
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx265",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-c:a",
            "copy",
            str(output_path),
        ]

    def collect_queue(self) -> list[Path]:
        queue: list[Path] = []
        for i in range(self.input_list.count()):
            path = Path(self.input_list.item(i).data(Qt.UserRole))
            if path.exists():
                queue.append(path)
        return queue

    def start_encode(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            return
        if not self._validate():
            return
        if not self.confirm_overwrite_risk():
            return

        self.pending_inputs = self.collect_queue()
        if not self.pending_inputs:
            QMessageBox.warning(self, "入力エラー", "存在する入力動画がありません。")
            return

        self.stop_requested = False
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)

        self.append_log(f"[INFO] {len(self.pending_inputs)} 件の逐次エンコードを開始します。")
        self.start_next_encode()

    def start_next_encode(self) -> None:
        if not self.pending_inputs:
            self.finish_all("[OK] すべてのエンコードが完了しました。")
            return

        self.current_input = self.pending_inputs.pop(0)
        output_path = self.build_output_path(self.current_input)
        args = self.build_args(self.current_input, output_path)

        self.append_log("")
        self.append_log(f"[INFO] 開始: {self.current_input.name}")
        self.append_log(f"[INFO] 出力: {output_path}")
        self.append_log("$ " + self.ffmpeg_path + " " + " ".join(shlex.quote(a) for a in args))

        self.process.start(self.ffmpeg_path, args)

    def apply_process_priority(self) -> None:
        if sys.platform != "win32":
            return

        pid = int(self.process.processId())
        if pid <= 0:
            return

        priority_name = self.priority_combo.currentText()
        priority_class = PRIORITY_CLASSES.get(priority_name, PRIORITY_CLASSES["Below Normal"])

        PROCESS_SET_INFORMATION = 0x0200
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
        if not handle:
            self.append_log(f"[WARN] 優先度設定に失敗しました (OpenProcess): PID={pid}")
            return

        try:
            ok = ctypes.windll.kernel32.SetPriorityClass(handle, priority_class)
            if ok:
                self.append_log(f"[INFO] 優先度を '{priority_name}' に設定しました。")
            else:
                self.append_log(f"[WARN] 優先度設定に失敗しました (SetPriorityClass): PID={pid}")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def stop_encode(self) -> None:
        self.stop_requested = True
        self.pending_inputs.clear()
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.append_log("[INFO] エンコードを停止しました。")
        self.finish_buttons_only()

    def read_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.append_log(data)

    def read_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            self.append_log(data)

    def handle_finished(self, code: int, _status) -> None:
        if self.current_input is not None:
            if code == 0:
                self.append_log(f"[OK] 完了: {self.current_input.name}")
            else:
                self.append_log(f"[ERROR] 失敗: {self.current_input.name} (code={code})")

        if self.stop_requested:
            self.finish_all("[INFO] 停止しました。")
            return

        self.start_next_encode()

    def finish_buttons_only(self) -> None:
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)

    def finish_all(self, message: str) -> None:
        self.finish_buttons_only()
        self.pending_inputs.clear()
        self.current_input = None
        self.stop_requested = False
        self.append_log(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FFmpeg MultiEncoder")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
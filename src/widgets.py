"""
widgets.py - Custom Qt widgets for FFmpeg MultiEncoder
           / FFmpeg MultiEncoder 用カスタム Qt ウィジェット

Provides InputTableWidget: a sortable, drag-and-drop-enabled table
for managing input video files and displaying encoding results.
入力動画ファイルの管理とエンコード結果表示に使う、
ソート・ドラッグ＆ドロップ対応のテーブルウィジェットを提供する。
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from src.constants import (
    COL_NAME, COL_BEFORE, COL_AFTER, COL_RATIO, COL_RESULT, COL_PATH,
    HEADER_LABELS, HEADER_TOOLTIPS,
    COLOR_RATIO_INCREASE, COLOR_RATIO_DECREASE,
)
from src.utils import accept_url_drag, extract_video_paths, format_bytes

# Result column colors / 結果列のカラー定義
_COLOR_OK = COLOR_RATIO_DECREASE    # Completed (green) / 完了 → 緑
_COLOR_NG = COLOR_RATIO_INCREASE    # Error (red)       / エラー → 赤


class SortableItem(QTableWidgetItem):
    """
    A QTableWidgetItem that sorts by its UserRole numeric value when available,
    falling back to text comparison.
    UserRole の数値を優先して比較し、なければテキストで比較するテーブル項目。
    """

    def __lt__(self, other) -> bool:
        left = self.data(Qt.UserRole)
        right = other.data(Qt.UserRole)
        if left is not None and right is not None:
            return left < right
        return self.text() < other.text()


class InputTableWidget(QTableWidget):
    """
    Table widget for managing input video files.
    入力動画ファイルを管理するテーブルウィジェット。

    - Accepts drag & drop of video files and folders.
      動画ファイル・フォルダのドラッグ＆ドロップを受け付ける。
    - Prevents duplicate entries via resolved path tracking.
      解決済みパスで重複登録を防ぐ。
    - Supports column sorting by clicking headers.
      ヘッダークリックで列ソートができる。
    - Displays before/after size, change ratio, and result per row.
      処理前後サイズ・変化率・結果を行ごとに表示する。
    """

    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(list(HEADER_LABELS))
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setToolTip("動画をドラッグ＆ドロップ、または追加ボタンで登録します。")
        self.setSortingEnabled(True)

        header = self.horizontalHeader()
        # All columns user-resizable; path column stretches to fill remaining space.
        # 全列をユーザーがリサイズ可能に。パス列は残り幅を埋めるStretch。
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(COL_PATH, QHeaderView.Stretch)

        # Initial column widths / 初期列幅の設定
        self.setColumnWidth(COL_NAME,   200)
        self.setColumnWidth(COL_BEFORE, 100)
        self.setColumnWidth(COL_AFTER,  100)
        self.setColumnWidth(COL_RATIO,   90)
        self.setColumnWidth(COL_RESULT, 180)

        # Apply tooltips to header items / ヘッダー項目にツールチップを設定
        for col, tooltip in enumerate(HEADER_TOOLTIPS):
            if item := self.horizontalHeaderItem(col):
                item.setToolTip(tooltip)

    # ------------------------------------------------------------------
    # Drag & drop event handlers / ドラッグ＆ドロップ イベントハンドラ
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        accept_url_drag(event)

    def dragMoveEvent(self, event) -> None:
        accept_url_drag(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        added = self.add_paths(extract_video_paths(event.mimeData().urls()))
        if added > 0:
            event.acceptProposedAction()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Internal helpers / 内部ヘルパー
    # ------------------------------------------------------------------

    def _existing_paths(self) -> set[str]:
        """Return resolved path strings for all rows already in the table.
        テーブルに登録済みの解決済みパス文字列セットを返す。"""
        return {
            item.data(Qt.UserRole)
            for row in range(self.rowCount())
            if (item := self.item(row, COL_PATH)) is not None
        }

    # ------------------------------------------------------------------
    # Public API / 公開 API
    # ------------------------------------------------------------------

    def add_paths(self, paths: list[Path]) -> int:
        """
        Add video paths to the table, skipping duplicates.
        Returns the number of newly added rows.
        動画パスをテーブルに追加する（重複はスキップ）。追加した行数を返す。
        """
        existing = self._existing_paths()
        added = 0

        # Disable sorting during batch insert to preserve order
        # 一括挿入中はソートを無効化して順序を維持する
        self.setSortingEnabled(False)
        try:
            for path in paths:
                resolved = str(path.resolve())
                if resolved in existing:
                    continue  # Skip duplicates / 重複をスキップ

                try:
                    before_size = path.stat().st_size
                except OSError:
                    before_size = None

                row = self.rowCount()
                self.insertRow(row)

                # File name cell / ファイル名セル
                name_item = SortableItem(path.name)
                name_item.setToolTip(resolved)

                # Size before encoding / 処理前サイズ
                before_item = SortableItem(format_bytes(before_size))
                before_item.setData(Qt.UserRole, before_size if before_size is not None else -1)
                before_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # Size after encoding (placeholder) / 処理後サイズ（未処理時はプレースホルダ）
                after_item = SortableItem("-")
                after_item.setData(Qt.UserRole, -1)
                after_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # Size change ratio (placeholder) / 変化率（未処理時はプレースホルダ）
                ratio_item = SortableItem("-")
                ratio_item.setData(Qt.UserRole, 0.0)
                ratio_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # Result cell (placeholder) / 結果セル（未処理時はプレースホルダ）
                result_item = SortableItem("-")
                result_item.setTextAlignment(Qt.AlignCenter)

                # Full path cell (used for deduplication and lookup)
                # フルパスセル（重複排除・行検索に使用）
                path_item = SortableItem(resolved)
                path_item.setData(Qt.UserRole, resolved)
                path_item.setToolTip(resolved)

                for col, item in enumerate([name_item, before_item, after_item, ratio_item, result_item, path_item]):
                    self.setItem(row, col, item)

                existing.add(resolved)
                added += 1
        finally:
            self.setSortingEnabled(True)

        return added

    def remove_selected_rows(self) -> None:
        """Remove all currently selected rows.
        現在選択中の行をすべて削除する。"""
        for row in sorted({idx.row() for idx in self.selectedIndexes()}, reverse=True):
            self.removeRow(row)

    def paths_in_display_order(self) -> list[Path]:
        """Return all input paths in the current display order (respects sorting).
        現在の表示順（ソート結果を反映）でパスのリストを返す。"""
        return [
            Path(item.data(Qt.UserRole))
            for row in range(self.rowCount())
            if (item := self.item(row, COL_PATH)) is not None
        ]

    def find_row_by_path(self, path: Path) -> int:
        """Return the row index for the given path, or -1 if not found.
        指定パスの行インデックスを返す。見つからなければ -1 を返す。"""
        target = str(path.resolve())
        for row in range(self.rowCount()):
            if (item := self.item(row, COL_PATH)) and item.data(Qt.UserRole) == target:
                return row
        return -1

    def update_encode_success(self, input_path: Path, output_path: Path) -> None:
        """
        Update the row for a successfully encoded file with size, ratio, and result.
        エンコード成功時: サイズ・変化率・結果列を更新する。
        """
        row = self.find_row_by_path(input_path)
        if row < 0:
            return

        before_item = self.item(row, COL_BEFORE)
        after_item  = self.item(row, COL_AFTER)
        ratio_item  = self.item(row, COL_RATIO)
        result_item = self.item(row, COL_RESULT)
        if None in (before_item, after_item, ratio_item, result_item):
            return

        before_size = before_item.data(Qt.UserRole)
        try:
            after_size = output_path.stat().st_size
        except OSError:
            after_size = None

        after_item.setText(format_bytes(after_size))
        after_item.setData(Qt.UserRole, after_size if after_size is not None else -1)

        if isinstance(before_size, int) and before_size > 0 and after_size is not None:
            ratio = ((after_size - before_size) / before_size) * 100.0
            ratio_item.setText(f"{ratio:+.2f}%")
            ratio_item.setData(Qt.UserRole, ratio)
            # Color red if size increased, green if decreased
            # サイズ増加なら赤、削減なら緑
            ratio_item.setForeground(COLOR_RATIO_INCREASE if ratio > 0 else COLOR_RATIO_DECREASE)
        else:
            ratio_item.setText("-")
            ratio_item.setData(Qt.UserRole, 0.0)
            ratio_item.setForeground(QBrush())  # Reset to theme default / テーマデフォルト色にリセット

        result_item.setText("完了")
        result_item.setForeground(_COLOR_OK)

    def set_result_error(self, input_path: Path, error: str) -> None:
        """
        Update the result cell of a failed row with an error message.
        エンコード失敗時: 結果列にエラー内容を表示する。
        """
        row = self.find_row_by_path(input_path)
        if row < 0:
            return
        if result_item := self.item(row, COL_RESULT):
            result_item.setText(error)
            result_item.setToolTip(error)
            result_item.setForeground(_COLOR_NG)

    def aggregate_sizes(self) -> tuple[int, int]:
        """
        Return (total_before, total_after) byte sizes across all rows.
        For rows where after-size is unknown (failed/not yet encoded),
        the before-size is used as a fallback.

        全行の (処理前合計サイズ, 処理後合計サイズ) をバイト単位で返す。
        処理後サイズが未確定（失敗・未実行）の行は処理前サイズを代わりに使う。
        """
        total_before = 0
        total_after = 0

        for row in range(self.rowCount()):
            before_item = self.item(row, COL_BEFORE)
            after_item  = self.item(row, COL_AFTER)
            if before_item is None:
                continue

            before_size = before_item.data(Qt.UserRole)
            if not isinstance(before_size, int) or before_size < 0:
                continue

            total_before += before_size
            raw_after = after_item.data(Qt.UserRole) if after_item else -1
            # Use before_size as fallback when after_size is unavailable
            # 処理後サイズが不明な場合は処理前サイズで代替
            after_size = raw_after if isinstance(raw_after, int) and raw_after >= 0 else before_size
            total_after += after_size

        return total_before, total_after

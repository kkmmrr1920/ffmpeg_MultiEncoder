from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from constants import (
    COL_NAME, COL_BEFORE, COL_AFTER, COL_RATIO, COL_PATH,
    HEADER_LABELS, HEADER_TOOLTIPS,
    COLOR_RATIO_INCREASE, COLOR_RATIO_DECREASE,
)
from utils import accept_url_drag, extract_video_paths, format_bytes


class SortableItem(QTableWidgetItem):
    """UserRoleの数値を優先して比較するテーブル項目。"""

    def __lt__(self, other) -> bool:
        left = self.data(Qt.UserRole)
        right = other.data(Qt.UserRole)
        if left is not None and right is not None:
            return left < right
        return self.text() < other.text()


class InputTableWidget(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 5)
        self.setHorizontalHeaderLabels(list(HEADER_LABELS))
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setToolTip("動画をドラッグ＆ドロップ、または追加ボタンで登録します。")
        self.setSortingEnabled(True)

        header = self.horizontalHeader()
        resize_modes = [
            QHeaderView.ResizeToContents,
            QHeaderView.ResizeToContents,
            QHeaderView.ResizeToContents,
            QHeaderView.ResizeToContents,
            QHeaderView.Stretch,
        ]
        for col, mode in enumerate(resize_modes):
            header.setSectionResizeMode(col, mode)

        for col, tooltip in enumerate(HEADER_TOOLTIPS):
            if item := self.horizontalHeaderItem(col):
                item.setToolTip(tooltip)

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

    def _existing_paths(self) -> set[str]:
        return {
            item.data(Qt.UserRole)
            for row in range(self.rowCount())
            if (item := self.item(row, COL_PATH)) is not None
        }

    def add_paths(self, paths: list[Path]) -> int:
        existing = self._existing_paths()
        added = 0

        self.setSortingEnabled(False)
        try:
            for path in paths:
                resolved = str(path.resolve())
                if resolved in existing:
                    continue

                try:
                    before_size = path.stat().st_size
                except OSError:
                    before_size = None

                row = self.rowCount()
                self.insertRow(row)

                name_item = SortableItem(path.name)
                name_item.setToolTip(resolved)

                before_item = SortableItem(format_bytes(before_size))
                before_item.setData(Qt.UserRole, before_size if before_size is not None else -1)
                before_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                after_item = SortableItem("-")
                after_item.setData(Qt.UserRole, -1)
                after_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                ratio_item = SortableItem("-")
                ratio_item.setData(Qt.UserRole, 0.0)
                ratio_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                path_item = SortableItem(resolved)
                path_item.setData(Qt.UserRole, resolved)
                path_item.setToolTip(resolved)

                for col, item in enumerate([name_item, before_item, after_item, ratio_item, path_item]):
                    self.setItem(row, col, item)

                existing.add(resolved)
                added += 1
        finally:
            self.setSortingEnabled(True)

        return added

    def remove_selected_rows(self) -> None:
        for row in sorted({idx.row() for idx in self.selectedIndexes()}, reverse=True):
            self.removeRow(row)

    def paths_in_display_order(self) -> list[Path]:
        return [
            Path(item.data(Qt.UserRole))
            for row in range(self.rowCount())
            if (item := self.item(row, COL_PATH)) is not None
        ]

    def find_row_by_path(self, path: Path) -> int:
        target = str(path.resolve())
        for row in range(self.rowCount()):
            if (item := self.item(row, COL_PATH)) and item.data(Qt.UserRole) == target:
                return row
        return -1

    def update_result(self, input_path: Path, output_path: Path) -> None:
        row = self.find_row_by_path(input_path)
        if row < 0:
            return

        before_item = self.item(row, COL_BEFORE)
        after_item = self.item(row, COL_AFTER)
        ratio_item = self.item(row, COL_RATIO)
        if None in (before_item, after_item, ratio_item):
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
            # ライト・ダーク両テーマで視認可能な色を使用
            ratio_item.setForeground(COLOR_RATIO_INCREASE if ratio > 0 else COLOR_RATIO_DECREASE)
        else:
            ratio_item.setText("-")
            ratio_item.setData(Qt.UserRole, 0.0)
            ratio_item.setForeground(QBrush())  # テーマに従うデフォルト色にリセット

    def aggregate_sizes(self) -> tuple[int, int]:
        """
        一覧全体の処理前/処理後合計サイズを返す。
        処理後サイズが未確定（失敗/未実行）の行は、処理前サイズを処理後として扱う。
        """
        total_before = 0
        total_after = 0

        for row in range(self.rowCount()):
            before_item = self.item(row, COL_BEFORE)
            after_item = self.item(row, COL_AFTER)
            if before_item is None:
                continue

            before_size = before_item.data(Qt.UserRole)
            if not isinstance(before_size, int) or before_size < 0:
                continue

            total_before += before_size
            raw_after = after_item.data(Qt.UserRole) if after_item else -1
            after_size = raw_after if isinstance(raw_after, int) and raw_after >= 0 else before_size
            total_after += after_size

        return total_before, total_after

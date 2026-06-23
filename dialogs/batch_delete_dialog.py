"""批量删除勾选对话框。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class BatchDeleteDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        records: list[dict[str, Any]],
        preselected_ids: set[int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("批量移入回收站")
        self.resize(680, 520)
        selected = preselected_ids or set()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("勾选要移入回收站的档案。借出中的档案不能删除。"))
        self.list_widget = QListWidget()
        for record in records:
            label = (
                f"{record.get('project_name', '')} | {record.get('box_no', '')} | "
                f"{record.get('file_name', '')} | {record.get('status_display', '')}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(record["file_id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if int(record["file_id"]) in selected
                else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        select_all = QPushButton("全选当前列表")
        select_all.clicked.connect(self._select_all)
        layout.addWidget(select_all)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_all(self) -> None:
        for index in range(self.list_widget.count()):
            self.list_widget.item(index).setCheckState(Qt.CheckState.Checked)

    def selected_ids(self) -> list[int]:
        return [
            int(self.list_widget.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.list_widget.count())
            if self.list_widget.item(index).checkState() == Qt.CheckState.Checked
        ]

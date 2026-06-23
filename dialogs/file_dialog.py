"""档案新增/编辑对话框。"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class FileDialog(QDialog):
    def __init__(self, parent=None, *, values: Mapping[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑档案" if values else "新增档案")
        self.resize(620, 380)
        self.box_no = QLineEdit()
        self.name = QLineEdit()
        self.file_type = QComboBox()
        self.file_type.setEditable(True)
        self.file_type.addItems(["纸质+电子", "纸质", "电子件", "其他"])
        self.count_text = QLineEdit()
        self.original_count = QSpinBox()
        self.original_count.setRange(0, 999999)
        self.original_count.setValue(1)
        self.copy_count = QSpinBox()
        self.copy_count.setRange(0, 999999)
        self.file_path = QLineEdit()
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.file_path)
        path_layout.addWidget(browse)

        if values:
            self.box_no.setText(str(values.get("box_no") or ""))
            self.name.setText(str(values.get("file_name") or values.get("name") or ""))
            self.file_type.setCurrentText(
                str(values.get("file_type") or values.get("type") or "")
            )
            self.count_text.setText(str(values.get("count_text") or ""))
            self.original_count.setValue(int(values.get("original_count") or 0))
            self.copy_count.setValue(int(values.get("copy_count") or 0))
            self.file_path.setText(str(values.get("file_path") or ""))

        form = QFormLayout()
        form.addRow("盒号", self.box_no)
        form.addRow("文件名称 *", self.name)
        form.addRow("载体类型", self.file_type)
        form.addRow("份数描述", self.count_text)
        form.addRow("原件库存", self.original_count)
        form.addRow("复印件库存", self.copy_count)
        form.addRow("电子文件", path_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择电子文件")
        if path:
            self.file_path.setText(path)

    def _validate_and_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "输入有误", "文件名称不能为空。")
            self.name.setFocus()
            return
        if self.original_count.value() + self.copy_count.value() <= 0:
            QMessageBox.warning(self, "输入有误", "原件和复印件库存不能同时为 0。")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "box_no": self.box_no.text().strip(),
            "name": self.name.text().strip(),
            "type": self.file_type.currentText().strip(),
            "count_text": self.count_text.text().strip(),
            "original_count": self.original_count.value(),
            "copy_count": self.copy_count.value(),
            "file_path": self.file_path.text().strip(),
        }

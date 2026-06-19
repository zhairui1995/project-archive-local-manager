"""项目新增/编辑对话框。"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)


PROJECT_LABELS = {
    "name": "项目名称 *",
    "construction_company": "建设单位",
    "contract_amount": "合同金额",
    "supervision_company": "监理单位",
    "supervision_amount": "监理金额",
    "start_date": "开工日期",
    "contact_person": "联系人",
    "contact_phone": "联系电话",
    "remarks": "备注",
}


class ProjectDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        values: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑项目" if values else "新增项目")
        self.resize(520, 520)
        self.editors: dict[str, QLineEdit | QPlainTextEdit] = {}

        form = QFormLayout()
        for field, label in PROJECT_LABELS.items():
            editor: QLineEdit | QPlainTextEdit
            if field == "remarks":
                editor = QPlainTextEdit()
                editor.setMaximumHeight(110)
            else:
                editor = QLineEdit()
            if values and values.get(field) is not None:
                if isinstance(editor, QPlainTextEdit):
                    editor.setPlainText(str(values[field]))
                else:
                    editor.setText(str(values[field]))
            self.editors[field] = editor
            form.addRow(label, editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.values()["name"]:
            QMessageBox.warning(self, "输入有误", "项目名称不能为空。")
            self.editors["name"].setFocus()
            return
        self.accept()

    def values(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for field, editor in self.editors.items():
            if isinstance(editor, QPlainTextEdit):
                result[field] = editor.toPlainText().strip()
            else:
                result[field] = editor.text().strip()
        return result

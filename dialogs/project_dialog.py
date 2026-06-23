"""项目新增/编辑对话框。"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import (
    QComboBox,
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
    "short_name": "子项目简称",
    "construction_company": "施工单位",
    "contract_amount": "合同金额",
    "design_company": "设计单位",
    "design_amount": "设计金额",
    "supervision_company": "监理单位",
    "supervision_amount": "监理金额",
    "start_date": "开工日期",
    "completion_date": "完工日期",
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
        parent_projects: list[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑项目" if values else "新增项目")
        self.resize(560, 650)
        self.editors: dict[str, QLineEdit | QPlainTextEdit] = {}

        form = QFormLayout()
        self.parent_project = QComboBox()
        self.parent_project.addItem("无（作为大项目）", None)
        current_id = values.get("id") if values else None
        for project in parent_projects or []:
            if project.get("id") == current_id or project.get("parent_project_id"):
                continue
            self.parent_project.addItem(str(project["name"]), int(project["id"]))
        if values and values.get("parent_project_id"):
            index = self.parent_project.findData(int(values["parent_project_id"]))
            if index >= 0:
                self.parent_project.setCurrentIndex(index)
        form.addRow("上级项目", self.parent_project)

        for field, label in PROJECT_LABELS.items():
            editor: QLineEdit | QPlainTextEdit
            if field == "remarks":
                editor = QPlainTextEdit()
                editor.setMaximumHeight(100)
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

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "parent_project_id": self.parent_project.currentData()
        }
        for field, editor in self.editors.items():
            result[field] = (
                editor.toPlainText().strip()
                if isinstance(editor, QPlainTextEdit)
                else editor.text().strip()
            )
        return result

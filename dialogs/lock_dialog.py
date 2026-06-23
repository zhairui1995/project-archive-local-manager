"""本机应用锁对话框。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class PasswordDialog(QDialog):
    def __init__(self, parent=None, *, title: str, confirm: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow("密码", self.password_edit)
        if confirm:
            form.addRow("确认密码", self.confirm_edit)
        self.confirm_required = confirm
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if self.confirm_required and self.password_edit.text() != self.confirm_edit.text():
            QMessageBox.warning(self, "输入有误", "两次输入的密码不一致。")
            return
        self.accept()

    def password(self) -> str:
        return self.password_edit.text()

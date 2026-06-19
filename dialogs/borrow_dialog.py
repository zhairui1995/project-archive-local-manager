"""借阅与归还对话框。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)


class BorrowDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("档案借阅")
        self.resize(440, 320)

        self.borrower = QLineEdit()
        self.contact = QLineEdit()
        self.reason = QPlainTextEdit()
        self.reason.setMaximumHeight(100)
        self.borrow_date = QDateEdit(QDate.currentDate())
        self.borrow_date.setCalendarPopup(True)
        self.borrow_date.setDisplayFormat("yyyy-MM-dd")

        form = QFormLayout()
        form.addRow("借用人 *", self.borrower)
        form.addRow("联系电话", self.contact)
        form.addRow("事由", self.reason)
        form.addRow("借出日期", self.borrow_date)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.borrower.text().strip():
            QMessageBox.warning(self, "输入有误", "借用人不能为空。")
            self.borrower.setFocus()
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {
            "borrower": self.borrower.text().strip(),
            "contact": self.contact.text().strip(),
            "reason": self.reason.toPlainText().strip(),
            "borrow_date": self.borrow_date.date().toString("yyyy-MM-dd"),
        }


class ReturnDialog(QDialog):
    def __init__(self, parent=None, *, borrow_date: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("归还档案")
        self.return_date = QDateEdit(QDate.currentDate())
        self.return_date.setCalendarPopup(True)
        self.return_date.setDisplayFormat("yyyy-MM-dd")
        self.borrow_date = borrow_date

        form = QFormLayout()
        form.addRow("归还日期", self.return_date)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        selected = self.return_date.date().toString("yyyy-MM-dd")
        if self.borrow_date and date.fromisoformat(selected) < date.fromisoformat(
            self.borrow_date
        ):
            QMessageBox.warning(self, "输入有误", "归还日期不能早于借出日期。")
            return
        self.accept()

    def value(self) -> str:
        return self.return_date.date().toString("yyyy-MM-dd")

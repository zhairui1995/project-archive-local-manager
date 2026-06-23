"""借阅、归还与历史记录对话框。"""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class BorrowDialog(QDialog):
    def __init__(self, parent=None, *, available_original: int = 0, available_copy: int = 0) -> None:
        super().__init__(parent)
        self.setWindowTitle("档案借阅")
        self.resize(460, 410)
        self.available = {"原件": available_original, "复印件": available_copy}
        self.borrower = QLineEdit()
        self.contact = QLineEdit()
        self.reason = QPlainTextEdit()
        self.reason.setMaximumHeight(90)
        self.media_type = QComboBox()
        for label, count in self.available.items():
            self.media_type.addItem(f"{label}（可借 {count} 份）", label)
        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.media_type.currentIndexChanged.connect(self._update_quantity_limit)
        self.borrow_date = QDateEdit(QDate.currentDate())
        self.borrow_date.setCalendarPopup(True)
        self.borrow_date.setDisplayFormat("yyyy-MM-dd")
        self.expected_return_date = QDateEdit(QDate.currentDate().addDays(30))
        self.expected_return_date.setCalendarPopup(True)
        self.expected_return_date.setDisplayFormat("yyyy-MM-dd")
        self._update_quantity_limit()

        form = QFormLayout()
        form.addRow("借用人 *", self.borrower)
        form.addRow("联系电话", self.contact)
        form.addRow("事由", self.reason)
        form.addRow("借阅类型", self.media_type)
        form.addRow("借阅份数", self.quantity)
        form.addRow("借出日期", self.borrow_date)
        form.addRow("预计归还日期", self.expected_return_date)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _update_quantity_limit(self) -> None:
        available = self.available.get(str(self.media_type.currentData()), 0)
        self.quantity.setMaximum(max(available, 1))

    def _validate_and_accept(self) -> None:
        if not self.borrower.text().strip():
            QMessageBox.warning(self, "输入有误", "借用人不能为空。")
            return
        media_type = str(self.media_type.currentData())
        if self.available.get(media_type, 0) <= 0:
            QMessageBox.warning(self, "库存不足", f"当前没有可借的{media_type}。")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "borrower": self.borrower.text().strip(),
            "contact": self.contact.text().strip(),
            "reason": self.reason.toPlainText().strip(),
            "media_type": str(self.media_type.currentData()),
            "quantity": self.quantity.value(),
            "borrow_date": self.borrow_date.date().toString("yyyy-MM-dd"),
            "expected_return_date": self.expected_return_date.date().toString("yyyy-MM-dd"),
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
        if self.borrow_date and date.fromisoformat(selected) < date.fromisoformat(self.borrow_date):
            QMessageBox.warning(self, "输入有误", "归还日期不能早于借出日期。")
            return
        self.accept()

    def value(self) -> str:
        return self.return_date.date().toString("yyyy-MM-dd")


class BorrowHistoryDialog(QDialog):
    def __init__(self, parent=None, *, records: list[dict[str, Any]]) -> None:
        super().__init__(parent)
        self.setWindowTitle("借阅详情与历史")
        self.resize(1000, 480)
        self.selected_record_id: int | None = None
        self.table = QTableWidget(len(records), 9)
        self.table.setHorizontalHeaderLabels(
            ["状态", "借用人", "联系电话", "事由", "类型", "份数", "借出日期", "预计归还", "实际归还"]
        )
        for row, record in enumerate(records):
            values = [
                "借出中" if not record.get("return_date") else "已归还",
                record.get("borrower"),
                record.get("contact"),
                record.get("reason"),
                record.get("media_type"),
                record.get("quantity"),
                record.get("borrow_date"),
                record.get("expected_return_date"),
                record.get("return_date"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(256, int(record["id"]))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        return_button = QPushButton("归还选中记录")
        return_button.clicked.connect(self._select_return)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(return_button)
        layout.addWidget(close)

    def _select_return(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条借阅记录。")
            return
        if self.table.item(row, 0).text() != "借出中":
            QMessageBox.information(self, "提示", "该记录已经归还。")
            return
        self.selected_record_id = int(self.table.item(row, 0).data(256))
        self.accept()

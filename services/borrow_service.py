"""整条档案借阅与归还业务服务。"""

from __future__ import annotations

from datetime import date
from typing import Any

from database import Database


class BorrowService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _date_text(value: date | str | None, *, default_today: bool = False) -> str:
        if value is None:
            if default_today:
                return date.today().isoformat()
            raise ValueError("日期不能为空。")
        if isinstance(value, date):
            return value.isoformat()
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("日期格式必须为 YYYY-MM-DD。") from exc

    def borrow_file(
        self,
        file_id: int,
        borrower: str,
        *,
        contact: str | None = None,
        reason: str | None = None,
        borrow_date: date | str | None = None,
        media_type: str = "原件",
        quantity: int = 1,
        expected_return_date: date | str | None = None,
    ) -> int:
        borrower = borrower.strip()
        if not borrower:
            raise ValueError("借用人不能为空。")
        record = self.database.get_file_with_status(file_id)
        if record is None or record.get("deleted_at"):
            raise LookupError("档案不存在或已被删除。")
        if media_type not in {"原件", "复印件"}:
            raise ValueError("借阅类型只能是原件或复印件。")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError) as exc:
            raise ValueError("借阅份数必须是整数。") from exc
        if quantity <= 0:
            raise ValueError("借阅份数必须大于 0。")
        available_field = (
            "available_original" if media_type == "原件" else "available_copy"
        )
        if quantity > int(record[available_field]):
            raise ValueError(
                f"{media_type}当前仅剩 {record[available_field]} 份可借。"
            )
        borrow_text = self._date_text(borrow_date, default_today=True)
        expected_text = (
            self._date_text(expected_return_date)
            if expected_return_date not in (None, "")
            else None
        )
        if expected_text and expected_text < borrow_text:
            raise ValueError("预计归还日期不能早于借出日期。")
        return self.database.execute(
            """
            INSERT INTO BorrowRecords(
                file_id, borrower, contact, reason, borrow_date,
                media_type, quantity, expected_return_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                borrower,
                contact.strip() or None if contact else None,
                reason.strip() or None if reason else None,
                borrow_text,
                media_type,
                quantity,
                expected_text,
            ),
        )

    def return_record(
        self,
        borrow_record_id: int,
        *,
        return_date: date | str | None = None,
    ) -> None:
        return_text = self._date_text(return_date, default_today=True)
        with self.database.connection() as conn:
            active = conn.execute(
                """
                SELECT id, borrow_date
                FROM BorrowRecords
                WHERE id = ? AND return_date IS NULL
                """,
                (borrow_record_id,),
            ).fetchone()
            if active is None:
                raise ValueError("该档案当前未借出，无需归还。")
            if return_text < active["borrow_date"]:
                raise ValueError("归还日期不能早于借出日期。")
            conn.execute(
                "UPDATE BorrowRecords SET return_date = ? WHERE id = ?",
                (return_text, active["id"]),
            )

    def return_file(
        self, file_id: int, *, return_date: date | str | None = None
    ) -> None:
        active = self.active_records(file_id)
        if len(active) != 1:
            raise ValueError("该档案存在多条借阅，请在借阅详情中选择具体记录归还。")
        self.return_record(active[0]["id"], return_date=return_date)

    def active_record(self, file_id: int) -> dict[str, Any] | None:
        rows = self.active_records(file_id)
        return rows[0] if len(rows) == 1 else None

    def active_records(self, file_id: int) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT *
            FROM BorrowRecords
            WHERE file_id = ? AND return_date IS NULL
            ORDER BY borrow_date, id
            """,
            (file_id,),
        )

    def history(self, file_id: int) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT *
            FROM BorrowRecords
            WHERE file_id = ?
            ORDER BY borrow_date DESC, id DESC
            """,
            (file_id,),
        )

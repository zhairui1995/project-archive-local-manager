"""整条档案借阅与归还业务服务。"""

from __future__ import annotations

import sqlite3
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
    ) -> int:
        borrower = borrower.strip()
        if not borrower:
            raise ValueError("借用人不能为空。")
        if self.database.fetch_one("SELECT id FROM Files WHERE id = ?", (file_id,)) is None:
            raise LookupError("档案不存在或已被删除。")

        try:
            return self.database.execute(
                """
                INSERT INTO BorrowRecords(file_id, borrower, contact, reason, borrow_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    borrower,
                    contact.strip() or None if contact else None,
                    reason.strip() or None if reason else None,
                    self._date_text(borrow_date, default_today=True),
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "BorrowRecords.file_id" in str(exc):
                raise ValueError("该档案当前已借出，不能重复借阅。") from exc
            raise

    def return_file(
        self,
        file_id: int,
        *,
        return_date: date | str | None = None,
    ) -> None:
        return_text = self._date_text(return_date, default_today=True)
        with self.database.connection() as conn:
            active = conn.execute(
                """
                SELECT id, borrow_date
                FROM BorrowRecords
                WHERE file_id = ? AND return_date IS NULL
                """,
                (file_id,),
            ).fetchone()
            if active is None:
                raise ValueError("该档案当前未借出，无需归还。")
            if return_text < active["borrow_date"]:
                raise ValueError("归还日期不能早于借出日期。")
            conn.execute(
                "UPDATE BorrowRecords SET return_date = ? WHERE id = ?",
                (return_text, active["id"]),
            )

    def active_record(self, file_id: int) -> dict[str, Any] | None:
        return self.database.fetch_one(
            """
            SELECT *
            FROM BorrowRecords
            WHERE file_id = ? AND return_date IS NULL
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

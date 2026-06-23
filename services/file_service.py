"""项目与档案台账业务服务。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from database import Database


PROJECT_FIELDS = (
    "name",
    "construction_company",
    "contract_amount",
    "supervision_company",
    "supervision_amount",
    "start_date",
    "contact_person",
    "contact_phone",
    "remarks",
    "parent_project_id",
    "short_name",
    "design_company",
    "design_amount",
    "completion_date",
)

FILE_FIELDS = (
    "project_id",
    "box_no",
    "name",
    "type",
    "count_text",
    "file_path",
    "original_count",
    "copy_count",
)


class FileService:
    """维护项目和档案，并负责本地电子文件路径操作。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def normalize_file_path(file_path: str | Path | None) -> str | None:
        if file_path is None or not str(file_path).strip():
            return None
        path = Path(file_path).expanduser()
        try:
            return str(path.resolve(strict=False))
        except OSError:
            return os.path.abspath(os.path.normpath(str(path)))

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _clean_nonnegative_int(value: Any, label: str) -> int:
        if value in (None, ""):
            return 0
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}必须是整数。") from exc
        if number < 0:
            raise ValueError(f"{label}不能小于 0。")
        return number

    def create_project(self, values: Mapping[str, Any]) -> int:
        name = self._clean_text(values.get("name"))
        if not name:
            raise ValueError("项目名称不能为空。")
        cleaned = {field: self._clean_text(values.get(field)) for field in PROJECT_FIELDS}
        parent_id = values.get("parent_project_id")
        cleaned["parent_project_id"] = int(parent_id) if parent_id not in (None, "") else None
        cleaned["name"] = name
        if cleaned["parent_project_id"] is not None:
            parent = self.get_project(int(cleaned["parent_project_id"]))
            if parent is None or parent.get("parent_project_id") is not None:
                raise ValueError("上级项目必须是有效的大项目。")
        placeholders = ", ".join("?" for _ in PROJECT_FIELDS)
        return self.database.execute(
            f"INSERT INTO Projects ({', '.join(PROJECT_FIELDS)}) VALUES ({placeholders})",
            tuple(cleaned[field] for field in PROJECT_FIELDS),
        )

    def update_project(self, project_id: int, values: Mapping[str, Any]) -> None:
        name = self._clean_text(values.get("name"))
        if not name:
            raise ValueError("项目名称不能为空。")
        cleaned = {field: self._clean_text(values.get(field)) for field in PROJECT_FIELDS}
        parent_id = values.get("parent_project_id")
        cleaned["parent_project_id"] = int(parent_id) if parent_id not in (None, "") else None
        cleaned["name"] = name
        if cleaned["parent_project_id"] == project_id:
            raise ValueError("项目不能把自己设为上级项目。")
        if cleaned["parent_project_id"] is not None:
            parent = self.get_project(int(cleaned["parent_project_id"]))
            if parent is None or parent.get("parent_project_id") is not None:
                raise ValueError("上级项目必须是有效的大项目。")
        assignments = ", ".join(f"{field} = ?" for field in PROJECT_FIELDS)
        affected = self.database.execute_affected(
            f"UPDATE Projects SET {assignments} WHERE id = ?",
            (*[cleaned[field] for field in PROJECT_FIELDS], project_id),
        )
        if affected != 1:
            raise LookupError("项目不存在或已被删除。")

    def delete_project(self, project_id: int) -> None:
        with self.database.connection() as conn:
            exists = conn.execute(
                "SELECT id FROM Projects WHERE id = ?", (project_id,)
            ).fetchone()
            if exists is None:
                raise LookupError("项目不存在或已被删除。")
            conn.execute(
                "DELETE FROM Projects WHERE parent_project_id = ?", (project_id,)
            )
            conn.execute("DELETE FROM Projects WHERE id = ?", (project_id,))

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        return self.database.fetch_one("SELECT * FROM Projects WHERE id = ?", (project_id,))

    def list_projects(self) -> list[dict[str, Any]]:
        return self.database.list_projects()

    def create_file(self, values: Mapping[str, Any]) -> int:
        project_id = values.get("project_id")
        if not isinstance(project_id, int) or project_id <= 0:
            raise ValueError("必须选择有效项目。")
        name = self._clean_text(values.get("name"))
        if not name:
            raise ValueError("文件名称不能为空。")
        cleaned = {
            "project_id": project_id,
            "box_no": self._clean_text(values.get("box_no")),
            "name": name,
            "type": self._clean_text(values.get("type")),
            "count_text": self._clean_text(values.get("count_text")),
            "file_path": self.normalize_file_path(values.get("file_path")),
            "original_count": self._clean_nonnegative_int(
                values.get("original_count", 1), "原件库存"
            ),
            "copy_count": self._clean_nonnegative_int(
                values.get("copy_count", 0), "复印件库存"
            ),
        }
        if cleaned["original_count"] + cleaned["copy_count"] <= 0:
            raise ValueError("原件和复印件库存不能同时为 0。")
        return self.database.execute(
            """
            INSERT INTO Files(
                project_id, box_no, name, type, count_text, file_path,
                original_count, copy_count
            )
            VALUES (
                :project_id, :box_no, :name, :type, :count_text, :file_path,
                :original_count, :copy_count
            )
            """,
            cleaned,
        )

    def update_file(self, file_id: int, values: Mapping[str, Any]) -> None:
        name = self._clean_text(values.get("name"))
        if not name:
            raise ValueError("文件名称不能为空。")
        cleaned = {
            "box_no": self._clean_text(values.get("box_no")),
            "name": name,
            "type": self._clean_text(values.get("type")),
            "count_text": self._clean_text(values.get("count_text")),
            "file_path": self.normalize_file_path(values.get("file_path")),
            "original_count": self._clean_nonnegative_int(
                values.get("original_count", 1), "原件库存"
            ),
            "copy_count": self._clean_nonnegative_int(
                values.get("copy_count", 0), "复印件库存"
            ),
            "file_id": file_id,
        }
        if cleaned["original_count"] + cleaned["copy_count"] <= 0:
            raise ValueError("原件和复印件库存不能同时为 0。")
        current = self.get_file(file_id)
        if current is None:
            raise LookupError("档案不存在或已被删除。")
        if cleaned["original_count"] < int(current["borrowed_original"]):
            raise ValueError("原件库存不能小于当前已借出的原件数量。")
        if cleaned["copy_count"] < int(current["borrowed_copy"]):
            raise ValueError("复印件库存不能小于当前已借出的复印件数量。")
        affected = self.database.execute_affected(
            """
            UPDATE Files
            SET box_no = :box_no,
                name = :name,
                type = :type,
                count_text = :count_text,
                file_path = :file_path,
                original_count = :original_count,
                copy_count = :copy_count
            WHERE id = :file_id
            """,
            cleaned,
        )
        if affected != 1:
            raise LookupError("档案不存在或已被删除。")

    def delete_file(self, file_id: int) -> None:
        self.delete_files([file_id])

    def delete_files(self, file_ids: list[int]) -> int:
        normalized = sorted({int(file_id) for file_id in file_ids})
        if not normalized:
            return 0
        placeholders = ", ".join("?" for _ in normalized)
        active = self.database.fetch_one(
            f"""
            SELECT COUNT(*) AS count
            FROM BorrowRecords
            WHERE return_date IS NULL AND file_id IN ({placeholders})
            """,
            normalized,
        )
        if active and active["count"]:
            raise ValueError("所选档案中存在尚未归还的记录，不能移入回收站。")
        affected = self.database.execute_affected(
            f"""
            UPDATE Files
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE deleted_at IS NULL AND id IN ({placeholders})
            """,
            normalized,
        )
        if affected == 0:
            raise LookupError("档案不存在、已删除或未选中有效记录。")
        return affected

    def restore_files(self, file_ids: list[int]) -> int:
        normalized = sorted({int(file_id) for file_id in file_ids})
        if not normalized:
            return 0
        placeholders = ", ".join("?" for _ in normalized)
        return self.database.execute_affected(
            f"UPDATE Files SET deleted_at = NULL WHERE id IN ({placeholders})",
            normalized,
        )

    def permanently_delete_files(self, file_ids: list[int]) -> int:
        normalized = sorted({int(file_id) for file_id in file_ids})
        if not normalized:
            return 0
        placeholders = ", ".join("?" for _ in normalized)
        return self.database.execute_affected(
            f"DELETE FROM Files WHERE deleted_at IS NOT NULL AND id IN ({placeholders})",
            normalized,
        )

    def bind_file(self, file_id: int, file_path: str | Path) -> str:
        normalized = self.normalize_file_path(file_path)
        if normalized is None:
            raise ValueError("请选择要绑定的电子文件。")
        if not Path(normalized).is_file():
            raise FileNotFoundError("所选电子文件不存在。")
        affected = self.database.execute_affected(
            "UPDATE Files SET file_path = ? WHERE id = ?", (normalized, file_id)
        )
        if affected != 1:
            raise LookupError("档案不存在或已被删除。")
        return normalized

    def get_file(self, file_id: int) -> dict[str, Any] | None:
        return self.database.get_file_with_status(file_id)

    def list_files(
        self, project_id: int, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        return self.database.list_files_with_status(
            project_id, include_deleted=include_deleted
        )

    def search_files(self, keyword: str) -> list[dict[str, Any]]:
        return self.database.search_files_global(keyword)

    def require_bound_path(self, file_id: int) -> Path:
        record = self.get_file(file_id)
        if record is None:
            raise LookupError("档案不存在或已被删除。")
        raw_path = record.get("file_path")
        if not raw_path:
            raise FileNotFoundError("该档案尚未绑定电子文件。")
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError("绑定路径已失效，请重新绑定电子文件。")
        return path

    def open_bound_file(self, file_id: int) -> None:
        self._open_path(self.require_bound_path(file_id))

    def open_containing_folder(self, file_id: int) -> None:
        path = self.require_bound_path(file_id)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            self._open_path(path.parent)

    @staticmethod
    def _open_path(path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

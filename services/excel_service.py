"""项目档案台账 Excel 导入导出。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from database import Database
from services.file_service import FileService


EXPORT_COLUMNS = {
    "project_name": "项目名称",
    "box_no": "盒号",
    "file_name": "文件名称",
    "file_type": "载体类型",
    "count_text": "份数描述",
    "file_path": "电子文件路径",
    "computed_status": "当前状态",
    "borrower": "当前借用人",
    "borrow_date": "借出日期",
}

IMPORT_ALIASES = {
    "盒号": "box_no",
    "文件名称": "name",
    "载体类型": "type",
    "份数描述": "count_text",
    "电子文件路径": "file_path",
}


class ExcelService:
    def __init__(self, database: Database, file_service: FileService) -> None:
        self.database = database
        self.file_service = file_service

    def export_project(self, project_id: int, output_path: str | Path) -> Path:
        project = self.file_service.get_project(project_id)
        if project is None:
            raise LookupError("项目不存在或已被删除。")
        rows = self.file_service.list_files(project_id)
        frame = pd.DataFrame(rows)
        for field in EXPORT_COLUMNS:
            if field not in frame:
                frame[field] = None
        frame = frame[list(EXPORT_COLUMNS)].rename(columns=EXPORT_COLUMNS)

        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name="档案台账", index=False)
            worksheet = writer.book["档案台账"]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(
                    max(max_length + 2, 10), 50
                )
        return output

    def import_project(self, project_id: int, input_path: str | Path) -> dict[str, Any]:
        if self.file_service.get_project(project_id) is None:
            raise LookupError("项目不存在或已被删除。")
        input_file = Path(input_path).expanduser().resolve()
        if not input_file.is_file():
            raise FileNotFoundError("Excel 文件不存在。")

        frame = pd.read_excel(input_file, sheet_name=0, dtype=str).fillna("")
        missing = {"文件名称"} - set(frame.columns)
        if missing:
            raise ValueError("Excel 至少需要包含“文件名称”列。")

        imported = 0
        errors: list[str] = []
        for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
            values = {"project_id": project_id}
            for excel_name, field_name in IMPORT_ALIASES.items():
                values[field_name] = str(row.get(excel_name, "")).strip()
            if not any(values.get(field_name) for field_name in IMPORT_ALIASES.values()):
                continue
            try:
                self.file_service.create_file(values)
                imported += 1
            except Exception as exc:
                errors.append(f"第 {row_number} 行：{exc}")
        return {"imported": imported, "failed": len(errors), "errors": errors}

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from database import Database
from services.excel_service import ExcelService
from services.file_service import FileService


def test_excel_import_and_export(tmp_path: Path) -> None:
    database = Database(tmp_path / "excel.db")
    database.initialize()
    files = FileService(database)
    excel = ExcelService(database, files)
    project_id = files.create_project({"name": "Excel 项目"})

    input_path = tmp_path / "input.xlsx"
    pd.DataFrame(
        [
            {
                "盒号": "X-01",
                "文件名称": "导入合同",
                "载体类型": "原件",
                "份数描述": "2份",
                "电子文件路径": "",
            }
        ]
    ).to_excel(input_path, index=False)
    result = excel.import_project(project_id, input_path)
    assert result == {"imported": 1, "failed": 0, "errors": []}

    output_path = excel.export_project(project_id, tmp_path / "output.xlsx")
    exported = pd.read_excel(output_path)
    assert exported.loc[0, "项目名称"] == "Excel 项目"
    assert exported.loc[0, "当前状态"] == "在库"


def test_delivered_migration_template_is_importable(tmp_path: Path) -> None:
    database = Database(tmp_path / "template.db")
    database.initialize()
    files = FileService(database)
    excel = ExcelService(database, files)
    project_id = files.create_project({"name": "模板导入测试"})

    source = Path(__file__).resolve().parents[1] / "deliverables" / "档案迁移导入模板.xlsx"
    target = tmp_path / "filled-template.xlsx"
    workbook = load_workbook(source)
    sheet = workbook["档案导入"]
    sheet.append(["A-101", "模板合同", "原件", "2份", ""])
    workbook.save(target)

    result = excel.import_project(project_id, target)
    assert result == {"imported": 1, "failed": 0, "errors": []}
    assert files.list_files(project_id)[0]["file_name"] == "模板合同"

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from database import Database
from services.borrow_service import BorrowService
from services.directory_scan_service import DirectoryScanService
from services.file_service import FileService


@pytest.fixture()
def services(tmp_path: Path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    return database, FileService(database), BorrowService(database)


def test_schema_has_no_status_and_has_active_borrow_index(services) -> None:
    database, _, _ = services
    with database.connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(Files)")}
        indexes = {
            row["name"]: row
            for row in conn.execute("PRAGMA index_list(BorrowRecords)").fetchall()
        }
        assert "status" not in columns
        assert indexes["idx_borrow_one_active_record"]["unique"] == 1
        assert indexes["idx_borrow_one_active_record"]["partial"] == 1
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_dynamic_status_and_one_active_borrow(services) -> None:
    database, files, borrows = services
    project_id = files.create_project({"name": "测试项目"})
    file_id = files.create_file(
        {
            "project_id": project_id,
            "box_no": "A-01",
            "name": "施工合同",
            "type": "原件",
            "count_text": "3份",
        }
    )
    assert files.get_file(file_id)["computed_status"] == "在库"

    borrows.borrow_file(file_id, "张三", borrow_date="2026-06-19")
    borrowed = files.get_file(file_id)
    assert borrowed["computed_status"] == "已借出"
    assert borrowed["status_display"] == "🔴 已借出：张三"

    with pytest.raises(ValueError, match="不能重复借阅"):
        borrows.borrow_file(file_id, "李四", borrow_date="2026-06-19")

    borrows.return_file(file_id, return_date="2026-06-20")
    assert files.get_file(file_id)["computed_status"] == "在库"
    assert len(borrows.history(file_id)) == 1

    # 归还后允许开启新的完整借阅周期。
    borrows.borrow_file(file_id, "李四", borrow_date="2026-06-21")
    assert files.get_file(file_id)["borrower"] == "李四"


def test_return_date_cannot_precede_borrow_date(services) -> None:
    _, files, borrows = services
    project_id = files.create_project({"name": "日期测试"})
    file_id = files.create_file({"project_id": project_id, "name": "验收报告"})
    borrows.borrow_file(file_id, "王五", borrow_date="2026-06-19")
    with pytest.raises(ValueError, match="不能早于"):
        borrows.return_file(file_id, return_date="2026-06-18")


def test_project_delete_cascades_files_and_borrows(services) -> None:
    database, files, borrows = services
    project_id = files.create_project({"name": "级联测试"})
    file_id = files.create_file({"project_id": project_id, "name": "图纸"})
    borrow_id = borrows.borrow_file(file_id, "赵六", borrow_date="2026-06-19")
    files.delete_project(project_id)
    assert files.get_file(file_id) is None
    assert (
        database.fetch_one("SELECT id FROM BorrowRecords WHERE id = ?", (borrow_id,))
        is None
    )


def test_file_binding_is_absolute_and_detects_missing_file(
    services, tmp_path: Path
) -> None:
    _, files, _ = services
    project_id = files.create_project({"name": "路径测试"})
    source = tmp_path / "资料.pdf"
    source.write_bytes(b"pdf")
    file_id = files.create_file(
        {"project_id": project_id, "name": "资料", "file_path": source}
    )
    assert Path(files.require_bound_path(file_id)).is_absolute()
    source.unlink()
    with pytest.raises(FileNotFoundError, match="重新绑定"):
        files.require_bound_path(file_id)


def test_global_search_matches_project_box_file_and_active_borrower(services) -> None:
    _, files, borrows = services
    project_id = files.create_project({"name": "南区工程"})
    file_id = files.create_file(
        {"project_id": project_id, "box_no": "B-09", "name": "监理月报"}
    )
    borrows.borrow_file(file_id, "陈工", borrow_date="2026-06-19")
    for keyword in ("南区", "B-09", "月报", "陈工"):
        assert files.search_files(keyword)[0]["file_id"] == file_id


def test_directory_scan(tmp_path: Path) -> None:
    (tmp_path / "子目录").mkdir()
    (tmp_path / "子目录" / "合同.pdf").write_bytes(b"")
    (tmp_path / "忽略.txt").write_text("", encoding="utf-8")
    rows = DirectoryScanService.scan(tmp_path, extensions=["pdf"])
    assert [row["name"] for row in rows] == ["合同"]
    assert Path(rows[0]["file_path"]).is_absolute()


def test_database_check_constraint_rejects_invalid_dates(services) -> None:
    database, files, _ = services
    project_id = files.create_project({"name": "约束测试"})
    file_id = files.create_file({"project_id": project_id, "name": "文件"})
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            INSERT INTO BorrowRecords(
                file_id, borrower, borrow_date, return_date
            ) VALUES (?, ?, ?, ?)
            """,
            (file_id, "测试人", "2026-06-20", "2026-06-19"),
        )

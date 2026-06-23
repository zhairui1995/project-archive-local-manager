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


def test_schema_v2_has_inventory_and_allows_parallel_borrows(services) -> None:
    database, _, _ = services
    with database.connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(Files)")}
        indexes = {
            row["name"]: row
            for row in conn.execute("PRAGMA index_list(BorrowRecords)").fetchall()
        }
        assert "status" not in columns
        assert {"original_count", "copy_count", "deleted_at"} <= columns
        assert "idx_borrow_one_active_record" not in indexes
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_inventory_status_parallel_borrow_and_history(services) -> None:
    database, files, borrows = services
    project_id = files.create_project({"name": "测试项目"})
    file_id = files.create_file(
        {
            "project_id": project_id,
            "box_no": "A-01",
            "name": "施工合同",
            "type": "原件",
            "count_text": "3份",
            "original_count": 3,
            "copy_count": 2,
        }
    )
    assert files.get_file(file_id)["computed_status"] == "在库"

    borrows.borrow_file(
        file_id, "张三", borrow_date="2026-06-19", media_type="原件", quantity=2
    )
    borrowed = files.get_file(file_id)
    assert borrowed["computed_status"] == "部分借出"
    assert borrowed["available_original"] == 1

    borrows.borrow_file(
        file_id, "李四", borrow_date="2026-06-19", media_type="原件", quantity=1
    )
    borrows.borrow_file(
        file_id, "王五", borrow_date="2026-06-19", media_type="复印件", quantity=2
    )
    assert files.get_file(file_id)["computed_status"] == "全部借出"

    with pytest.raises(ValueError, match="仅剩 0"):
        borrows.borrow_file(
            file_id, "赵六", borrow_date="2026-06-19", media_type="原件", quantity=1
        )

    first = borrows.active_records(file_id)[0]
    borrows.return_record(first["id"], return_date="2026-06-20")
    assert files.get_file(file_id)["computed_status"] == "部分借出"
    assert len(borrows.history(file_id)) == 3


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


def test_project_hierarchy_and_group_delete(services) -> None:
    _, files, _ = services
    parent = files.create_project({"name": "产业园"})
    child = files.create_project(
        {"name": "产业园消防工程", "short_name": "消防工程", "parent_project_id": parent}
    )
    file_id = files.create_file({"project_id": child, "name": "消防验收资料"})
    projects = files.list_projects()
    assert projects[1]["parent_project_id"] == parent
    files.delete_project(parent)
    assert files.get_project(child) is None
    assert files.get_file(file_id) is None


def test_batch_delete_uses_recycle_bin_and_blocks_active_borrow(services) -> None:
    _, files, borrows = services
    project_id = files.create_project({"name": "批量测试"})
    first = files.create_file({"project_id": project_id, "name": "文件一"})
    second = files.create_file({"project_id": project_id, "name": "文件二"})
    assert files.delete_files([first, second]) == 2
    assert files.list_files(project_id) == []
    assert len(files.list_files(project_id, include_deleted=True)) == 2
    assert files.restore_files([first, second]) == 2
    borrows.borrow_file(first, "张三")
    with pytest.raises(ValueError, match="尚未归还"):
        files.delete_files([first, second])


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


def test_v01_database_migrates_with_backup(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE Projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                construction_company TEXT,
                contract_amount TEXT,
                supervision_company TEXT,
                supervision_amount TEXT,
                start_date TEXT,
                contact_person TEXT,
                contact_phone TEXT,
                remarks TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE Files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                box_no TEXT,
                name TEXT NOT NULL,
                type TEXT,
                count_text TEXT,
                file_path TEXT,
                FOREIGN KEY (project_id) REFERENCES Projects(id) ON DELETE CASCADE
            );
            CREATE TABLE BorrowRecords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                borrower TEXT NOT NULL,
                contact TEXT,
                reason TEXT,
                borrow_date DATE NOT NULL,
                return_date DATE,
                FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE
            );
            CREATE UNIQUE INDEX idx_borrow_one_active_record
            ON BorrowRecords(file_id) WHERE return_date IS NULL;
            INSERT INTO Projects(name, construction_company)
            VALUES ('旧项目', '原施工单位');
            INSERT INTO Files(project_id, name, count_text)
            VALUES (1, '旧档案', '3份');
            """
        )
    database = Database(path)
    database.initialize()
    files = FileService(database)
    assert files.get_project(1)["construction_company"] == "原施工单位"
    migrated = files.get_file(1)
    assert migrated["original_count"] == 1
    assert migrated["copy_count"] == 0
    assert list(tmp_path.glob("legacy-升级前-*.db"))

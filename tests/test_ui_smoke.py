from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from database import Database
from services.file_service import FileService
from ui_main import MainWindow


def test_main_window_smoke(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "ui.db")
    database.initialize()
    files = FileService(database)
    project_id = files.create_project({"name": "界面测试项目"})
    files.create_file({"project_id": project_id, "name": "界面测试文件"})

    window = MainWindow(database)
    assert window.project_tree.topLevelItemCount() == 1
    assert window.table.rowCount() == 1
    assert window.search_timer.interval() == 300
    window.close()
    app.processEvents()


def test_global_search_stays_visible_until_explicit_location(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "search-ui.db")
    database.initialize()
    files = FileService(database)
    first_project = files.create_project({"name": "第一项目"})
    files.create_file({"project_id": first_project, "name": "普通文件"})
    second_project = files.create_project({"name": "第二项目"})
    target_file = files.create_file(
        {"project_id": second_project, "box_no": "TARGET", "name": "目标文件"}
    )

    window = MainWindow(database)
    window.search_edit.setText("TARGET")
    window.search_timer.stop()
    window._apply_global_search()
    assert window.global_mode is True
    assert window.table.rowCount() == 1

    window.table.selectRow(0)
    assert window.search_edit.text() == "TARGET"
    assert window.global_mode is True
    window._locate_selected_project()
    assert window.current_project_id == second_project
    assert window.search_edit.text() == ""
    assert window.table.currentRow() >= 0
    selected = window.table.item(window.table.currentRow(), 0)
    assert selected.data(Qt.ItemDataRole.UserRole) == target_file
    window.close()
    app.processEvents()


def test_project_form_saves_all_fields(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "project-form.db")
    database.initialize()
    files = FileService(database)
    project_id = files.create_project({"name": "旧名称"})

    window = MainWindow(database)
    window.project_editors["name"].setText("新名称")
    window.project_editors["contact_person"].setText("周工")
    window.project_editors["remarks"].setPlainText("表单直接保存")
    window._save_project_form()

    project = files.get_project(project_id)
    assert project["name"] == "新名称"
    assert project["contact_person"] == "周工"
    assert project["remarks"] == "表单直接保存"
    window.close()
    app.processEvents()

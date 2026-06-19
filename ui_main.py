"""项目档案本地管理系统主界面。"""

from __future__ import annotations

from functools import partial
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app_paths import database_path
from database import Database
from dialogs import BorrowDialog, FileDialog, ProjectDialog, ReturnDialog
from services import BorrowService, ExcelService, FileService


APP_NAME = "项目档案本地管理系统"
PROJECT_FIELDS = (
    ("name", "项目名称"),
    ("construction_company", "建设单位"),
    ("contract_amount", "合同金额"),
    ("supervision_company", "监理单位"),
    ("supervision_amount", "监理金额"),
    ("start_date", "开工日期"),
    ("contact_person", "联系人"),
    ("contact_phone", "联系电话"),
    ("remarks", "备注"),
)


class MainWindow(QMainWindow):
    def __init__(self, database: Database | None = None) -> None:
        super().__init__()
        if database is None:
            database = Database(database_path())
            database.initialize()
        self.database = database
        self.file_service = FileService(database)
        self.borrow_service = BorrowService(database)
        self.excel_service = ExcelService(database, self.file_service)
        self.current_project_id: int | None = None
        self.global_mode = False
        self._pending_highlight_file_id: int | None = None

        self.setWindowTitle(APP_NAME)
        self.resize(1420, 850)
        self._build_ui()
        self._load_projects()

    def _build_ui(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        add_project_action = QAction("新增项目", self)
        add_project_action.triggered.connect(self._add_project)
        toolbar.addAction(add_project_action)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" 全局搜索："))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索项目名、盒号、文件名、当前借用人")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(420)
        toolbar.addWidget(self.search_edit)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self._apply_global_search)

        root_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(root_splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("项目列表"))
        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(220)
        self.project_list.currentItemChanged.connect(self._project_selected)
        left_layout.addWidget(self.project_list)
        left_buttons = QHBoxLayout()
        edit_project = QPushButton("编辑")
        delete_project = QPushButton("删除")
        edit_project.clicked.connect(self._edit_project)
        delete_project.clicked.connect(self._delete_project)
        left_buttons.addWidget(edit_project)
        left_buttons.addWidget(delete_project)
        left_layout.addLayout(left_buttons)
        root_splitter.addWidget(left)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        root_splitter.addWidget(right_splitter)
        root_splitter.setStretchFactor(1, 1)

        project_area = QScrollArea()
        project_area.setWidgetResizable(True)
        project_form_widget = QWidget()
        self.project_grid = QGridLayout(project_form_widget)
        self.project_editors: dict[str, QLineEdit | QPlainTextEdit] = {}
        for index, (field, label) in enumerate(PROJECT_FIELDS):
            row, pair = divmod(index, 2)
            label_widget = QLabel(f"{label}：")
            if field == "remarks":
                value_widget: QLineEdit | QPlainTextEdit = QPlainTextEdit()
                value_widget.setMaximumHeight(80)
            else:
                value_widget = QLineEdit()
            column = pair * 2
            self.project_grid.addWidget(label_widget, row, column)
            self.project_grid.addWidget(value_widget, row, column + 1)
            self.project_editors[field] = value_widget
        save_project = QPushButton("保存项目资料")
        save_project.clicked.connect(self._save_project_form)
        self.project_grid.addWidget(save_project, 5, 3)
        project_area.setWidget(project_form_widget)
        right_splitter.addWidget(project_area)

        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_buttons = QHBoxLayout()
        self.mode_label = QLabel("档案台账")
        add_file = QPushButton("新增档案")
        edit_file = QPushButton("编辑档案")
        delete_file = QPushButton("删除档案")
        import_excel = QPushButton("Excel 导入")
        export_excel = QPushButton("Excel 导出")
        add_file.clicked.connect(self._add_file)
        edit_file.clicked.connect(self._edit_file)
        delete_file.clicked.connect(self._delete_file)
        import_excel.clicked.connect(self._import_excel)
        export_excel.clicked.connect(self._export_excel)
        table_buttons.addWidget(self.mode_label)
        table_buttons.addStretch()
        for button in (add_file, edit_file, delete_file, import_excel, export_excel):
            table_buttons.addWidget(button)
        table_layout.addLayout(table_buttons)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self._global_result_activated)
        table_layout.addWidget(self.table)
        right_splitter.addWidget(table_panel)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([260, 580])

        self.statusBar().showMessage("就绪")

    def _load_projects(self, select_project_id: int | None = None) -> None:
        if select_project_id is None:
            select_project_id = self.current_project_id
        self.project_list.blockSignals(True)
        self.project_list.clear()
        selected_row = -1
        for row, project in enumerate(self.file_service.list_projects()):
            item = QListWidgetItem(project["name"])
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            self.project_list.addItem(item)
            if project["id"] == select_project_id:
                selected_row = row
        self.project_list.blockSignals(False)
        if self.project_list.count():
            self.project_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
            self._project_selected(self.project_list.currentItem(), None)
        else:
            self.current_project_id = None
            self._show_project(None)
            self._render_files([])

    def _project_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        self.current_project_id = int(current.data(Qt.ItemDataRole.UserRole))
        project = self.file_service.get_project(self.current_project_id)
        self._show_project(project)
        if not self.search_edit.text().strip():
            self.global_mode = False
            self.mode_label.setText("档案台账")
            self._render_files(self.file_service.list_files(self.current_project_id))
            if self._pending_highlight_file_id is not None:
                self._select_file_row(self._pending_highlight_file_id)
                self._pending_highlight_file_id = None

    def _show_project(self, project: dict[str, Any] | None) -> None:
        for field, editor in self.project_editors.items():
            value = str(project.get(field) or "") if project else ""
            editor.setEnabled(project is not None)
            if isinstance(editor, QPlainTextEdit):
                editor.setPlainText(value)
            else:
                editor.setText(value)

    def _save_project_form(self) -> None:
        if self.current_project_id is None:
            return
        values: dict[str, str] = {}
        for field, editor in self.project_editors.items():
            if isinstance(editor, QPlainTextEdit):
                values[field] = editor.toPlainText().strip()
            else:
                values[field] = editor.text().strip()
        try:
            self.file_service.update_project(self.current_project_id, values)
            self._load_projects(self.current_project_id)
            self.statusBar().showMessage("项目资料已保存", 3000)
        except Exception as exc:
            self._show_error(exc)

    def _render_files(self, rows: list[dict[str, Any]]) -> None:
        global_columns = [
            ("project_name", "项目名称"),
            ("box_no", "盒号"),
            ("file_name", "文件名称"),
            ("file_type", "载体类型"),
            ("count_text", "份数"),
            ("status_display", "状态"),
            ("actions", "操作"),
        ]
        local_columns = global_columns[1:]
        columns = global_columns if self.global_mode else local_columns
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])
        self.table.setRowCount(len(rows))

        for row_index, record in enumerate(rows):
            file_id = int(record["file_id"])
            for column_index, (field, _label) in enumerate(columns):
                if field == "actions":
                    self.table.setCellWidget(
                        row_index, column_index, self._action_widget(record)
                    )
                    continue
                item = QTableWidgetItem(str(record.get(field) or ""))
                item.setData(Qt.ItemDataRole.UserRole, file_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, record["project_id"])
                if field == "status_display":
                    if record["computed_status"] == "已借出":
                        item.setForeground(Qt.GlobalColor.red)
                    else:
                        item.setForeground(Qt.GlobalColor.darkGreen)
                self.table.setItem(row_index, column_index, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        name_column = next(
            index for index, (field, _) in enumerate(columns) if field == "file_name"
        )
        header.setSectionResizeMode(name_column, QHeaderView.ResizeMode.Stretch)
        self.table.resizeRowsToContents()

    def _action_widget(self, record: dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        file_id = int(record["file_id"])
        bind = QPushButton("重新绑定" if record.get("file_path") else "绑定")
        open_file = QPushButton("打开")
        open_folder = QPushButton("所在文件夹")
        borrow = QPushButton(
            "归还" if record["computed_status"] == "已借出" else "借阅"
        )
        bind.clicked.connect(partial(self._bind_file, file_id))
        open_file.clicked.connect(partial(self._open_file, file_id))
        open_folder.clicked.connect(partial(self._open_folder, file_id))
        if record["computed_status"] == "已借出":
            borrow.clicked.connect(partial(self._return_file, file_id))
        else:
            borrow.clicked.connect(partial(self._borrow_file, file_id))
        for button in (bind, open_file, open_folder, borrow):
            layout.addWidget(button)
        return widget

    def _selected_file_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        for column in range(self.table.columnCount()):
            item = self.table.item(row, column)
            if item is not None:
                value = item.data(Qt.ItemDataRole.UserRole)
                if value:
                    return int(value)
        return None

    def _select_file_row(self, file_id: int) -> None:
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item and item.data(Qt.ItemDataRole.UserRole) == file_id:
                    self.table.selectRow(row)
                    self.table.scrollToItem(item)
                    return

    def _refresh_files(self) -> None:
        keyword = self.search_edit.text().strip()
        if keyword:
            self.global_mode = True
            rows = self.file_service.search_files(keyword)
            self.mode_label.setText(f"全局搜索结果（{len(rows)}）")
        elif self.current_project_id is not None:
            self.global_mode = False
            rows = self.file_service.list_files(self.current_project_id)
            self.mode_label.setText("档案台账")
        else:
            rows = []
        self._render_files(rows)

    def _apply_global_search(self) -> None:
        self._refresh_files()

    def _global_result_activated(self, row: int, _column: int) -> None:
        if not self.global_mode:
            return
        item = next(
            (
                self.table.item(row, column)
                for column in range(self.table.columnCount())
                if self.table.item(row, column) is not None
            ),
            None,
        )
        if item is None:
            return
        file_id = int(item.data(Qt.ItemDataRole.UserRole))
        project_id = int(item.data(Qt.ItemDataRole.UserRole + 1))
        self._pending_highlight_file_id = file_id
        self.search_edit.clear()
        self.search_timer.stop()
        for index in range(self.project_list.count()):
            project_item = self.project_list.item(index)
            if project_item.data(Qt.ItemDataRole.UserRole) == project_id:
                if self.project_list.currentItem() is project_item:
                    self._project_selected(project_item, None)
                else:
                    self.project_list.setCurrentItem(project_item)
                break

    def _add_project(self) -> None:
        dialog = ProjectDialog(self)
        if dialog.exec():
            try:
                project_id = self.file_service.create_project(dialog.values())
                self._load_projects(project_id)
            except Exception as exc:
                self._show_error(exc)

    def _edit_project(self) -> None:
        if self.current_project_id is None:
            return
        project = self.file_service.get_project(self.current_project_id)
        if project is None:
            return
        dialog = ProjectDialog(self, values=project)
        if dialog.exec():
            try:
                self.file_service.update_project(
                    self.current_project_id, dialog.values()
                )
                self._load_projects(self.current_project_id)
            except Exception as exc:
                self._show_error(exc)

    def _delete_project(self) -> None:
        if self.current_project_id is None:
            return
        if QMessageBox.question(
            self,
            "确认删除",
            "删除项目将级联删除其全部档案和借阅记录，是否继续？",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.file_service.delete_project(self.current_project_id)
            self._load_projects()
        except Exception as exc:
            self._show_error(exc)

    def _add_file(self) -> None:
        if self.current_project_id is None:
            QMessageBox.information(self, "提示", "请先新增或选择项目。")
            return
        dialog = FileDialog(self)
        if dialog.exec():
            values = dialog.values()
            values["project_id"] = self.current_project_id
            try:
                self.file_service.create_file(values)
                self._refresh_files()
            except Exception as exc:
                self._show_error(exc)

    def _edit_file(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            QMessageBox.information(self, "提示", "请先选择档案。")
            return
        record = self.file_service.get_file(file_id)
        if record is None:
            return
        dialog = FileDialog(self, values=record)
        if dialog.exec():
            try:
                self.file_service.update_file(file_id, dialog.values())
                self._refresh_files()
                self._select_file_row(file_id)
            except Exception as exc:
                self._show_error(exc)

    def _delete_file(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            return
        if QMessageBox.question(
            self, "确认删除", "删除档案将同时删除其全部借阅记录，是否继续？"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.file_service.delete_file(file_id)
            self._refresh_files()
        except Exception as exc:
            self._show_error(exc)

    def _bind_file(self, file_id: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "绑定电子文件")
        if not path:
            return
        try:
            self.file_service.bind_file(file_id, path)
            self._refresh_files()
            self._select_file_row(file_id)
        except Exception as exc:
            self._show_error(exc)

    def _open_file(self, file_id: int) -> None:
        try:
            self.file_service.open_bound_file(file_id)
        except FileNotFoundError as exc:
            self._offer_rebind(file_id, str(exc))
        except Exception as exc:
            self._show_error(exc)

    def _open_folder(self, file_id: int) -> None:
        try:
            self.file_service.open_containing_folder(file_id)
        except FileNotFoundError as exc:
            self._offer_rebind(file_id, str(exc))
        except Exception as exc:
            self._show_error(exc)

    def _offer_rebind(self, file_id: int, message: str) -> None:
        if QMessageBox.question(
            self, "电子文件不可用", f"{message}\n\n是否立即重新绑定？"
        ) == QMessageBox.StandardButton.Yes:
            self._bind_file(file_id)

    def _borrow_file(self, file_id: int) -> None:
        dialog = BorrowDialog(self)
        if dialog.exec():
            try:
                self.borrow_service.borrow_file(file_id, **dialog.values())
                self._refresh_files()
                self._select_file_row(file_id)
            except Exception as exc:
                self._show_error(exc)

    def _return_file(self, file_id: int) -> None:
        active = self.borrow_service.active_record(file_id)
        if active is None:
            self._refresh_files()
            return
        dialog = ReturnDialog(self, borrow_date=active["borrow_date"])
        if dialog.exec():
            try:
                self.borrow_service.return_file(file_id, return_date=dialog.value())
                self._refresh_files()
                self._select_file_row(file_id)
            except Exception as exc:
                self._show_error(exc)

    def _import_excel(self) -> None:
        if self.current_project_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 Excel", filter="Excel 文件 (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            result = self.excel_service.import_project(self.current_project_id, path)
            self._refresh_files()
            detail = "\n".join(result["errors"][:10])
            QMessageBox.information(
                self,
                "导入完成",
                f"成功 {result['imported']} 条，失败 {result['failed']} 条。"
                + (f"\n\n{detail}" if detail else ""),
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_excel(self) -> None:
        if self.current_project_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", "档案台账.xlsx", "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            output = self.excel_service.export_project(self.current_project_id, path)
            QMessageBox.information(self, "导出完成", f"已导出到：\n{output}")
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, error: Exception) -> None:
        QMessageBox.critical(self, "操作失败", str(error))

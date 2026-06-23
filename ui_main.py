"""项目档案本地管理系统 V0.2 主界面。"""

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
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_paths import database_path, lock_config_path
from database import Database
from dialogs import (
    BatchDeleteDialog,
    BorrowDialog,
    BorrowHistoryDialog,
    FileDialog,
    PasswordDialog,
    ProjectDialog,
    ReturnDialog,
)
from services import BackupService, BorrowService, ExcelService, FileService, LockService


APP_NAME = "项目档案本地管理系统 V0.2"
PROJECT_FIELDS = (
    ("name", "项目名称"),
    ("short_name", "子项目简称"),
    ("construction_company", "施工单位"),
    ("contract_amount", "合同金额"),
    ("design_company", "设计单位"),
    ("design_amount", "设计金额"),
    ("supervision_company", "监理单位"),
    ("supervision_amount", "监理金额"),
    ("start_date", "开工日期"),
    ("completion_date", "完工日期"),
    ("contact_person", "联系人"),
    ("contact_phone", "联系电话"),
    ("remarks", "备注"),
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        database: Database | None = None,
        *,
        lock_service: LockService | None = None,
    ) -> None:
        super().__init__()
        if database is None:
            database = Database(database_path())
            database.initialize()
        self.database = database
        self.file_service = FileService(database)
        self.borrow_service = BorrowService(database)
        self.excel_service = ExcelService(database, self.file_service)
        self.backup_service = BackupService(database)
        self.lock_service = lock_service or LockService(lock_config_path())
        self.current_project_id: int | None = None
        self.global_mode = False
        self.recycle_mode = False
        self._current_rows: list[dict[str, Any]] = []

        self.setWindowTitle(APP_NAME)
        self.resize(1500, 900)
        self._build_ui()
        self._load_projects()

    def _build_ui(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, callback in (
            ("新增项目", self._add_project),
            ("全部导出", self._export_all),
            ("全部导入", self._import_all),
            ("完整备份", self._backup_all),
            ("恢复备份", self._restore_backup),
            ("应用锁", self._configure_lock),
        ):
            action = QAction(text, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" 全局搜索："))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索大项目、子项目、盒号、文件名、当前借用人")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(430)
        toolbar.addWidget(self.search_edit)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self._apply_global_search)

        root = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(root)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("项目组 / 子项目"))
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setMinimumWidth(320)
        self.project_tree.currentItemChanged.connect(self._project_selected)
        left_layout.addWidget(self.project_tree)
        buttons = QHBoxLayout()
        for text, callback in (
            ("编辑", self._edit_project),
            ("删除", self._delete_project),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        left_layout.addLayout(buttons)
        root.addWidget(left)

        right = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(right)
        root.setStretchFactor(1, 1)
        project_area = QScrollArea()
        project_area.setWidgetResizable(True)
        project_form = QWidget()
        self.project_grid = QGridLayout(project_form)
        self.project_editors: dict[str, QLineEdit | QPlainTextEdit] = {}
        for index, (field, label) in enumerate(PROJECT_FIELDS):
            row, pair = divmod(index, 2)
            editor: QLineEdit | QPlainTextEdit
            if field == "remarks":
                editor = QPlainTextEdit()
                editor.setMaximumHeight(70)
            else:
                editor = QLineEdit()
            self.project_grid.addWidget(QLabel(f"{label}："), row, pair * 2)
            self.project_grid.addWidget(editor, row, pair * 2 + 1)
            self.project_editors[field] = editor
        save = QPushButton("保存项目资料")
        save.clicked.connect(self._save_project_form)
        self.project_grid.addWidget(save, 7, 3)
        project_area.setWidget(project_form)
        right.addWidget(project_area)

        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        controls = QHBoxLayout()
        self.mode_label = QLabel("档案台账")
        controls.addWidget(self.mode_label)
        controls.addStretch()
        for text, callback in (
            ("新增档案", self._add_file),
            ("编辑档案", self._edit_file),
            ("批量移入回收站", self._delete_files),
            ("回收站", self._toggle_recycle),
            ("恢复所选", self._restore_selected_files),
            ("定位到项目", self._locate_selected_project),
            ("Excel 导入", self._import_excel),
            ("Excel 导出", self._export_excel),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
        table_layout.addLayout(controls)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table)
        right.addWidget(table_panel)
        right.setStretchFactor(1, 1)
        right.setSizes([300, 600])
        self.statusBar().showMessage("就绪")

    def _load_projects(self, select_project_id: int | None = None) -> None:
        if select_project_id is None:
            select_project_id = self.current_project_id
        self.project_tree.blockSignals(True)
        self.project_tree.clear()
        items: dict[int, QTreeWidgetItem] = {}
        projects = self.file_service.list_projects()
        for project in projects:
            if project.get("parent_project_id") is None:
                item = QTreeWidgetItem([str(project["name"])])
                item.setData(0, Qt.ItemDataRole.UserRole, int(project["id"]))
                self.project_tree.addTopLevelItem(item)
                items[int(project["id"])] = item
        for project in projects:
            parent_id = project.get("parent_project_id")
            if parent_id is None:
                continue
            label = project.get("short_name") or project["name"]
            item = QTreeWidgetItem([str(label)])
            item.setToolTip(0, str(project["name"]))
            item.setData(0, Qt.ItemDataRole.UserRole, int(project["id"]))
            items.get(int(parent_id), self.project_tree.invisibleRootItem()).addChild(item)
            items[int(project["id"])] = item
        self.project_tree.expandAll()
        self.project_tree.blockSignals(False)
        selected = items.get(int(select_project_id)) if select_project_id else None
        if selected is None and self.project_tree.topLevelItemCount():
            selected = self.project_tree.topLevelItem(0)
        if selected:
            self.project_tree.setCurrentItem(selected)
            self._project_selected(selected, None)
        else:
            self.current_project_id = None
            self._show_project(None)
            self._render_files([])

    def _project_selected(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            return
        self.current_project_id = int(current.data(0, Qt.ItemDataRole.UserRole))
        self._show_project(self.file_service.get_project(self.current_project_id))
        if not self.search_edit.text().strip():
            self.global_mode = False
            self._refresh_files()

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
        current = self.file_service.get_project(self.current_project_id) or {}
        values: dict[str, Any] = {"parent_project_id": current.get("parent_project_id")}
        for field, editor in self.project_editors.items():
            values[field] = (
                editor.toPlainText().strip()
                if isinstance(editor, QPlainTextEdit)
                else editor.text().strip()
            )
        try:
            self.file_service.update_project(self.current_project_id, values)
            self._load_projects(self.current_project_id)
            self.statusBar().showMessage("项目资料已保存", 3000)
        except Exception as exc:
            self._show_error(exc)

    def _render_files(self, rows: list[dict[str, Any]]) -> None:
        self._current_rows = [dict(row) for row in rows]
        columns = [
            ("project_name", "项目名称"),
            ("box_no", "盒号"),
            ("file_name", "文件名称"),
            ("original_inventory", "原件 可借/总数"),
            ("copy_inventory", "复印件 可借/总数"),
            ("status_display", "状态"),
            ("actions", "操作"),
        ]
        if not self.global_mode:
            columns = columns[1:]
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])
        self.table.setRowCount(len(rows))
        for row_index, record in enumerate(rows):
            file_id = int(record["file_id"])
            record = dict(record)
            record["original_inventory"] = (
                f"{record['available_original']}/{record['original_count']}"
            )
            record["copy_inventory"] = f"{record['available_copy']}/{record['copy_count']}"
            for column_index, (field, _) in enumerate(columns):
                if field == "actions":
                    self.table.setCellWidget(
                        row_index, column_index, self._action_widget(record)
                    )
                    continue
                item = QTableWidgetItem(str(record.get(field) or ""))
                item.setData(Qt.ItemDataRole.UserRole, file_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, int(record["project_id"]))
                if field == "status_display":
                    color = (
                        Qt.GlobalColor.darkGreen
                        if record["computed_status"] == "在库"
                        else Qt.GlobalColor.red
                    )
                    item.setForeground(color)
                self.table.setItem(row_index, column_index, item)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        name_column = next(i for i, (field, _) in enumerate(columns) if field == "file_name")
        header.setSectionResizeMode(name_column, QHeaderView.ResizeMode.Stretch)
        self.table.resizeRowsToContents()

    def _action_widget(self, record: dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        file_id = int(record["file_id"])
        if record.get("deleted_at"):
            actions = (("恢复", partial(self._restore_file, file_id)),)
        else:
            actions = (
                ("绑定", partial(self._bind_file, file_id)),
                ("打开", partial(self._open_file, file_id)),
                ("借阅", partial(self._borrow_file, file_id)),
                ("详情/归还", partial(self._borrow_history, file_id)),
            )
        for text, callback in actions:
            button = QPushButton(text)
            button.clicked.connect(callback)
            layout.addWidget(button)
        return widget

    def _selected_file_ids(self) -> list[int]:
        result: set[int] = set()
        for index in self.table.selectionModel().selectedRows():
            for column in range(self.table.columnCount()):
                item = self.table.item(index.row(), column)
                if item and item.data(Qt.ItemDataRole.UserRole):
                    result.add(int(item.data(Qt.ItemDataRole.UserRole)))
                    break
        return sorted(result)

    def _selected_file_id(self) -> int | None:
        values = self._selected_file_ids()
        return values[0] if values else None

    def _refresh_files(self) -> None:
        keyword = self.search_edit.text().strip()
        if keyword:
            self.global_mode = True
            self.recycle_mode = False
            rows = self.file_service.search_files(keyword)
            self.mode_label.setText(f"全局搜索结果（{len(rows)}）— 点击操作不会退出搜索")
        elif self.current_project_id is not None:
            self.global_mode = False
            rows = self.file_service.list_files(
                self.current_project_id, include_deleted=self.recycle_mode
            )
            if self.recycle_mode:
                rows = [row for row in rows if row.get("deleted_at")]
                self.mode_label.setText(f"回收站（{len(rows)}）")
            else:
                self.mode_label.setText("档案台账")
        else:
            rows = []
        self._render_files(rows)

    def _apply_global_search(self) -> None:
        self._refresh_files()

    def _locate_selected_project(self) -> None:
        file_id = self._selected_file_id()
        if file_id is None:
            QMessageBox.information(self, "提示", "请先选择一条搜索结果。")
            return
        record = self.file_service.get_file(file_id)
        if record is None:
            return
        self.search_edit.clear()
        self.search_timer.stop()
        self._load_projects(int(record["project_id"]))
        self._select_file_row(file_id)

    def _select_file_row(self, file_id: int) -> None:
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item and item.data(Qt.ItemDataRole.UserRole) == file_id:
                    self.table.selectRow(row)
                    self.table.scrollToItem(item)
                    return

    def _add_project(self) -> None:
        dialog = ProjectDialog(self, parent_projects=self.file_service.list_projects())
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
        dialog = ProjectDialog(
            self, values=project, parent_projects=self.file_service.list_projects()
        )
        if dialog.exec():
            try:
                self.file_service.update_project(self.current_project_id, dialog.values())
                self._load_projects(self.current_project_id)
            except Exception as exc:
                self._show_error(exc)

    def _delete_project(self) -> None:
        if self.current_project_id is None:
            return
        if QMessageBox.question(
            self, "确认删除", "删除项目将删除其全部档案和借阅历史，是否继续？"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.file_service.delete_project(self.current_project_id)
            self._load_projects()
        except Exception as exc:
            self._show_error(exc)

    def _add_file(self) -> None:
        if self.current_project_id is None:
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

    def _delete_files(self) -> None:
        if not self._current_rows:
            QMessageBox.information(self, "提示", "当前列表没有可删除的档案。")
            return
        dialog = BatchDeleteDialog(
            self,
            records=self._current_rows,
            preselected_ids=set(self._selected_file_ids()),
        )
        if not dialog.exec():
            return
        file_ids = dialog.selected_ids()
        if not file_ids:
            QMessageBox.information(self, "提示", "尚未勾选任何档案。")
            return
        if QMessageBox.question(
            self, "批量移入回收站", f"确定将选中的 {len(file_ids)} 条档案移入回收站？"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            count = self.file_service.delete_files(file_ids)
            self._refresh_files()
            self.statusBar().showMessage(f"已将 {count} 条档案移入回收站", 4000)
        except Exception as exc:
            self._show_error(exc)

    def _toggle_recycle(self) -> None:
        if self.search_edit.text():
            self.search_edit.clear()
        self.recycle_mode = not self.recycle_mode
        self._refresh_files()

    def _restore_file(self, file_id: int) -> None:
        self.file_service.restore_files([file_id])
        self._refresh_files()

    def _restore_selected_files(self) -> None:
        file_ids = self._selected_file_ids()
        if not file_ids:
            QMessageBox.information(self, "提示", "请先在回收站选择档案。")
            return
        try:
            count = self.file_service.restore_files(file_ids)
            self._refresh_files()
            self.statusBar().showMessage(f"已恢复 {count} 条档案", 3000)
        except Exception as exc:
            self._show_error(exc)

    def _bind_file(self, file_id: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "绑定电子文件")
        if path:
            try:
                self.file_service.bind_file(file_id, path)
                self._refresh_files()
            except Exception as exc:
                self._show_error(exc)

    def _open_file(self, file_id: int) -> None:
        try:
            self.file_service.open_bound_file(file_id)
        except Exception as exc:
            self._show_error(exc)

    def _borrow_file(self, file_id: int) -> None:
        record = self.file_service.get_file(file_id)
        if record is None:
            return
        dialog = BorrowDialog(
            self,
            available_original=int(record["available_original"]),
            available_copy=int(record["available_copy"]),
        )
        if dialog.exec():
            try:
                self.borrow_service.borrow_file(file_id, **dialog.values())
                self._refresh_files()
            except Exception as exc:
                self._show_error(exc)

    def _borrow_history(self, file_id: int) -> None:
        while True:
            records = self.borrow_service.history(file_id)
            dialog = BorrowHistoryDialog(self, records=records)
            if not dialog.exec() or dialog.selected_record_id is None:
                return
            record = next(
                item for item in records if item["id"] == dialog.selected_record_id
            )
            return_dialog = ReturnDialog(self, borrow_date=record["borrow_date"])
            if not return_dialog.exec():
                return
            try:
                self.borrow_service.return_record(
                    dialog.selected_record_id, return_date=return_dialog.value()
                )
                self._refresh_files()
            except Exception as exc:
                self._show_error(exc)
                return

    def _import_excel(self) -> None:
        if self.current_project_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入 Excel", filter="Excel (*.xlsx)")
        if not path:
            return
        try:
            result = self.excel_service.import_project(self.current_project_id, path)
            self._refresh_files()
            QMessageBox.information(
                self, "导入完成", f"成功 {result['imported']} 条，失败 {result['failed']} 条。"
            )
        except Exception as exc:
            self._show_error(exc)

    def _export_excel(self) -> None:
        if self.current_project_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出当前项目", "项目档案.xlsx", "Excel (*.xlsx)"
        )
        if path:
            try:
                output = self.excel_service.export_project(self.current_project_id, path)
                QMessageBox.information(self, "导出完成", f"已导出到：\n{output}")
            except Exception as exc:
                self._show_error(exc)

    def _export_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "全部导出", "全部项目档案.xlsx", "Excel (*.xlsx)"
        )
        if path:
            try:
                output = self.excel_service.export_all(path)
                QMessageBox.information(self, "导出完成", f"已导出到：\n{output}")
            except Exception as exc:
                self._show_error(exc)

    def _import_all(self) -> None:
        if QMessageBox.question(
            self,
            "整库导入",
            "整库导入会替换当前所有项目、档案和借阅历史。\n建议先执行完整备份。是否继续？",
        ) != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(self, "全部导入", filter="Excel (*.xlsx)")
        if path:
            try:
                self.backup_service.create_backup(
                    self.database.path.with_name("整库导入前自动备份.pambak")
                )
                result = self.excel_service.import_all(path)
                self._load_projects()
                QMessageBox.information(
                    self,
                    "导入完成",
                    f"项目 {result['projects']} 个，档案 {result['files']} 条，"
                    f"借阅记录 {result['borrows']} 条。",
                )
            except Exception as exc:
                self._show_error(exc)

    def _backup_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "完整备份", "项目档案完整备份.pambak", "备份文件 (*.pambak)"
        )
        if path:
            try:
                output = self.backup_service.create_backup(path)
                QMessageBox.information(self, "备份完成", f"已备份到：\n{output}")
            except Exception as exc:
                self._show_error(exc)

    def _restore_backup(self) -> None:
        if QMessageBox.question(
            self, "恢复备份", "恢复将替换当前数据，程序会先自动保存恢复前副本。是否继续？"
        ) != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "恢复备份", filter="备份文件 (*.pambak)"
        )
        if path:
            try:
                safety = self.backup_service.restore_backup(path)
                self._load_projects()
                QMessageBox.information(
                    self, "恢复完成", f"数据已恢复。\n恢复前副本：\n{safety}"
                )
            except Exception as exc:
                self._show_error(exc)

    def _configure_lock(self) -> None:
        if not self.lock_service.is_enabled():
            dialog = PasswordDialog(self, title="启用应用锁", confirm=True)
            if dialog.exec():
                try:
                    self.lock_service.set_password(dialog.password())
                    QMessageBox.information(self, "应用锁", "应用锁已启用，下次启动生效。")
                except Exception as exc:
                    self._show_error(exc)
            return
        current = PasswordDialog(self, title="验证当前密码")
        if not current.exec() or not self.lock_service.verify(current.password()):
            if current.result():
                QMessageBox.warning(self, "密码错误", "当前密码不正确。")
            return
        choice = QMessageBox.question(
            self,
            "应用锁",
            "选择“是”修改密码；选择“否”关闭应用锁。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Yes:
            new = PasswordDialog(self, title="设置新密码", confirm=True)
            if new.exec():
                try:
                    self.lock_service.set_password(new.password())
                    QMessageBox.information(self, "应用锁", "密码已修改。")
                except Exception as exc:
                    self._show_error(exc)
        elif choice == QMessageBox.StandardButton.No:
            self.lock_service.disable(current.password())
            QMessageBox.information(self, "应用锁", "应用锁已关闭。")

    def _show_error(self, error: Exception) -> None:
        QMessageBox.critical(self, "操作失败", str(error))

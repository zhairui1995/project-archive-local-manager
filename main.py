"""项目档案本地管理系统统一入口。

当前仓库仅完成第一、第二阶段。后续接入 ``ui_main.MainWindow`` 后，
本入口无需调整启动方式。
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from app_paths import application_data_dir, database_path
from database import Database


APP_NAME = "项目档案本地管理系统"


def create_main_window(database: Database) -> QMainWindow:
    """创建正式主窗口。"""
    from ui_main import MainWindow

    return MainWindow(database)


def main() -> int:
    application_data_dir().mkdir(parents=True, exist_ok=True)
    database = Database(database_path())
    database.initialize()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = create_main_window(database)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

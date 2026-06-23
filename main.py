"""项目档案本地管理系统统一入口。

当前仓库仅完成第一、第二阶段。后续接入 ``ui_main.MainWindow`` 后，
本入口无需调整启动方式。
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox

from app_paths import application_data_dir, database_path, lock_config_path
from database import Database
from dialogs import PasswordDialog
from services import LockService


APP_NAME = "项目档案本地管理系统 V0.2"


def create_main_window(
    database: Database, lock_service: LockService | None = None
) -> QMainWindow:
    """创建正式主窗口。"""
    from ui_main import MainWindow

    return MainWindow(database, lock_service=lock_service)


def main() -> int:
    application_data_dir().mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    lock_service = LockService(lock_config_path())
    if lock_service.is_enabled():
        for _ in range(3):
            dialog = PasswordDialog(title="请输入应用锁密码")
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
            if lock_service.verify(dialog.password()):
                break
            QMessageBox.warning(None, "密码错误", "密码不正确，请重试。")
        else:
            QMessageBox.critical(None, "已锁定", "连续三次密码错误，程序将退出。")
            return 1
    database = Database(database_path())
    database.initialize()
    window = create_main_window(database, lock_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""跨平台应用数据路径。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "ProjectArchiveManager"


def application_data_dir() -> Path:
    """返回当前用户可写的数据目录。"""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
        return base / APP_DIR_NAME / "data"
    return Path(__file__).resolve().parent / "data"


def database_path() -> Path:
    return application_data_dir() / "project_archives.db"


def lock_config_path() -> Path:
    return application_data_dir() / "app_lock.json"

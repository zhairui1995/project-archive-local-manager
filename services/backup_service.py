"""数据库完整备份与恢复。"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from database import Database, SCHEMA_VERSION


class BackupService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_backup(self, output_path: str | Path) -> Path:
        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".pambak":
            output = output.with_suffix(".pambak")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            snapshot = temp / "project_archives.db"
            source = sqlite3.connect(self.database.path)
            target = sqlite3.connect(snapshot)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            manifest = {
                "format": "ProjectArchiveManagerBackup",
                "format_version": 1,
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            manifest_path = temp / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary = output.with_suffix(output.suffix + ".tmp")
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.write(snapshot, "project_archives.db")
                archive.write(manifest_path, "manifest.json")
            temporary.replace(output)
        return output

    def restore_backup(self, input_path: str | Path) -> Path:
        source = Path(input_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError("备份文件不存在。")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            with zipfile.ZipFile(source) as archive:
                names = set(archive.namelist())
                if {"manifest.json", "project_archives.db"} - names:
                    raise ValueError("不是有效的项目档案备份文件。")
                manifest = json.loads(archive.read("manifest.json"))
                if manifest.get("format") != "ProjectArchiveManagerBackup":
                    raise ValueError("备份文件格式不受支持。")
                archive.extract("project_archives.db", temp)
            restored = temp / "project_archives.db"
            with sqlite3.connect(restored) as conn:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("备份数据库完整性检查失败。")
            safety = self.database.path.with_name(
                f"{self.database.path.stem}-恢复前-"
                f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
            )
            if self.database.path.exists():
                shutil.copy2(self.database.path, safety)
            for suffix in ("-wal", "-shm"):
                Path(str(self.database.path) + suffix).unlink(missing_ok=True)
            shutil.copy2(restored, self.database.path)
            self.database.initialize()
        return safety

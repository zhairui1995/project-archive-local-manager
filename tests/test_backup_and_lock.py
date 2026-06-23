from __future__ import annotations

from database import Database
from services import BackupService, FileService, LockService


def test_lock_service_round_trip(tmp_path) -> None:
    service = LockService(tmp_path / "lock.json")
    assert not service.is_enabled()
    service.set_password("secret123")
    assert service.verify("secret123")
    assert not service.verify("wrong")
    service.change_password("secret123", "new-secret")
    assert service.verify("new-secret")
    service.disable("new-secret")
    assert not service.is_enabled()


def test_backup_and_restore(tmp_path) -> None:
    database = Database(tmp_path / "archive.db")
    database.initialize()
    files = FileService(database)
    files.create_project({"name": "备份前项目"})
    service = BackupService(database)
    backup = service.create_backup(tmp_path / "backup.pambak")
    files.create_project({"name": "备份后项目"})
    safety = service.restore_backup(backup)
    assert safety.is_file()
    assert [item["name"] for item in files.list_projects()] == ["备份前项目"]

from __future__ import annotations

from pathlib import Path

import app_paths


def test_windows_database_uses_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert app_paths.database_path() == (
        tmp_path / "ProjectArchiveManager" / "data" / "project_archives.db"
    )

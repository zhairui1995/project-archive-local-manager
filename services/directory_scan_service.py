"""只读扫描目录，生成可供批量建档使用的文件清单。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class DirectoryScanService:
    @staticmethod
    def scan(
        root: str | Path,
        *,
        recursive: bool = True,
        extensions: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        root_path = Path(root).expanduser().resolve()
        if not root_path.is_dir():
            raise NotADirectoryError("扫描目录不存在或不是有效目录。")

        allowed = None
        if extensions:
            allowed = {
                extension.lower()
                if extension.startswith(".")
                else f".{extension.lower()}"
                for extension in extensions
            }

        iterator = root_path.rglob("*") if recursive else root_path.glob("*")
        rows: list[dict[str, str]] = []
        for path in iterator:
            if not path.is_file() or (allowed and path.suffix.lower() not in allowed):
                continue
            rows.append(
                {
                    "name": path.stem,
                    "file_path": str(path.resolve()),
                    "relative_path": str(path.relative_to(root_path)),
                    "extension": path.suffix.lower(),
                }
            )
        rows.sort(key=lambda row: row["relative_path"].casefold())
        return rows

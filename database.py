"""SQLite 数据库基础设施、版本迁移与档案库存查询。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


DEFAULT_BUSY_TIMEOUT_MS = 30_000
SCHEMA_VERSION = 2


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS Projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    construction_company TEXT,
    contract_amount TEXT,
    supervision_company TEXT,
    supervision_amount TEXT,
    start_date TEXT,
    contact_person TEXT,
    contact_phone TEXT,
    remarks TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parent_project_id INTEGER,
    short_name TEXT,
    design_company TEXT,
    design_amount TEXT,
    completion_date TEXT,
    FOREIGN KEY (parent_project_id) REFERENCES Projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    box_no TEXT,
    name TEXT NOT NULL,
    type TEXT,
    count_text TEXT,
    file_path TEXT,
    original_count INTEGER NOT NULL DEFAULT 1 CHECK (original_count >= 0),
    copy_count INTEGER NOT NULL DEFAULT 0 CHECK (copy_count >= 0),
    deleted_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES Projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS BorrowRecords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    borrower TEXT NOT NULL,
    contact TEXT,
    reason TEXT,
    borrow_date DATE NOT NULL,
    return_date DATE,
    media_type TEXT NOT NULL DEFAULT '原件'
        CHECK (media_type IN ('原件', '复印件')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    expected_return_date DATE,
    FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE,
    CHECK (return_date IS NULL OR return_date >= borrow_date),
    CHECK (
        expected_return_date IS NULL
        OR expected_return_date >= borrow_date
    )
);

CREATE INDEX IF NOT EXISTS idx_projects_parent ON Projects(parent_project_id);
CREATE INDEX IF NOT EXISTS idx_files_project_id ON Files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_box_no ON Files(box_no);
CREATE INDEX IF NOT EXISTS idx_files_name ON Files(name);
CREATE INDEX IF NOT EXISTS idx_files_deleted_at ON Files(deleted_at);
CREATE INDEX IF NOT EXISTS idx_borrow_records_file_id ON BorrowRecords(file_id);
CREATE INDEX IF NOT EXISTS idx_borrow_records_borrower ON BorrowRecords(borrower);
"""


FILE_STATUS_SELECT = """
SELECT
    f.id AS file_id,
    f.project_id,
    p.name AS project_name,
    COALESCE(p.short_name, '') AS project_short_name,
    parent.name AS parent_project_name,
    f.box_no,
    f.name AS file_name,
    f.type AS file_type,
    f.count_text,
    f.file_path,
    f.original_count,
    f.copy_count,
    f.deleted_at,
    COALESCE(active.borrowed_original, 0) AS borrowed_original,
    COALESCE(active.borrowed_copy, 0) AS borrowed_copy,
    f.original_count - COALESCE(active.borrowed_original, 0)
        AS available_original,
    f.copy_count - COALESCE(active.borrowed_copy, 0)
        AS available_copy,
    COALESCE(active.active_borrow_count, 0) AS active_borrow_count,
    active.borrowers,
    CASE
        WHEN COALESCE(active.active_borrow_count, 0) = 0 THEN '在库'
        WHEN (
            f.original_count - COALESCE(active.borrowed_original, 0) = 0
            AND f.copy_count - COALESCE(active.borrowed_copy, 0) = 0
        ) THEN '全部借出'
        ELSE '部分借出'
    END AS computed_status,
    CASE
        WHEN COALESCE(active.active_borrow_count, 0) = 0 THEN '🟢 在库'
        WHEN (
            f.original_count - COALESCE(active.borrowed_original, 0) = 0
            AND f.copy_count - COALESCE(active.borrowed_copy, 0) = 0
        ) THEN '🔴 全部借出：' || active.borrowers
        ELSE '🟠 部分借出：' || active.borrowers
    END AS status_display
FROM Files AS f
INNER JOIN Projects AS p ON p.id = f.project_id
LEFT JOIN Projects AS parent ON parent.id = p.parent_project_id
LEFT JOIN (
    SELECT
        file_id,
        SUM(CASE WHEN media_type = '原件' THEN quantity ELSE 0 END)
            AS borrowed_original,
        SUM(CASE WHEN media_type = '复印件' THEN quantity ELSE 0 END)
            AS borrowed_copy,
        COUNT(*) AS active_borrow_count,
        GROUP_CONCAT(borrower, '、') AS borrowers
    FROM BorrowRecords
    WHERE return_date IS NULL
    GROUP BY file_id
) AS active ON active.file_id = f.id
"""


class Database:
    """管理连接、事务、版本迁移和查询。"""

    def __init__(
        self,
        database_path: str | Path,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.busy_timeout_ms = busy_timeout_ms

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level="DEFERRED",
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        if existed:
            with sqlite3.connect(self.path) as probe:
                version = int(probe.execute("PRAGMA user_version").fetchone()[0])
                has_legacy_tables = probe.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Projects'"
                ).fetchone()
            if has_legacy_tables and version < SCHEMA_VERSION:
                self._create_upgrade_backup()

        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            self._migrate(conn)
            conn.executescript(SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._validate_schema(conn)

    def _create_upgrade_backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.stem}-升级前-{stamp}.db")
        source = sqlite3.connect(self.path)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return target

    @staticmethod
    def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
        return {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }

    def _migrate(self, conn: sqlite3.Connection) -> None:
        projects_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Projects'"
        ).fetchone()
        if not projects_exists:
            conn.executescript(SCHEMA_SQL)
            return

        project_columns = self._column_names(conn, "Projects")
        for definition in (
            "parent_project_id INTEGER REFERENCES Projects(id) ON DELETE SET NULL",
            "short_name TEXT",
            "design_company TEXT",
            "design_amount TEXT",
            "completion_date TEXT",
        ):
            name = definition.split()[0]
            if name not in project_columns:
                conn.execute(f"ALTER TABLE Projects ADD COLUMN {definition}")

        file_columns = self._column_names(conn, "Files")
        for definition in (
            "original_count INTEGER NOT NULL DEFAULT 1 CHECK (original_count >= 0)",
            "copy_count INTEGER NOT NULL DEFAULT 0 CHECK (copy_count >= 0)",
            "deleted_at DATETIME",
        ):
            name = definition.split()[0]
            if name not in file_columns:
                conn.execute(f"ALTER TABLE Files ADD COLUMN {definition}")

        borrow_columns = self._column_names(conn, "BorrowRecords")
        for definition in (
            "media_type TEXT NOT NULL DEFAULT '原件'",
            "quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0)",
            "expected_return_date DATE",
        ):
            name = definition.split()[0]
            if name not in borrow_columns:
                conn.execute(f"ALTER TABLE BorrowRecords ADD COLUMN {definition}")

        # V0.1 用唯一索引禁止并行借阅；V0.2 改为按库存数量控制。
        conn.execute("DROP INDEX IF EXISTS idx_borrow_one_active_record")

    def _validate_schema(self, conn: sqlite3.Connection) -> None:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise RuntimeError(f"数据库版本异常：期望 {SCHEMA_VERSION}，实际 {version}。")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"数据库存在外键完整性错误：{violations!r}")

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> int:
        with self.connection() as conn:
            cursor = conn.execute(sql, parameters)
            return int(cursor.lastrowid or 0)

    def execute_affected(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> int:
        with self.connection() as conn:
            return conn.execute(sql, parameters).rowcount

    def fetch_all(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(sql, parameters).fetchall()
        return [dict(row) for row in rows]

    def fetch_one(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(sql, parameters).fetchone()
        return dict(row) if row is not None else None

    def list_projects(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                p.*,
                parent.name AS parent_project_name
            FROM Projects AS p
            LEFT JOIN Projects AS parent ON parent.id = p.parent_project_id
            ORDER BY
                CASE WHEN p.parent_project_id IS NULL THEN p.id ELSE p.parent_project_id END,
                CASE WHEN p.parent_project_id IS NULL THEN 0 ELSE 1 END,
                p.id
            """
        )

    def list_files_with_status(
        self, project_id: int, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        deleted_clause = "" if include_deleted else "AND f.deleted_at IS NULL"
        return self.fetch_all(
            FILE_STATUS_SELECT
            + f"""
            WHERE f.project_id = ? {deleted_clause}
            ORDER BY
                CASE WHEN f.box_no IS NULL OR f.box_no = '' THEN 1 ELSE 0 END,
                f.box_no COLLATE NOCASE,
                f.id
            """,
            (project_id,),
        )

    def get_file_with_status(self, file_id: int) -> dict[str, Any] | None:
        return self.fetch_one(FILE_STATUS_SELECT + " WHERE f.id = ?", (file_id,))

    def search_files_global(self, keyword: str) -> list[dict[str, Any]]:
        normalized = keyword.strip()
        if not normalized:
            return []
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        return self.fetch_all(
            FILE_STATUS_SELECT
            + """
            WHERE f.deleted_at IS NULL AND (
                p.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(p.short_name, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(parent.name, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(f.box_no, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR f.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR EXISTS (
                    SELECT 1
                    FROM BorrowRecords AS search_br
                    WHERE search_br.file_id = f.id
                      AND search_br.return_date IS NULL
                      AND search_br.borrower LIKE ? ESCAPE '\\' COLLATE NOCASE
                )
            )
            ORDER BY p.name COLLATE NOCASE, f.box_no COLLATE NOCASE, f.id
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern),
        )


def init_database(database_path: str | Path) -> Database:
    database = Database(database_path)
    database.initialize()
    return database

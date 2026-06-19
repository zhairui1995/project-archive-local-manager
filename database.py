"""SQLite 数据库基础设施与动态档案状态查询。

设计约束：
1. Files 表绝不保存 status 字段。
2. “在库/已借出”仅由 return_date IS NULL 的借阅记录动态计算。
3. 每个数据库连接都启用外键、busy timeout，并由上下文管理器负责事务。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


DEFAULT_BUSY_TIMEOUT_MS = 30_000


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
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    box_no TEXT,
    name TEXT NOT NULL,
    type TEXT,
    count_text TEXT,
    file_path TEXT,
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
    FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE,
    CHECK (return_date IS NULL OR return_date >= borrow_date)
);

CREATE INDEX IF NOT EXISTS idx_files_project_id ON Files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_box_no ON Files(box_no);
CREATE INDEX IF NOT EXISTS idx_files_name ON Files(name);
CREATE INDEX IF NOT EXISTS idx_borrow_records_file_id ON BorrowRecords(file_id);
CREATE INDEX IF NOT EXISTS idx_borrow_records_borrower ON BorrowRecords(borrower);

CREATE UNIQUE INDEX IF NOT EXISTS idx_borrow_one_active_record
ON BorrowRecords(file_id)
WHERE return_date IS NULL;
"""


FILE_STATUS_SELECT = """
SELECT
    f.id AS file_id,
    f.project_id,
    p.name AS project_name,
    f.box_no,
    f.name AS file_name,
    f.type AS file_type,
    f.count_text,
    f.file_path,
    br.id AS active_borrow_id,
    br.borrower,
    br.contact AS borrower_contact,
    br.reason AS borrow_reason,
    br.borrow_date,
    CASE
        WHEN br.id IS NULL THEN '在库'
        ELSE '已借出'
    END AS computed_status,
    CASE
        WHEN br.id IS NULL THEN '🟢 在库'
        ELSE '🔴 已借出：' || br.borrower
    END AS status_display
FROM Files AS f
INNER JOIN Projects AS p ON p.id = f.project_id
LEFT JOIN BorrowRecords AS br
    ON br.file_id = f.id
   AND br.return_date IS NULL
"""


class Database:
    """管理 SQLite 连接、建表校验和基础联合查询。"""

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
        """提供自动提交/回滚/关闭的数据库连接。

        每次连接均执行 ``PRAGMA foreign_keys = ON``。写操作发生锁竞争时，
        SQLite 会在 busy timeout 内等待，而不是立即抛出 database is locked。
        """
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
        """初始化数据库，并验证关键结构约束。"""
        with self.connection() as conn:
            # WAL 提升单机程序读写并发能力；NORMAL 在可靠性和性能间取平衡。
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(SCHEMA_SQL)
            self._validate_schema(conn)

    def _validate_schema(self, conn: sqlite3.Connection) -> None:
        """拒绝带硬编码状态列或缺少关键约束的数据库。"""
        file_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(Files)").fetchall()
        }
        if "status" in {name.lower() for name in file_columns}:
            raise RuntimeError(
                "数据库结构不合法：Files 表禁止包含 status 字段，"
                "状态必须由有效借阅记录动态计算。"
            )

        foreign_keys_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        if foreign_keys_enabled != 1:
            raise RuntimeError("数据库连接未成功启用 PRAGMA foreign_keys = ON。")

        index_rows = conn.execute("PRAGMA index_list(BorrowRecords)").fetchall()
        active_index = next(
            (
                row
                for row in index_rows
                if row["name"] == "idx_borrow_one_active_record"
            ),
            None,
        )
        if active_index is None or active_index["unique"] != 1 or active_index["partial"] != 1:
            raise RuntimeError("缺少防止重复借阅的唯一部分索引。")

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"数据库存在外键完整性错误：{violations!r}")

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> int:
        """执行单条写语句并返回 lastrowid。

        业务层可使用此方法完成简单写入；复杂事务应直接使用
        ``with database.connection() as conn``，确保多条语句原子提交。
        """
        with self.connection() as conn:
            cursor = conn.execute(sql, parameters)
            return int(cursor.lastrowid or 0)

    def execute_affected(
        self,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] = (),
    ) -> int:
        """执行写语句并返回受影响行数。"""
        with self.connection() as conn:
            cursor = conn.execute(sql, parameters)
            return cursor.rowcount

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
        """按创建顺序返回左侧列表所需的全部项目。"""
        return self.fetch_all(
            """
            SELECT
                id,
                name,
                construction_company,
                contract_amount,
                supervision_company,
                supervision_amount,
                start_date,
                contact_person,
                contact_phone,
                remarks,
                created_at
            FROM Projects
            ORDER BY id ASC
            """
        )

    def list_files_with_status(self, project_id: int) -> list[dict[str, Any]]:
        """查询指定项目档案，状态由有效借阅记录实时计算。"""
        return self.fetch_all(
            FILE_STATUS_SELECT
            + """
            WHERE f.project_id = ?
            ORDER BY
                CASE WHEN f.box_no IS NULL OR f.box_no = '' THEN 1 ELSE 0 END,
                f.box_no COLLATE NOCASE,
                f.id
            """,
            (project_id,),
        )

    def get_file_with_status(self, file_id: int) -> dict[str, Any] | None:
        """查询单条档案及其实时借阅状态。"""
        return self.fetch_one(
            FILE_STATUS_SELECT + " WHERE f.id = ?",
            (file_id,),
        )

    def search_files_global(self, keyword: str) -> list[dict[str, Any]]:
        """跨项目搜索项目名、盒号、文件名和当前借用人。

        借用人匹配仅针对尚未归还的借阅记录，与界面当前状态保持一致。
        空关键词返回空列表，避免误加载全部档案。
        """
        normalized = keyword.strip()
        if not normalized:
            return []

        escaped = (
            normalized.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        return self.fetch_all(
            FILE_STATUS_SELECT
            + """
            WHERE
                p.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(f.box_no, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR f.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(br.borrower, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
            ORDER BY p.name COLLATE NOCASE, f.box_no COLLATE NOCASE, f.id
            """,
            (pattern, pattern, pattern, pattern),
        )


def init_database(database_path: str | Path) -> Database:
    """初始化并返回数据库对象，便于入口或脚本调用。"""
    database = Database(database_path)
    database.initialize()
    return database

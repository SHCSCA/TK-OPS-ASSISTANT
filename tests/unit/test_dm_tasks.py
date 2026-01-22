"""私信任务队列（dm_tasks）数据库结构测试。"""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

# 保障测试在任意工作目录下都能解析 src/ 模块
SRC_DIR = (Path(__file__).resolve().parents[2] / "src").resolve()
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db.migrations import MigrationManager  # type: ignore[import-not-found]


def test_dm_tasks_unique_comment_id(tmp_path: Path):
    """dm_tasks 的 comment_id 应保持唯一，重复插入不应新增。"""
    db_path = tmp_path / "assets.db"
    manager = MigrationManager(db_path=str(db_path))
    manager.run_migrations()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dm_tasks (comment_id, status, message) VALUES (?, ?, ?)",
            (123, "pending", "hello"),
        )
        # 触发唯一约束：同 comment_id 重复插入
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO dm_tasks (comment_id, status, message) VALUES (?, ?, ?)",
                (123, "pending", "hello again"),
            )
        except Exception:
            # 若执行不走 IGNORE，则此处也不应导致测试失败
            pass
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM dm_tasks WHERE comment_id=?", (123,))
        count = cursor.fetchone()[0]
        assert count == 1

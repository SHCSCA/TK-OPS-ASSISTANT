"""
素材库 SQLite：存储下载/处理的视频、图片、文件元数据
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import config

logger = logging.getLogger(__name__)


class AssetLibrary:
    """素材库管理（SQLite）"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(config.ASSET_LIBRARY_DIR / "assets.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()

            # 主素材表
            c.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,              -- video / image / document
                title TEXT,
                file_path TEXT NOT NULL,
                file_size INTEGER,               -- 字节
                duration REAL,                   -- 视频秒数
                source_url TEXT,
                source_type TEXT,                -- download / blue_ocean / user_upload
                tags TEXT,                       -- JSON 数组
                metadata TEXT,                   -- JSON 对象
                status TEXT DEFAULT 'active',    -- active / archived / deleted
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 处理记录表
            c.execute('''
            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                process_type TEXT,               -- video_remix / compress / etc
                input_path TEXT,
                output_path TEXT,
                params TEXT,                     -- JSON
                status TEXT,                     -- success / failed
                error_msg TEXT,
                elapsed_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
            ''')

            # 索引
            c.execute('CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_logs_asset_id ON processing_logs(asset_id)')

            conn.commit()
    
    def add_asset(self, 
                  asset_id: str,
                  file_type: str,
                  file_path: str,
                  title: str = None,
                  source_url: str = None,
                  source_type: str = "user_upload",
                  tags: List[str] = None,
                  metadata: Dict[str, Any] = None,
                  type_tag: str = "",
                  emotion_tag: str = "",
                  object_tag: str = "") -> bool:
        """添加素材到库"""
        try:
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size if file_path_obj.exists() else 0

            with sqlite3.connect(str(self.db_path)) as conn:
                c = conn.cursor()

                c.execute('''
                INSERT OR REPLACE INTO assets 
                (asset_id, type, title, file_path, file_size, source_url, source_type, tags, metadata, type_tag, emotion_tag, object_tag, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(last_used_at, CURRENT_TIMESTAMP))
                ''', (
                    asset_id,
                    file_type,
                    title or file_path_obj.stem,
                    str(file_path_obj),
                    file_size,
                    source_url,
                    source_type,
                    json.dumps(tags or []),
                    json.dumps(metadata or {}),
                    (type_tag or "").strip(),
                    (emotion_tag or "").strip(),
                    (object_tag or "").strip(),
                ))

                conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加素材失败: {e}")
            return False

    def select_asset_by_tags(self, type_tag: str, emotion_tag: str, object_tag: str) -> Optional[Dict[str, Any]]:
        """按标签选择最少使用的素材（避免重复）。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    """
                    SELECT * FROM assets
                    WHERE status = 'active'
                      AND type_tag = ? AND emotion_tag = ? AND object_tag = ?
                    ORDER BY last_used_at ASC
                    LIMIT 1
                    """,
                    ((type_tag or "").strip(), (emotion_tag or "").strip(), (object_tag or "").strip()),
                )
                row = c.fetchone()
                if not row:
                    return None
                d = dict(row)
                d["tags"] = json.loads(d.get("tags", "[]"))
                d["metadata"] = json.loads(d.get("metadata", "{}"))

                # 更新使用时间
                c.execute("UPDATE assets SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (d.get("id"),))
                conn.commit()
                return d
        except Exception as e:
            logger.error(f"按标签选取素材失败: {e}")
            return None
    
    def log_processing(self,
                      asset_id: str,
                      process_type: str,
                      input_path: str,
                      output_path: str,
                      params: Dict[str, Any],
                      success: bool,
                      error_msg: str = "",
                      elapsed_seconds: float = 0) -> bool:
        """记录处理日志"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                c = conn.cursor()

                c.execute('''
                INSERT INTO processing_logs
                (asset_id, process_type, input_path, output_path, params, status, error_msg, elapsed_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    asset_id,
                    process_type,
                    input_path,
                    output_path,
                    json.dumps(params),
                    "success" if success else "failed",
                    error_msg,
                    elapsed_seconds
                ))

                conn.commit()
            return True
        except Exception as e:
            logger.error(f"记录处理日志失败: {e}")
            return False
    
    def search_assets(self,
                     file_type: str = None,
                     status: str = "active",
                     tags: List[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """查询素材"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                query = "SELECT * FROM assets WHERE status = ?"
                params = [status]

                if file_type:
                    query += " AND type = ?"
                    params.append(file_type)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                c.execute(query, params)
                rows = c.fetchall()

                results = []
                for row in rows:
                    d = dict(row)
                    d['tags'] = json.loads(d.get('tags', '[]'))
                    d['metadata'] = json.loads(d.get('metadata', '{}'))
                    results.append(d)

                return results
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []
    
    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """获取单个素材"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                c.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
                row = c.fetchone()

                if row:
                    d = dict(row)
                    d['tags'] = json.loads(d.get('tags', '[]'))
                    d['metadata'] = json.loads(d.get('metadata', '{}'))
                    return d
                return None
        except Exception:
            return None
    
    def get_processing_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """获取素材的处理历史"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                c.execute('''
                SELECT * FROM processing_logs 
                WHERE asset_id = ?
                ORDER BY created_at DESC
                ''', (asset_id,))

                rows = c.fetchall()

                results = []
                for row in rows:
                    d = dict(row)
                    d['params'] = json.loads(d.get('params', '{}'))
                    results.append(d)

                return results
        except Exception:
            return []
    
    def delete_asset(self, asset_id: str) -> bool:
        """标记素材为已删除（逻辑删除）"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                c = conn.cursor()

                c.execute('''
                UPDATE assets SET status = 'deleted', updated_at = CURRENT_TIMESTAMP
                WHERE asset_id = ?
                ''', (asset_id,))

                conn.commit()
            return True
        except Exception:
            return False
    
    def statistics(self) -> Dict[str, Any]:
        """获取库统计信息"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                c = conn.cursor()

                c.execute("SELECT COUNT(*) FROM assets WHERE status = 'active'")
                total = c.fetchone()[0]

                c.execute("SELECT type, COUNT(*) FROM assets WHERE status = 'active' GROUP BY type")
                by_type = {row[0]: row[1] for row in c.fetchall()}

                c.execute("SELECT SUM(file_size) FROM assets WHERE status = 'active'")
                total_size = c.fetchone()[0] or 0

                c.execute("SELECT COUNT(*) FROM processing_logs WHERE status = 'success'")
                success_ops = c.fetchone()[0]

                return {
                    'total_assets': total,
                    'by_type': by_type,
                    'total_size_mb': round(total_size / 1024 / 1024, 2),
                    'successful_operations': success_ops,
                }
        except Exception:
            return {}

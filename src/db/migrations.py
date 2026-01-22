"""
数据库迁移管理器 (V1.0 -> V2.0)
负责平滑升级数据库结构，支持新功能模块
"""
import sqlite3
import logging
from pathlib import Path

import config

logger = logging.getLogger(__name__)

class MigrationManager:
    """管理 V1.0 到 V2.0 的数据库结构变更"""
    
    def __init__(self, db_path: str | None = None):
        # 统一数据库位置：与素材库/CRM 保持一致，避免打包后出现“迁移在 A 库，读取在 B 库”
        if db_path is None:
            try:
                db_path = str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
            except Exception:
                db_path = "AssetLibrary/assets.db"
        self.db_path = str(db_path)
        self.ensure_directory()

    def ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def run_migrations(self):
        """执行所有挂起的数据库迁移（自动补全所有核心表结构，包括 assets 表）"""
        logger.info(f"[DB] 使用数据库：{self.db_path}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                logger.info("开始执行 V2.0 数据库迁移...")

                # 0. 创建素材库主表（必须，兼容 asset_library.py）
                self._create_assets_table(cursor)

                # 1. 创建账号表 (CRM Module)
                self._create_accounts_table(cursor)

                # 2. 创建利润配置表 (Profit Module)
                self._create_profit_config_table(cursor)

                # 3. 扩展 product_history 表 (新增利润字段)
                self._migrate_product_history(cursor)

                # 4. 初始化默认配置
                self._initialize_default_config(cursor)

                # 5. 评论区表（V2.2）
                self._create_comments_table(cursor)

                # 6. 素材库标签字段（V2.2）
                self._migrate_assets_table(cursor)

                # 7. 私信任务表（V2.2）
                self._create_dm_tasks_table(cursor)

                conn.commit()
                logger.info("✅ 数据库迁移完成")
        except sqlite3.Error as e:
            logger.error(f"❌ 数据库迁移失败: {e}")

    def _create_assets_table(self, cursor):
        """创建素材库主表（与 asset_library.py 保持一致，避免多处定义漂移）"""
        cursor.execute('''
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
        # 索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at)')

    def _create_accounts_table(self, cursor):
        """创建账号矩阵管理表"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'active', -- active, shadowban, suspended
                proxy_ip TEXT,
                last_post_date DATETIME,
                today_post_count INTEGER DEFAULT 0,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("✅ accounts 表已创建/检查")

    def _create_profit_config_table(self, cursor):
        """创建利润核算配置表"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profit_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        logger.info("✅ profit_config 表已创建/检查")

    def _migrate_product_history(self, cursor):
        """扩展 product_history 表，新增利润相关字段"""
        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='product_history'
        """)
        
        if not cursor.fetchone():
            # 表不存在，创建完整的新表
            cursor.execute("""
                CREATE TABLE product_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    tk_price REAL DEFAULT 0,
                    sales_count INTEGER DEFAULT 0,
                    cny_cost REAL DEFAULT 0,
                    weight REAL DEFAULT 0,
                    net_profit REAL DEFAULT 0,
                    source_file TEXT,
                    image_url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ product_history 表已创建（全新）")
            return

        # 表已存在，检查并添加新列
        cursor.execute("PRAGMA table_info(product_history)")
        columns = [info[1] for info in cursor.fetchall()]
        
        new_columns = {
            'tk_price': 'REAL DEFAULT 0',
            'cny_cost': 'REAL DEFAULT 0',
            'weight': 'REAL DEFAULT 0',
            'net_profit': 'REAL DEFAULT 0',
            'source_file': 'TEXT',
            'sales_count': 'INTEGER DEFAULT 0',
            'image_url': 'TEXT'
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE product_history ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ 新增字段: product_history.{col_name}")

    def _initialize_default_config(self, cursor):
        """初始化默认的利润核算配置"""
        default_configs = [
            ('exchange_rate', '7.25'),
            ('shipping_cost_per_kg', '12.0'),
            ('platform_commission', '0.05'),
            ('fixed_fee', '0.3')
        ]
        
        for key, value in default_configs:
            cursor.execute("""
                INSERT OR IGNORE INTO profit_config (key, value) 
                VALUES (?, ?)
            """, (key, value))
        
        logger.info("✅ 默认利润配置已初始化")

    def _create_comments_table(self, cursor):
        """创建评论区 CRM 表（V2.2）"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                comment_id TEXT,
                author TEXT,
                content TEXT,
                sentiment_score REAL DEFAULT 0,
                lead_tier INTEGER DEFAULT 3,
                is_replied INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_lead ON comments(lead_tier)")
        logger.info("✅ comments 表已创建/检查")

    def _migrate_assets_table(self, cursor):
        """为素材库补充标签字段与last_used_at。若表不存在则跳过，不中断迁移。"""
        try:
            cursor.execute("PRAGMA table_info(assets)")
            columns = [info[1] for info in cursor.fetchall()]
        except Exception:
            logger.warning("⚠️ assets 表不存在，跳过标签字段迁移。")
            return
        new_columns = {
            "type_tag": "TEXT",
            "emotion_tag": "TEXT",
            "object_tag": "TEXT",
            "last_used_at": "DATETIME",
        }
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE assets ADD COLUMN {col_name} {col_type}")
                    logger.info(f"✅ 新增字段: assets.{col_name}")
                except Exception as e:
                    logger.warning(f"⚠️ 添加字段 {col_name} 失败: {e}")

    def _create_dm_tasks_table(self, cursor):
        """创建评论私信任务表（V2.2）"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dm_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER UNIQUE,
                status TEXT DEFAULT 'pending',
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                handled_at DATETIME
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dm_tasks_status ON dm_tasks(status)")
        logger.info("✅ dm_tasks 表已创建/检查")

    def rollback_to_v1(self, conn):
        """回滚到 V1.0 结构（仅用于测试/紧急情况）"""
        cursor = conn.cursor()
        logger.warning("⚠️ 执行回滚操作...")
        
        cursor.execute("DROP TABLE IF EXISTS accounts")
        cursor.execute("DROP TABLE IF EXISTS profit_config")
        
        conn.commit()
        logger.info("✅ 已回滚到 V1.0 数据库结构")


# 便捷调用函数
def ensure_v2_database():
    """
    在应用启动时调用，确保数据库已升级到 V2.0
    """
    manager = MigrationManager()
    manager.run_migrations()


if __name__ == "__main__":
    # 测试迁移
    logging.basicConfig(level=logging.INFO)
    ensure_v2_database()

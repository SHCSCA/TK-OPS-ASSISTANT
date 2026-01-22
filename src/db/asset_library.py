"""
素材库 SQLite：存储下载/处理的视频、图片、文件元数据
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import config
from db.core import SessionLocal, engine, Base
from db.models import Asset, ProcessingLog
from sqlalchemy import func
import datetime

logger = logging.getLogger(__name__)


class AssetLibrary:
    """素材库管理（SQLAlchemy ORM）"""
    
    def __init__(self, db_path: str = None):
        # db_path logic is handled by db.core mostly, but we keep the structure 
        # to not break existing calls. However, SessionLocal uses fixed path from config.
        # If db_path is provided differently, proper ORM usage would req recreating engine, 
        # but for this app sticking to single global DB is fine.
        if db_path is None:
            self.db_path = config.ASSET_LIBRARY_DIR / "assets.db"
        else:
            self.db_path = Path(db_path)
        
        self.init_db()
    
    def init_db(self):
        """初始化数据库表 (ORM)"""
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.error(f"Init DB failed: {e}")
    
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
        """添加素材到库 (ORM)"""
        session = SessionLocal()
        try:
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size if file_path_obj.exists() else 0
            
            # Check existing to preserve last_used_at logic if needed
            asset = session.query(Asset).filter_by(asset_id=asset_id).first()
            
            tags_json = json.dumps(tags or [])
            meta_json = json.dumps(metadata or {})
            
            if asset:
                asset.type = file_type
                asset.title = title or file_path_obj.stem
                asset.file_path = str(file_path_obj)
                asset.file_size = file_size
                asset.source_url = source_url
                asset.source_type = source_type
                asset.tags = tags_json
                asset.metadata_json = meta_json
                asset.type_tag = (type_tag or "").strip()
                asset.emotion_tag = (emotion_tag or "").strip()
                asset.object_tag = (object_tag or "").strip()
            else:
                asset = Asset(
                    asset_id=asset_id,
                    type=file_type,
                    title=title or file_path_obj.stem,
                    file_path=str(file_path_obj),
                    file_size=file_size,
                    source_url=source_url,
                    source_type=source_type,
                    tags=tags_json,
                    metadata_json=meta_json,
                    type_tag=(type_tag or "").strip(),
                    emotion_tag=(emotion_tag or "").strip(),
                    object_tag=(object_tag or "").strip(),
                    last_used_at=datetime.datetime.now()
                )
                session.add(asset)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"添加素材失败: {e}")
            return False
        finally:
            session.close()

    def select_asset_by_tags(self, type_tag: str, emotion_tag: str, object_tag: str) -> Optional[Dict[str, Any]]:
        """按标签选择最少使用的素材（避免重复）。(ORM)"""
        session = SessionLocal()
        try:
            asset = session.query(Asset).filter(
                Asset.status == 'active',
                Asset.type_tag == (type_tag or "").strip(),
                Asset.emotion_tag == (emotion_tag or "").strip(),
                Asset.object_tag == (object_tag or "").strip()
            ).order_by(Asset.last_used_at.asc()).first()
            
            if not asset:
                return None
            
            d = {
                "id": asset.id,
                "asset_id": asset.asset_id,
                "type": asset.type,
                "title": asset.title,
                "file_path": asset.file_path,
                "file_size": asset.file_size,
                "duration": asset.duration,
                "source_url": asset.source_url,
                "source_type": asset.source_type,
                "tags": json.loads(asset.tags or "[]"),
                "metadata": json.loads(asset.metadata_json or "{}"),
                "type_tag": asset.type_tag,
                "emotion_tag": asset.emotion_tag,
                "object_tag": asset.object_tag,
                "status": asset.status,
                "last_used_at": asset.last_used_at
            }

            # Update usage time
            asset.last_used_at = datetime.datetime.now()
            session.commit()
            return d
        except Exception as e:
            session.rollback()
            logger.error(f"按标签选取素材失败: {e}")
            return None
        finally:
            session.close()
    
    def log_processing(self,
                      asset_id: str,
                      process_type: str,
                      input_path: str,
                      output_path: str,
                      params: Dict[str, Any],
                      success: bool,
                      error_msg: str = "",
                      elapsed_seconds: float = 0) -> bool:
        """记录处理日志 (ORM)"""
        session = SessionLocal()
        try:
            log = ProcessingLog(
                asset_id=asset_id,
                process_type=process_type,
                input_path=input_path,
                output_path=output_path,
                params=json.dumps(params or {}),
                status="success" if success else "failed",
                error_msg=error_msg,
                elapsed_seconds=elapsed_seconds,
                created_at=datetime.datetime.now()
            )
            session.add(log)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"记录处理日志失败: {e}")
            return False
        finally:
            session.close()
    
    def search_assets(self,
                     file_type: str = None,
                     status: str = "active",
                     tags: List[str] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """查询素材 (ORM)"""
        session = SessionLocal()
        try:
            query = session.query(Asset).filter(Asset.status == status)

            if file_type:
                query = query.filter(Asset.type == file_type)

            assets = query.order_by(Asset.created_at.desc()).limit(limit).all()

            results = []
            for asset in assets:
                d = {
                    "id": asset.id,
                    "asset_id": asset.asset_id,
                    "type": asset.type,
                    "title": asset.title,
                    "file_path": asset.file_path,
                    "file_size": asset.file_size,
                    "duration": asset.duration,
                    "source_url": asset.source_url,
                    "source_type": asset.source_type,
                    "tags": json.loads(asset.tags or "[]"),
                    "metadata": json.loads(asset.metadata_json or "{}"),
                    "type_tag": asset.type_tag,
                    "emotion_tag": asset.emotion_tag,
                    "object_tag": asset.object_tag,
                    "status": asset.status,
                    "last_used_at": asset.last_used_at,
                    "created_at": asset.created_at
                }
                results.append(d)

            return results
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []
        finally:
            session.close()
    
    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """获取单个素材 (ORM)"""
        session = SessionLocal()
        try:
            asset = session.query(Asset).filter(Asset.asset_id == asset_id).first()
            if asset:
                d = {
                    "id": asset.id,
                    "asset_id": asset.asset_id,
                    "type": asset.type,
                    "title": asset.title,
                    "file_path": asset.file_path,
                    "file_size": asset.file_size,
                    "duration": asset.duration,
                    "source_url": asset.source_url,
                    "source_type": asset.source_type,
                    "tags": json.loads(asset.tags or "[]"),
                    "metadata": json.loads(asset.metadata_json or "{}"),
                    "type_tag": asset.type_tag,
                    "emotion_tag": asset.emotion_tag,
                    "object_tag": asset.object_tag,
                    "status": asset.status,
                    "last_used_at": asset.last_used_at
                }
                return d
            return None
        except Exception:
            return None
        finally:
            session.close()
    
    def get_processing_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """获取素材的处理历史 (ORM)"""
        session = SessionLocal()
        try:
            logs = session.query(ProcessingLog).filter(ProcessingLog.asset_id == asset_id).order_by(ProcessingLog.created_at.desc()).all()
            
            results = []
            for log in logs:
                d = {
                    "id": log.id,
                    "asset_id": log.asset_id,
                    "process_type": log.process_type,
                    "input_path": log.input_path,
                    "output_path": log.output_path,
                    "params": json.loads(log.params or "{}"),
                    "status": log.status,
                    "error_msg": log.error_msg,
                    "elapsed_seconds": log.elapsed_seconds,
                    "created_at": log.created_at
                }
                results.append(d)
            return results
        except Exception:
            return []
        finally:
            session.close()
    
    def delete_asset(self, asset_id: str) -> bool:
        """标记素材为已删除（逻辑删除） (ORM)"""
        session = SessionLocal()
        try:
            asset = session.query(Asset).filter(Asset.asset_id == asset_id).first()
            if asset:
                asset.status = 'deleted'
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    
    def statistics(self) -> Dict[str, Any]:
        """获取库统计信息 (ORM)"""
        session = SessionLocal()
        try:
            total = session.query(Asset).filter(Asset.status == 'active').count()
            
            # Group by type
            by_type_q = session.query(Asset.type, func.count(Asset.id)).filter(Asset.status == 'active').group_by(Asset.type).all()
            by_type = {r[0]: r[1] for r in by_type_q}
            
            # Sum size
            total_size_res = session.query(func.sum(Asset.file_size)).filter(Asset.status == 'active').scalar()
            total_size = total_size_res if total_size_res else 0
            
            # Successful ops
            success_ops = session.query(ProcessingLog).filter(ProcessingLog.status == 'success').count()

            return {
                'total_assets': total,
                'by_type': by_type,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'successful_operations': success_ops,
            }
        except Exception:
            return {}
        finally:
            session.close()

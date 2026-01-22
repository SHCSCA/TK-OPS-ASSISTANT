from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from db.core import Base
import datetime

class Asset(Base):
    """
    素材库主表
    Stores metadata for videos, images, and documents.
    """
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False, index=True) # video / image / document
    title = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True) # bytes
    duration = Column(Float, nullable=True) # seconds
    source_url = Column(String, nullable=True)
    source_type = Column(String, nullable=True) # download / blue_ocean / user_upload
    tags = Column(String, nullable=True) # JSON list string
    metadata_json = Column("metadata", Text, nullable=True) # JSON object string
    
    # New tags (V2.2)
    type_tag = Column(String, nullable=True)
    emotion_tag = Column(String, nullable=True)
    object_tag = Column(String, nullable=True)
    
    status = Column(String, default="active", index=True) # active / archived / deleted
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Account(Base):
    """
    账号矩阵表 (CRM)
    Stores TikTok account credentials and status.
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    status = Column(String, default="active") # active, shadowban, suspended
    proxy_ip = Column(String, nullable=True)
    last_post_date = Column(DateTime, nullable=True)
    today_post_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)


class ProfitConfig(Base):
    """
    利润核算配置表
    Key-Value store for global profit settings.
    """
    __tablename__ = "profit_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)


class ProductHistory(Base):
    """
    选品清洗池/产品历史表
    """
    __tablename__ = "product_history"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    tk_price = Column(Float, default=0.0)
    sales_count = Column(Integer, default=0)
    cny_cost = Column(Float, default=0.0)
    weight = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    source_file = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)


class Comment(Base):
    """
    评论区监控表 (Engagement)
    """
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, nullable=True)
    comment_id = Column(String, nullable=True)
    author = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    sentiment_score = Column(Float, default=0.0)
    lead_tier = Column(Integer, default=3, index=True)
    is_replied = Column(Integer, default=0) # 0 or 1
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)


class DMTask(Base):
    """
    私信任务表 (Engagement)
    """
    __tablename__ = "dm_tasks"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, unique=True)
    status = Column(String, default="pending", index=True) # pending, sent, failed
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    handled_at = Column(DateTime, nullable=True)

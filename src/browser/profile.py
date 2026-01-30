from dataclasses import dataclass, field
from typing import Optional, Dict
import random
import uuid

@dataclass
class BrowserProfile:
    """账户指纹配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Default Profile"
    
    # 指纹参数
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    viewport_width: int = 1280
    viewport_height: int = 720
    timezone_id: str = "Asia/Shanghai"
    locale: str = "zh-CN"
    
    # 隔离存储
    user_data_dir_name: str = "" # 如果为空，自动基于 id 生成

    def __post_init__(self):
        if not self.user_data_dir_name:
            self.user_data_dir_name = f"profile_{self.id}"

    @property
    def viewport(self) -> Dict[str, int]:
        return {"width": self.viewport_width, "height": self.viewport_height}

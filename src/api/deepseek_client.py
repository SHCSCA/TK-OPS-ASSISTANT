"""
DeepSeek AI 客户端 (V3.0 Intelligence)
用于选品分析、文案优化、评论情感分析
"""
from typing import Optional, Dict, Any
import logging
from openai import OpenAI
import config

logger = logging.getLogger(__name__)

class DeepSeekClient:
    """DeepSeek API 封装"""
    
    def __init__(self):
        # 优先读取 DeepSeek 专用配置，其次回退到全局 AI 配置
        self.api_key = (
            getattr(config, "AI_DEEPSEEK_API_KEY", "")
            or getattr(config, "AI_API_KEY", "")
            or ""
        ).strip()
        self.base_url = (
            getattr(config, "AI_DEEPSEEK_BASE_URL", "")
            or getattr(config, "AI_BASE_URL", "")
            or "https://api.deepseek.com"
        ).strip()

        # 模型优先级：DeepSeek 专用模型 > 全局模型 > 默认 deepseek-chat
        self.model = (
            getattr(config, "AI_DEEPSEEK_MODEL", "")
            or getattr(config, "AI_MODEL", "")
            or "deepseek-chat"
        ).strip()
        
        self.client: Optional[OpenAI] = None
        self._fingerprint = f"{self.api_key}|{self.base_url}|{self.model}"
        if self.api_key:
            try:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except Exception as e:
                logger.error(f"DeepSeek 客户端初始化失败: {e}")

    def is_configured(self) -> bool:
        return bool(self.client and self.api_key)

    def analyze_product_potential(self, product_title: str, price: float, sales: int, role_prompt: str = "") -> str:
        """分析单一商品的市场潜力。

        Args:
            product_title: 商品标题
            price: 售价
            sales: 销量
            role_prompt: 角色提示词（可选，优先于配置）
        """
        if not self.is_configured():
            return "错误: 未配置 DeepSeek API Key，请在系统设置中填写。"

        prompt = f"""
        请以此身份分析商品：跨境电商选品专家。
        
        商品信息：
        - 标题: {product_title}
        - 售价: ${price}
        - 销量: {sales}
        
        请简练回答以下3点（200字以内）：
        1. 市场潜力评分 (0-10分)
        2. 目标受众画像
        3. 建议的短视频营销痛点
        """
        
        # 角色提示词（优先使用传入，其次使用选品参谋已保存配置）
        extra_role = (
            (role_prompt or "").strip()
            or (getattr(config, "AI_PROFIT_ROLE_PROMPT", "") or "").strip()
            or (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
        )

        system_prompt = "You are a helpful assistant for TikTok shop operations."
        if extra_role:
            system_prompt += "\n[ROLE_PROMPT]\n" + extra_role

        return self._chat_completion(prompt, system_prompt=system_prompt)

    def optimize_dm_script(self, original_script: str, user_intent: str) -> str:
        """优化私信话术"""
        if not self.is_configured():
            return original_script

        prompt = f"""
        用户意图: {user_intent}
        原始话术: {original_script}
        
        任务：请将上述话术修改得更具亲和力、更像真人（非机器人），并包含明确的行动号召(CTA)。
        """
        return self._chat_completion(prompt)

    def _chat_completion(self, user_prompt: str, system_prompt: str | None = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt or "You are a helpful assistant for TikTok shop operations."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"DeepSeek API 调用出错: {e}")
            return f"AI 分析暂时不可用: {str(e)}"

# 单例
_global_deepseek = None

def get_deepseek_client() -> DeepSeekClient:
    global _global_deepseek
    current = DeepSeekClient()
    if _global_deepseek is None:
        _global_deepseek = current
        return _global_deepseek
    try:
        if getattr(_global_deepseek, "_fingerprint", "") != getattr(current, "_fingerprint", ""):
            _global_deepseek = current
    except Exception:
        _global_deepseek = current
    return _global_deepseek

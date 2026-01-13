"""
AI 模板系统：提示词管理、变量替换、Provider 统一
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import config


@dataclass
class Template:
    """AI 模板"""
    name: str
    prompt: str
    variables: List[str]      # 模板变量列表
    category: str = "general" # 标题 / 脚本 / 标签 / 评论
    description: str = ""
    

class AITemplateManager:
    """AI 模板管理器"""
    
    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            templates_dir = str(config.SRC_DIR / "ai" / "templates")
        
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.templates: Dict[str, Template] = {}
        
        self._load_builtin_templates()
        self._load_user_templates()
    
    def _load_builtin_templates(self):
        """加载内置模板"""
        builtin = {
            "tiktok_title": Template(
                name="TikTok 标题生成",
                category="标题",
                prompt="为下列产品生成 3 个吸人眼球的 TikTok 视频标题（20 字以内），英文，可包含 emoji：\n\n产品名：{product_name}\n特点：{features}\n目标人群：{target_audience}",
                variables=["product_name", "features", "target_audience"],
                description="生成 TikTok Shop 视频标题"
            ),
            "tiktok_script": Template(
                name="TikTok 脚本生成",
                category="脚本",
                prompt="为下列产品编写 30 秒 TikTok 视频脚本（英文），开头要吸引注意力，结尾要鼓励关注和购买：\n\n产品：{product_name}\n卖点：{selling_point}\n风格：{style}",
                variables=["product_name", "selling_point", "style"],
                description="生成视频脚本/文案"
            ),
            "product_tags": Template(
                name="产品标签生成",
                category="标签",
                prompt="为下列 TikTok Shop 产品生成 10 个搜索标签和分类标签（英文，#开头）：\n\n产品：{product_name}\n描述：{description}",
                variables=["product_name", "description"],
                description="生成 TikTok 标签"
            ),
            "comment_reply": Template(
                name="评论回复建议",
                category="评论",
                prompt="为用户的如下评论生成 3 个专业而友好的回复（英文，体现品牌声音）：\n\n用户评论：{comment}\n产品背景：{product_context}",
                variables=["comment", "product_context"],
                description="自动化评论互动"
            ),
        }
        
        for key, template in builtin.items():
            self.templates[key] = template
    
    def _load_user_templates(self):
        """从用户文件夹加载自定义模板"""
        try:
            for json_file in self.templates_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        template = Template(**data)
                        self.templates[json_file.stem] = template
                except Exception:
                    pass
        except Exception:
            pass
    
    def get_template(self, template_id: str) -> Optional[Template]:
        """获取模板"""
        return self.templates.get(template_id)
    
    def list_templates(self, category: str = None) -> List[Template]:
        """列出模板"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates
    
    def save_template(self, template_id: str, template: Template) -> bool:
        """保存用户自定义模板"""
        try:
            self.templates[template_id] = template
            
            json_path = self.templates_dir / f"{template_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(template), f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def render_template(self, template_id: str, variables: Dict[str, str]) -> Optional[str]:
        """使用变量渲染模板提示词"""
        template = self.templates.get(template_id)
        if not template:
            return None
        
        try:
            prompt = template.prompt
            for var in template.variables:
                prompt = prompt.replace(f"{{{var}}}", variables.get(var, ""))
            return prompt
        except Exception:
            return None


class AIProvider:
    """统一 AI Provider 接口（支持 OpenAI / DeepSeek / 兼容服务）"""
    
    def __init__(self, provider: str = None, api_key: str = None, base_url: str = None, model: str = None):
        self.provider = provider or getattr(config, "AI_PROVIDER", "openai")
        self.api_key = api_key or getattr(config, "AI_API_KEY", "")
        self.base_url = base_url or getattr(config, "AI_BASE_URL", "")
        self.model = model or getattr(config, "AI_MODEL", "gpt-4o-mini")
    
    async def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> Optional[str]:
        """调用 AI 生成文本"""
        try:
            if self.provider == "openai" or self.provider.startswith("compatible"):
                # 兼容 OpenAI Chat Completions API
                from openai import AsyncOpenAI, OpenAI
                
                client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url if self.base_url else None
                )
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一位 TikTok 商务内容专家和创意文案编辑。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                return response.choices[0].message.content
            else:
                return None
        except Exception as e:
            print(f"AI 生成失败 ({self.provider}): {e}")
            return None
    
    def generate_text_sync(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> Optional[str]:
        """同步调用 AI 生成文本（UI 友好）"""
        try:
            if not self.api_key:
                return "❌ 未配置 AI_API_KEY，请在系统设置填入。"
            
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url if self.base_url else None
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位 TikTok 商务内容专家和创意文案编辑。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ AI 生成失败：{str(e)}"

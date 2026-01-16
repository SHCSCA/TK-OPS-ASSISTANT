"""AI 文案助手 Worker（QThread）"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal

from workers.base_worker import BaseWorker
from api.ai_assistant import generate_tiktok_copy


class AICopyWorker(BaseWorker):
    """生成标题/标签的后台线程"""

    result_signal = pyqtSignal(dict)

    def __init__(self, desc_cn: str, tone: str, role_prompt: str = "", model: str = ""):
        super().__init__()
        self.desc_cn = desc_cn
        self.tone = tone
        self.role_prompt = role_prompt
        self.model = model

    def _run_impl(self):
        self.emit_log("开始生成 AI 文案...")
        # 明确告知本次会使用哪一份角色提示词（便于用户验证“是否真的传给模型”）
        try:
            effective_role = ""
            ui_role = (self.role_prompt or "").strip()
            if ui_role:
                effective_role = ui_role
                preview = ui_role.replace("\n", " ")[:60]
                self.emit_log(f"角色提示词：使用【面板输入/预设】({len(ui_role)} 字) - {preview}...")
            else:
                panel_saved = (getattr(__import__("config"), "AI_COPYWRITER_ROLE_PROMPT", "") or "").strip()
                if panel_saved:
                    effective_role = panel_saved
                    preview = panel_saved.replace("\n", " ")[:60]
                    self.emit_log(f"角色提示词：使用【文案助手面板已保存】({len(panel_saved)} 字) - {preview}...")
                else:
                    system_saved = (getattr(__import__("config"), "AI_SYSTEM_PROMPT", "") or "").strip()
                    if system_saved:
                        effective_role = system_saved
                        preview = system_saved.replace("\n", " ")[:60]
                        self.emit_log(f"角色提示词：使用【系统设置】({len(system_saved)} 字) - {preview}...")
                    else:
                        self.emit_log("角色提示词：未配置（仅使用内置默认角色约束）")

            # 结构冲突提醒：文案助手固定输出 titles/hashtags/notes。
            # 如果用户的提示词里写了 hook_text/body_text/full_script 等“脚本 JSON 字段”，会造成观感上的“没生效”。
            try:
                t = (effective_role or "")
                if t and any(k in t for k in ("hook_text", "body_text", "cta_text", "full_script", "visual_cues", "suggested_bgm_mood")):
                    self.emit_log(
                        "⚠️ 检测到你的角色提示词包含‘口播脚本 JSON 字段’(如 hook_text/body_text)。"
                        "但【AI 爆款文案助手】固定输出 titles/hashtags/notes，提示词中的输出结构要求将不会被采纳。"
                        "建议：把提示词改成‘风格/约束’而不要改字段结构，或使用【AI 二创工厂】生成口播脚本。"
                    )
            except Exception:
                pass
        except Exception:
            pass
        self.emit_progress(10)

        result = generate_tiktok_copy(self.desc_cn, self.tone, role_prompt=self.role_prompt, model=self.model)

        self.emit_progress(90)
        try:
            self.result_signal.emit(result)
        except Exception:
            pass
        try:
            self.data_signal.emit(result)
        except Exception:
            pass
        self.emit_log("✓ AI 文案生成完成")
        self.emit_progress(100)
        self.emit_finished(True, "AI 文案生成完成")

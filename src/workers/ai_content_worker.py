"""
AI 智能二创 Worker (V2.0)
集成 DeepSeek 脚本生成 + Edge-TTS 语音合成 + MoviePy 音画混合
"""
from PyQt5.QtCore import QThread, pyqtSignal
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import config

from tts import synthesize as tts_synthesize
from tts.types import TtsError, TtsForbiddenError
from video.processor import VideoProcessor

logger = logging.getLogger(__name__)

class AIContentWorker(QThread):
    """
    AI 二创全流程 Worker
    输入: 商品描述文本 + 原始视频路径
    输出: 带AI解说的新视频
    """
    progress = pyqtSignal(int, str)  # percentage, message
    finished = pyqtSignal(str, str)  # output_path, error_msg
    
    def __init__(
        self,
        product_desc,
        video_path,
        output_dir="Output/AI_Videos",
        skip_tts_failure: bool = True,
        role_prompt: str = "",
        model: str = "",
        provider: str = "",
        script_text: str = "",
        script_json: dict | None = None,
    ):
        super().__init__()
        self.product_desc = product_desc
        self.video_path = video_path
        self.output_dir = output_dir
        self.skip_tts_failure = skip_tts_failure
        self.role_prompt = role_prompt
        self.model = model
        self.provider = (provider or "").strip()
        self.script_text = (script_text or "").strip()
        self.script_json = script_json or {}
        self._last_script_error: str = ""
        self._base_output_dir = str(output_dir)
        self._video_stem_raw = Path(video_path).stem
        self._video_stem_safe = self._safe_name(self._video_stem_raw) or "video"
        self._job_dir = self._prepare_job_dir(Path(output_dir), self._video_stem_safe)
        self.output_dir = str(self._job_dir)
        self._job_dir.mkdir(parents=True, exist_ok=True)

        # 统一的中文产物命名（每个视频单独文件夹内，文件名固定即可）
        self._name_script = "脚本.txt"
        self._name_voice = "配音.mp3"
        self._name_voice_timeline = "配音_时间轴.mp3"
        self._name_captions = "字幕.srt"
        self._name_remix = "成片.mp4"
        self._name_remix_sub = "成片_带字幕.mp4"

    def run(self):
        try:
            try:
                self.progress.emit(2, f"📁 输出目录：{self.output_dir}")
            except Exception:
                pass

            # 先输出“本次角色提示词来源”，便于排查是否真的传入/生效
            try:
                ui_role = (self.role_prompt or "").strip()
                if ui_role:
                    preview = ui_role.replace("\n", " ")[:60]
                    self.progress.emit(1, f"🧩 角色提示词：使用【面板输入/预设】({len(ui_role)} 字) - {preview}...")
                else:
                    panel_saved = (getattr(config, "AI_FACTORY_ROLE_PROMPT", "") or "").strip()
                    if panel_saved:
                        preview = panel_saved.replace("\n", " ")[:60]
                        self.progress.emit(1, f"🧩 角色提示词：使用【二创工厂面板已保存】({len(panel_saved)} 字) - {preview}...")
                    else:
                        system_saved = (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
                        if system_saved:
                            preview = system_saved.replace("\n", " ")[:60]
                            self.progress.emit(1, f"🧩 角色提示词：使用【系统设置】({len(system_saved)} 字) - {preview}...")
                        else:
                            self.progress.emit(1, "🧩 角色提示词：未配置（仅使用内置默认角色）")
            except Exception:
                pass

            # Step 1: 获取脚本（两步式：优先使用外部注入的已通过脚本）
            script = ""
            if self.script_text:
                self.progress.emit(10, "📝 使用已通过校验的脚本，跳过脚本生成")
                script = self.script_text
            else:
                self.progress.emit(10, "🤖 AI 正在生成脚本...")
                script = self.generate_script()
            
            if not script:
                reason = (self._last_script_error or "").strip()
                hint = "脚本生成失败，请检查二创 AI 配置（Base URL / API Key / Model）。"
                if reason:
                    hint = hint + f"\n原因：{reason}"
                self.finished.emit("", hint)
                return
            
            # 永远落盘脚本（即使后续 TTS 失败，也给到可交付物）
            script_path = self._save_script(script)
            if script_path:
                self.progress.emit(25, f"📝 脚本已保存：{script_path}")

            # Step 2: 语音合成 (Edge-TTS)
            timeline = self._extract_timeline(self.script_json)
            if timeline:
                self.progress.emit(40, "🎙️ 正在合成语音（时间轴模式）...")
                audio_path, tts_error = self.synthesize_timeline_voice(timeline)
            else:
                self.progress.emit(40, "🎙️ 正在合成语音...")
                audio_path, tts_error = self.synthesize_voice(script)

            if not audio_path:
                if self.skip_tts_failure:
                    self.progress.emit(55, f"⚠️ 配音失败，已降级：输出脚本 + 复制原视频（原因：{tts_error}）")
                    fallback_video = self._copy_original_video(script_path=script_path)
                    if fallback_video:
                        self.progress.emit(100, "✅ 已输出降级结果")
                        self.finished.emit(fallback_video, "")
                        return
                self.finished.emit("", f"语音合成失败：{tts_error}")
                return

            # Step 2.5: 生成字幕（可选但默认启用）
            subtitle_srt = ""
            try:
                self.progress.emit(60, "📝 正在生成字幕...")
                if timeline:
                    subtitle_srt = self._save_subtitles_with_timeline(timeline)
                else:
                    subtitle_srt = self._save_subtitles(script_text=script, audio_path=audio_path)
                if subtitle_srt:
                    self.progress.emit(65, f"📝 字幕已生成：{subtitle_srt}")
                else:
                    self.progress.emit(65, "⚠️ 字幕生成失败（将继续输出无字幕视频）")
            except Exception:
                subtitle_srt = ""
            
            # Step 3: 音画合成 (MoviePy)
            self.progress.emit(70, "🎬 正在混合音视频...")
            final_video = self.mix_audio_video(audio_path, subtitle_srt_path=subtitle_srt)
            
            if not final_video:
                self.finished.emit("", "视频合成失败")
                return
            
            self.progress.emit(100, "✅ AI 二创完成")
            self.finished.emit(final_video, "")
            
        except Exception as e:
            logger.error(f"AI 二创失败: {e}", exc_info=True)
            self.finished.emit("", f"处理失败: {str(e)}")

    def generate_script(self):
        """调用 DeepSeek API 生成脚本"""
        try:
            import openai

            self._last_script_error = ""

            from utils.ai_routing import resolve_ai_profile

            profile = resolve_ai_profile("factory", model_override=self.model, provider_override=self.provider)
            api_key = (profile.get("api_key", "") or "").strip()
            if not api_key:
                logger.warning("AI_API_KEY 未配置")
                return None
            
            # 配置 OpenAI 兼容客户端
            client = openai.OpenAI(
                api_key=api_key,
                base_url=(profile.get("base_url", "") or "").strip() or "https://api.deepseek.com",
            )

            # 火山方舟（Ark）深度思考：仅当用户显式配置且 base_url 为 Ark 时透传。
            base_url_now = ""
            try:
                base_url_now = (profile.get("base_url", "") or "").strip()
            except Exception:
                base_url_now = ""

            ark_thinking_type = (getattr(config, "ARK_THINKING_TYPE", "") or "").strip()
            ark_extra = None
            if base_url_now and ark_thinking_type:
                u = base_url_now.lower()
                if ("volces.com" in u) or ("volcengine.com" in u) or ("ark." in u):
                    ark_extra = {"thinking": {"type": ark_thinking_type}}
            
            system = (
                "You are a TikTok script writer. Keep output concise and natural. "
                "Follow role/style constraints if provided."
            )
            extra_role = (
                (self.role_prompt or "").strip()
                or (getattr(config, "AI_FACTORY_ROLE_PROMPT", "") or "").strip()
                or (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
            )
            
            is_free_mode = bool(self.role_prompt and self.role_prompt.strip())
            
            if extra_role:
                system = system + "\n[ROLE_PROMPT]\n" + extra_role

            if is_free_mode:
                # 自由模式：完全听从 Role Prompt，仅保留最基础要求
                prompt = f"""
Context / Product: {self.product_desc}

Requirement: Write a short video script based on the ROLE_PROMPT above.
Output ONLY the script text, no markdown.
""".strip()
            else:
                # 默认模式：保持旧有结构
                prompt = f"""
Create a 30-second product pitch script for:

Product: {self.product_desc}

Requirements:
- Start with a Hook (3 seconds)
- Present Pain Points (10 seconds)
- Show Solution (15 seconds)
- End with Call to Action (2 seconds)
- Use casual, conversational American English
- Keep it under 100 words

Output ONLY the script text, no formatting.
""".strip()

            use_model = (profile.get("model", "") or "").strip() or "deepseek-chat"

            # --- Model Capability Validation ---
            _model_lower = use_model.lower()
            if any(k in _model_lower for k in ("seedance", "t2v", "i2v", "wan2.1", "wan2-1")):
                self.emit_log(f"⚠️ 错误：检测到视频生成模型 '{use_model}'")
                self.emit_log("❌ 二创工厂的脚本生成环节需要文本模型，不能使用视频模型！")
                return None

            # Auto-correction for DeepSeek official API
            if "deepseek.com" in (base_url_now or ""):
                if use_model not in ("deepseek-chat", "deepseek-reasoner"):
                    if "r1" in use_model.lower():
                        use_model = "deepseek-reasoner"
                    else:
                        use_model = "deepseek-chat"

            # Ark（火山方舟）官方示例优先使用 Responses API
            if base_url_now and "volces.com" in base_url_now and hasattr(client, "responses"):
                resp = client.responses.create(
                    model=use_model,
                    input=prompt,
                    instructions=system,
                )
                text = ""
                try:
                    text = (getattr(resp, "output_text", "") or "").strip()
                    # 尝试获取 usage (responses API 可能结构不同，需查阅文档，这里暂忽略或尝试通用字段)
                except Exception:
                    text = ""
                if text:
                    return text
                # 兜底：即使解析不到文本，也不当作失败
                return ""

            # chat.completions：如为 Ark 且配置了 thinking，则尝试透传；不支持则自动降级。
            try:
                kwargs = {
                    "model": use_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4096, # Increased for reasoning models
                    "temperature": 0.5,
                }
                if ark_extra:
                    kwargs["extra_body"] = ark_extra
                    
                response = client.chat.completions.create(**kwargs)

                # 检查截断
                try:
                    if response.choices[0].finish_reason == "length":
                         self.emit_log("⚠️ 警告：输出因达到最大长度限制而被截断 (Max Tokens)")
                except Exception:
                    pass
                
                # Token 统计
                try:
                    if response and response.usage:
                        u = response.usage
                        token_msg = f"💰 Token 消耗: Prompt={u.prompt_tokens}, Completion={u.completion_tokens}, Total={u.total_tokens}"
                        logger.info(token_msg)
                        # 通过 progress 信号传回 UI 日志 (保持进度条不动)
                        self.progress.emit(15, token_msg)
                except Exception:
                    pass
                    
                return (response.choices[0].message.content or "").strip()
            except TypeError:
                 # Legacy fallback
                 try:
                    # 降级尝试：不带 extra_body
                    if "extra_body" in kwargs:
                        del kwargs["extra_body"]
                    response = client.chat.completions.create(**kwargs)
                    return (response.choices[0].message.content or "").strip()
                 except Exception:
                     pass

            except Exception as e:
                logger.error(f"Generate script error: {e}")
                return ""
        except Exception as e:
            logger.error(f"脚本生成调用失败: {e}", exc_info=True)
            self._last_script_error = str(e)
            return None

    def synthesize_voice(self, text):
        """合成语音（支持 volcengine/edge-tts + fallback）。"""
        audio_path = Path(self.output_dir) / self._name_voice
        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()
        emotion_instruction = self._build_emotion_instruction("neutral")

        def _try(p: str) -> None:
            tts_synthesize(text=text, out_path=audio_path, provider=p, emotion=emotion_instruction)

        try:
            _try(provider)
            if audio_path.exists():
                return str(audio_path), ""
            return None, "语音文件未生成"
        except (TtsForbiddenError, TtsError) as e:
            # 403/风控 等：优先尝试备用 provider
            if fallback:
                try:
                    self.progress.emit(55, f"⚠️ 配音失败，尝试备用 TTS：{fallback} ...")
                    _try(fallback)
                    if audio_path.exists():
                        return str(audio_path), ""
                except Exception as e2:
                    logger.error(f"备用 TTS 也失败: {e2}")
                    return None, f"{e}；备用失败：{e2}"
            logger.error(f"TTS 合成失败: {e}")
            return None, str(e)
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            return None, str(e)

    def _build_emotion_instruction(self, base_emotion: str) -> str:
        """构建豆包 TTS 2.0 情绪指令文本。"""
        preset = (getattr(config, "TTS_EMOTION_PRESET", "") or "").strip()
        custom = (getattr(config, "TTS_EMOTION_CUSTOM", "") or "").strip()
        intensity = (getattr(config, "TTS_EMOTION_INTENSITY", "中") or "中").strip()
        scene_mode = (getattr(config, "TTS_SCENE_MODE", "") or "").strip().lower()

        scene_templates = {
            "commerce": "用强转化、强节奏、强调卖点的带货语气说",
            "review": "用客观、冷静、对比分析的测评语气说",
            "unboxing": "用真实、兴奋、细节描述的开箱语气说",
            "story": "用剧情对白的语气说，带有情绪起伏",
            "talk": "用清晰、稳定、讲解导向的口播语气说",
        }

        emotion = (base_emotion or "").strip().lower()
        emotion_map = {
            "happy": "开心",
            "sad": "悲伤",
            "angry": "生气",
            "surprise": "惊讶",
            "neutral": "平静",
            "excited": "兴奋",
            "calm": "沉稳",
            "serious": "严肃",
            "curious": "好奇",
            "persuasive": "劝导",
            "suspense": "悬念",
            "warm": "温柔",
            "firm": "坚定",
            "energetic": "有活力",
        }

        parts = []
        scene_hint = scene_templates.get(scene_mode, "")
        if scene_hint:
            parts.append(scene_hint)
        if preset:
            parts.append(preset)
        if custom:
            parts.append(custom)

        if emotion and emotion != "neutral":
            emotion_cn = emotion_map.get(emotion, emotion)
            parts.append(f"情绪偏{emotion_cn}，强度{intensity}")
        elif parts:
            parts.append(f"情绪强度{intensity}")
        else:
            return ""

        return "，".join([p for p in parts if p])

    def synthesize_timeline_voice(self, timeline: list[dict]) -> tuple[str, str]:
        """根据时间轴逐段合成语音，并做弹性对齐 (FFmpeg版)。"""
        audio_path = Path(self.output_dir) / self._name_voice_timeline
        processor = VideoProcessor()

        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()
        
        clips_to_concat = [] 
        current_time = 0.0
        
        # Helper for TTS generation
        def _gen_tts(txt, emo, out):
            try:
                tts_synthesize(text=txt, out_path=out, provider=provider, emotion=emo)
                return True
            except Exception:
                if fallback:
                    try:
                        tts_synthesize(text=txt, out_path=out, provider=fallback, emotion=emo)
                        return True
                    except: pass
            return False

        try:
            for i, seg in enumerate(timeline):
                if not isinstance(seg, dict): continue
                try:
                    start = float(seg.get("start", 0))
                    end = float(seg.get("end", 0))
                except Exception: continue
                
                text = (seg.get("text", "") or "").strip()
                emotion = (seg.get("emotion", "neutral") or "neutral").strip().lower()
                emotion_instruction = self._build_emotion_instruction(emotion)
                if not text or end <= start: continue

                # 1. Handle Gap (Silence)
                if start > current_time:
                    gap = start - current_time
                    if gap > 0.05:
                        silence_path = Path(self.output_dir) / f"silence_{i}_{int(gap*1000)}.mp3"
                        if processor.generate_silence(gap, str(silence_path)):
                            clips_to_concat.append(str(silence_path))
                    current_time = start # Align to start

                # 2. Generate TTS
                seg_out = Path(self.output_dir) / f"tts_seg_{i:03d}.mp3"
                if not _gen_tts(text, emotion_instruction, seg_out):
                    return "", f"TTS generation failed for segment {i}"
                
                if not seg_out.exists():
                     return "", f"TTS file missing for segment {i}"

                # 3. Align Duration
                dur = processor.get_audio_duration(str(seg_out))
                slot = max(0.1, end - start)
                
                # Check speed factor
                if dur > slot + 0.1: # Tolerance
                    # Speed up
                    factor = dur / slot
                    speed_out = Path(self.output_dir) / f"tts_seg_{i:03d}_speed.mp3"
                    if processor.adjust_audio_speed(str(seg_out), str(speed_out), factor):
                        clips_to_concat.append(str(speed_out))
                    else:
                        # Fallback to original
                        clips_to_concat.append(str(seg_out))
                elif dur < slot - 0.1:
                    # Pad
                    clips_to_concat.append(str(seg_out))
                    pad = slot - dur
                    pad_path = Path(self.output_dir) / f"pad_{i}_{int(pad*1000)}.mp3"
                    if processor.generate_silence(pad, str(pad_path)):
                        clips_to_concat.append(str(pad_path))
                else:
                    clips_to_concat.append(str(seg_out))

                current_time = end

            if not clips_to_concat:
                return "", "时间轴为空或无法生成配音"

            # Concat all
            if processor.concat_audio_files(clips_to_concat, str(audio_path)):
                return str(audio_path), ""
            else:
                return "", "音频拼接失败"

        except Exception as e:
            logger.error(f"Timeline synthesis failed: {e}", exc_info=True)
            return "", f"时间轴配音失败：{e}"
    def _save_script(self, script: str) -> str:
        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            script_path = str((Path(self.output_dir) / self._name_script).resolve())
            Path(script_path).write_text(script.strip() + "\n", encoding="utf-8")
            return script_path
        except Exception:
            return ""

    def _extract_timeline(self, data: dict | None) -> list[dict]:
        if not isinstance(data, dict):
            return []
        timeline = data.get("timeline")
        if not isinstance(timeline, list):
            return []
        cleaned = []
        for seg in timeline:
            if not isinstance(seg, dict):
                continue
            try:
                start = float(seg.get("start", 0))
                end = float(seg.get("end", 0))
            except Exception:
                continue
            text = (seg.get("text", "") or "").strip()
            emotion = (seg.get("emotion", "neutral") or "neutral").strip().lower()
            if not text or end <= start:
                continue
            emotion = self._normalize_or_infer_emotion(emotion, text)
            cleaned.append({"start": start, "end": end, "text": text, "emotion": emotion})
        cleaned.sort(key=lambda x: x["start"])
        cleaned = self._apply_structural_emotion(cleaned)
        return cleaned

    def _scene_emotion_defaults(self) -> dict[str, str]:
        """根据场景模式返回情绪推荐。"""
        scene_mode = (getattr(config, "TTS_SCENE_MODE", "") or "").strip().lower()
        # 默认：通用转化节奏
        mapping = {
            "hook": "excited",
            "pain": "serious",
            "solution": "persuasive",
            "cta": "firm",
        }

        if scene_mode == "commerce":
            return {"hook": "excited", "pain": "serious", "solution": "persuasive", "cta": "energetic"}
        if scene_mode == "review":
            return {"hook": "curious", "pain": "serious", "solution": "calm", "cta": "firm"}
        if scene_mode == "unboxing":
            return {"hook": "excited", "pain": "neutral", "solution": "warm", "cta": "energetic"}
        if scene_mode == "story":
            return {"hook": "suspense", "pain": "sad", "solution": "warm", "cta": "firm"}
        if scene_mode == "talk":
            return {"hook": "curious", "pain": "serious", "solution": "persuasive", "cta": "firm"}
        return mapping

    def _apply_structural_emotion(self, timeline: list[dict]) -> list[dict]:
        """按结构（Hook/Pain/Solution/CTA）为中性段落补情绪。"""
        if not timeline:
            return timeline
        total_end = max([seg.get("end", 0) for seg in timeline if isinstance(seg, dict)] or [0])
        if total_end <= 0:
            return timeline

        defaults = self._scene_emotion_defaults()

        for seg in timeline:
            if not isinstance(seg, dict):
                continue
            emo = (seg.get("emotion", "neutral") or "neutral").strip().lower()
            if emo and emo != "neutral":
                continue

            start = float(seg.get("start", 0) or 0)
            end = float(seg.get("end", 0) or 0)
            mid = (start + end) / 2.0
            ratio = 0 if total_end == 0 else (mid / total_end)

            # 结构阶段：前20% Hook，中间前半痛点，后半解决，最后15% CTA
            if ratio <= 0.2:
                seg["emotion"] = defaults.get("hook", "excited")
                continue
            if ratio <= 0.5:
                seg["emotion"] = defaults.get("pain", "serious")
                continue
            if ratio <= 0.85:
                seg["emotion"] = defaults.get("solution", "persuasive")
                continue
            seg["emotion"] = defaults.get("cta", "firm")

        return timeline

    def _normalize_or_infer_emotion(self, emotion: str, text: str) -> str:
        """标准化情绪标签；空/未知时基于文本做轻量推断。"""
        allowed = {
            "happy",
            "sad",
            "angry",
            "surprise",
            "neutral",
            "excited",
            "calm",
            "serious",
            "curious",
            "persuasive",
            "suspense",
            "warm",
            "firm",
            "energetic",
        }
        emo = (emotion or "").strip().lower()
        if emo in allowed:
            return emo
        inferred = self._infer_emotion_from_text(text)
        return inferred or "neutral"

    def _infer_emotion_from_text(self, text: str) -> str:
        """根据文本内容推断情绪（仅用于兜底）。"""
        t = (text or "").lower()

        # 疑问/引导
        if "?" in t or "？" in t or "why" in t or "what" in t or "how" in t or "怎么" in t or "为何" in t:
            return "curious"

        # 强召唤 / 行动号召
        cta_keywords = [
            "buy now",
            "get it",
            "order",
            "shop",
            "limited",
            "hurry",
            "right now",
            "马上",
            "现在",
            "立刻",
            "赶紧",
            "抢",
            "下单",
            "购买",
            "到手",
        ]
        if any(k in t for k in cta_keywords):
            return "firm"

        # 兴奋/吸睛
        excited_keywords = ["wow", "amazing", "insane", "crazy", "必看", "炸裂", "超", "太", "绝了"]
        if any(k in t for k in excited_keywords) or "!" in t or "！" in t:
            return "excited"

        # 负向/问题场景
        negative_keywords = ["pain", "problem", "annoy", "hate", "难受", "麻烦", "困扰", "糟糕", "烦", "痛点"]
        if any(k in t for k in negative_keywords):
            return "serious"

        # 解决/说服
        persuasive_keywords = ["solution", "fix", "solve", "帮你", "解决", "改善", "建议", "推荐", "reason"]
        if any(k in t for k in persuasive_keywords):
            return "persuasive"

        # 温和种草
        warm_keywords = ["gentle", "soft", "cozy", "舒服", "温柔", "安心", "放松", "治愈"]
        if any(k in t for k in warm_keywords):
            return "warm"

        return "neutral"
    def _copy_original_video(self, script_path: str = "") -> str:
        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            ext = Path(self.video_path).suffix or ".mp4"
            out_path = str((Path(self.output_dir) / f"原视频{ext}").resolve())
            shutil.copy2(self.video_path, out_path)
            if script_path:
                logger.info(f"脚本已输出：{script_path}")
            return out_path
        except Exception as e:
            logger.error(f"降级输出失败: {e}")
            return ""

    def mix_audio_video(self, audio_path: str, subtitle_srt_path: str = ""):
        """
        Riley Goodside 重构版：
        使用 FFmpeg Filter Complex 实现【单次编码】完成：
        1. 视频自动循环补齐音频时长
        2. 原声压低 + TTS 混合
        3. 字幕烧录
        4. 极速渲染
        """
        try:
            output_path = str((Path(self.output_dir) / self._name_remix).resolve())

            video_inp = str(Path(self.video_path).resolve())
            audio_inp = str(Path(audio_path).resolve())

            import shutil

            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                try:
                    import imageio_ffmpeg  # type: ignore
                    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                except Exception:
                    ffmpeg_path = None
            if not ffmpeg_path:
                logger.error("未找到 ffmpeg，无法执行混流")
                return None

            cmd = [
                ffmpeg_path, "-y",
                "-stream_loop", "-1", "-i", video_inp,
                "-i", audio_inp,
            ]

            # 原视频无音轨时补一个静音轨，避免 filter_complex 报错
            has_audio = self._has_audio_stream(video_inp)
            if not has_audio:
                cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

            filter_chains = []
            # 音频鸭闪：当 TTS 出现时压低原声
            if has_audio:
                filter_chains.append("[0:a][1:a]sidechaincompress=threshold=0.02:ratio=10:attack=5:release=200[ducked]")
                filter_chains.append("[ducked][1:a]amix=inputs=2:duration=shortest[a_out]")
            else:
                # 使用静音轨占位后混音
                filter_chains.append("[2:a][1:a]amix=inputs=2:duration=shortest[a_out]")

            video_map_label = "0:v"
            subtitle_srt_path = (subtitle_srt_path or "").strip()
            if subtitle_srt_path and Path(subtitle_srt_path).exists():
                sub_path_esc = str(Path(subtitle_srt_path).resolve()).replace("\\", "/").replace(":", "\\:")
                filter_chains.append(
                    f"[0:v]subtitles='{sub_path_esc}':force_style='Fontname=Microsoft YaHei UI,Fontsize=16,PrimaryColour=&H00FFFFFF,Outline=2'[v_out]"
                )
                video_map_label = "[v_out]"

            cmd.extend(["-filter_complex", ";".join(filter_chains)])

            cmd.extend([
                "-map", video_map_label,
                "-map", "[a_out]",
                "-shortest",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "aac",
                output_path,
            ])

            try:
                self.progress.emit(75, "🚀 正在进行极速渲染 (FFmpeg Native)...")
            except Exception:
                pass

            logger.info(f"Executing FFmpeg: {' '.join(cmd)}")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            proc = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
            if proc.returncode != 0:
                logger.error(f"FFmpeg Error: {proc.stderr}")
                return None

            return output_path
        except Exception as e:
            logger.error(f"FFmpeg Pipeline Failed: {e}")
            return None

    def _has_audio_stream(self, video_path: str) -> bool:
        """检测视频是否包含音轨。"""
        try:
            import shutil
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                return True
            cmd = [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=nw=1:nk=1",
                str(Path(video_path).resolve()),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            return (proc.stdout or "").strip() == "audio"
        except Exception:
            return True

    def _save_subtitles(self, script_text: str, audio_path: str) -> str:
        """生成并落盘 SRT 字幕。

        - 以合成配音文本为来源
        - 时轴按音频总时长做均匀/按文本长度加权分配
        """
        try:
            # Removed MoviePy dependency
            s = (script_text or "").strip()
            if not s:
                return ""

            duration = VideoProcessor().get_audio_duration(audio_path)

            if duration <= 0.2:
                return ""

            captions = self._split_script_to_captions(s)
            if not captions:
                return ""

            srt_text = self._build_srt(captions=captions, total_duration=duration)
            if not srt_text:
                return ""

            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            srt_path = str((Path(self.output_dir) / self._name_captions).resolve())
            Path(srt_path).write_text(srt_text, encoding="utf-8")
            return srt_path
        except Exception as e:
            logger.error(f"字幕生成失败: {e}")
            return ""

    def _save_subtitles_with_timeline(self, timeline: list[dict]) -> str:
        """按时间轴落点生成 SRT 字幕。"""
        try:
            if not timeline:
                return ""

            lines: list[str] = []
            i = 1
            for seg in timeline:
                if not isinstance(seg, dict):
                    continue
                try:
                    start = float(seg.get("start", 0))
                    end = float(seg.get("end", 0))
                except Exception:
                    continue
                text = (seg.get("text", "") or "").strip()
                if not text or end <= start:
                    continue

                lines.append(str(i))
                lines.append(f"{self._fmt_srt_ts(start)} --> {self._fmt_srt_ts(end)}")
                lines.append(text)
                lines.append("")
                i += 1

            if not lines:
                return ""

            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            srt_path = str((Path(self.output_dir) / self._name_captions).resolve())
            Path(srt_path).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
            return srt_path
        except Exception as e:
            logger.error(f"字幕生成失败: {e}")
            return ""

    def _split_script_to_captions(self, text: str) -> list[str]:
        s = (text or "").strip()
        if not s:
            return []

        # 先按句号/问号/感叹号切分
        parts = re.split(r"(?<=[\.!\?。！？])\s+", s)
        parts = [p.strip() for p in parts if p and p.strip()]
        if not parts:
            return []

        captions: list[str] = []
        for p in parts:
            # 再按逗号做二次切分（避免单句过长）
            sub = re.split(r"(?<=[,，；;:：])\s*", p)
            sub = [x.strip() for x in sub if x and x.strip()]
            if not sub:
                continue
            for x in sub:
                captions.extend(self._wrap_caption_line(x))

        # 去掉过短空白
        captions = [c for c in captions if c.strip()]
        # 最多 18 行，避免字幕太碎
        if len(captions) > 18:
            # 合并相邻行
            merged: list[str] = []
            buf = ""
            for c in captions:
                if not buf:
                    buf = c
                    continue
                if len(buf) + 1 + len(c) <= 84:
                    buf = f"{buf} {c}".strip()
                else:
                    merged.append(buf)
                    buf = c
            if buf:
                merged.append(buf)
            captions = merged[:18]

        return captions

    def _wrap_caption_line(self, line: str) -> list[str]:
        """简单换行：英文按词，中文按长度。"""
        s = (line or "").strip()
        if not s:
            return []

        has_cjk = any(("\u4e00" <= ch <= "\u9fff") for ch in s)
        if has_cjk:
            max_len = 22
            out: list[str] = []
            buf = ""
            for ch in s:
                buf += ch
                if len(buf) >= max_len:
                    out.append(buf.strip())
                    buf = ""
            if buf.strip():
                out.append(buf.strip())
            return out

        # 英文：按词拼接
        words = [w for w in s.split() if w.strip()]
        if not words:
            return []
        max_len = 44
        out: list[str] = []
        buf = ""
        for w in words:
            candidate = (buf + " " + w).strip() if buf else w
            if len(candidate) <= max_len:
                buf = candidate
            else:
                if buf:
                    out.append(buf)
                buf = w
        if buf:
            out.append(buf)
        return out

    def _build_srt(self, captions: list[str], total_duration: float) -> str:
        if not captions or total_duration <= 0:
            return ""

        weights = [max(1, len(re.sub(r"\s+", "", c))) for c in captions]
        total_w = float(sum(weights))
        raw = [total_duration * (w / total_w) for w in weights]

        # 约束每条字幕时长
        min_d, max_d = 1.0, 4.5
        clipped = [min(max(d, min_d), max_d) for d in raw]
        ssum = float(sum(clipped))
        if ssum <= 0:
            return ""
        scale = total_duration / ssum
        durations = [d * scale for d in clipped]

        lines: list[str] = []
        t = 0.0
        for i, (cap, d) in enumerate(zip(captions, durations), start=1):
            start = t
            end = t + float(d)
            if i == len(captions):
                end = total_duration
            if end <= start:
                continue
            lines.append(str(i))
            lines.append(f"{self._fmt_srt_ts(start)} --> {self._fmt_srt_ts(end)}")
            lines.append(cap)
            lines.append("")
            t = end
            if t >= total_duration:
                break

        return "\n".join(lines).strip() + "\n"

    def _fmt_srt_ts(self, seconds: float) -> str:
        ms = int(max(0.0, seconds) * 1000)
        h = ms // 3600000
        ms = ms % 3600000
        m = ms // 60000
        ms = ms % 60000
        s = ms // 1000
        ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _burn_subtitles_ffmpeg(self, *, input_video_path: str, srt_path: str) -> str:
        """使用 ffmpeg 将 srt 字幕烧录到视频中。

        失败则返回空字符串（不影响主流程）。
        """
        in_path = (input_video_path or "").strip()
        sub_path = (srt_path or "").strip()
        if not in_path or not sub_path:
            return ""

        # 仅控制“烧录”开关：关闭时仍会保留 .srt 文件
        try:
            if not bool(getattr(config, "SUBTITLE_BURN_ENABLED", True)):
                return ""
        except Exception:
            pass

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            try:
                import imageio_ffmpeg  # type: ignore

                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_path = None

        if not ffmpeg_path:
            return ""

        in_p = Path(in_path)
        out_path = str((in_p.parent / self._name_remix_sub).resolve())

        # TikTok 风格字幕：白字黑描边 + 底部居中抬高
        v_h = self._get_video_height(in_path)

        # 字号：优先使用 px（更直观）；否则用按分辨率自适应
        try:
            font_auto = bool(getattr(config, "SUBTITLE_FONT_AUTO", True))
        except Exception:
            font_auto = True

        font_size = 56
        if not font_auto:
            try:
                font_size = int(getattr(config, "SUBTITLE_FONT_SIZE", 56) or 56)
            except Exception:
                font_size = 56
            font_size = int(max(10, min(140, font_size)))
        else:
            try:
                font_ratio = float(getattr(config, "SUBTITLE_FONT_SIZE_RATIO", 0.034) or 0.034)
            except Exception:
                font_ratio = 0.034
            try:
                font_min = int(getattr(config, "SUBTITLE_FONT_SIZE_MIN", 34) or 34)
            except Exception:
                font_min = 34
            try:
                font_max = int(getattr(config, "SUBTITLE_FONT_SIZE_MAX", 72) or 72)
            except Exception:
                font_max = 72
            font_size = int(max(font_min, min(font_max, round(v_h * font_ratio))))

        # 描边：支持“自动（按字号自适应）”与“手动像素值（无上限）”两种模式
        try:
            outline_auto = bool(getattr(config, "SUBTITLE_OUTLINE_AUTO", True))
        except Exception:
            outline_auto = True

        outline = 2
        if not outline_auto:
            try:
                outline_px = int(getattr(config, "SUBTITLE_OUTLINE", 4) or 4)
            except Exception:
                outline_px = 4
            # 手动模式：直接使用用户配置的像素值，不做上限裁剪（无限制）
            outline = int(max(0, outline_px))
        else:
            # 自动模式基础比例：字号的 9%（比 12% 更薄，更接近 TikTok 常见观感）
            base_ratio = 0.09
            try:
                outline_min = int(getattr(config, "SUBTITLE_OUTLINE_MIN", 2) or 2)
            except Exception:
                outline_min = 2
            try:
                outline_max = int(getattr(config, "SUBTITLE_OUTLINE_MAX", 10) or 10)
            except Exception:
                outline_max = 10

            # 小字号（如 12~24px）时，固定最小描边会显得“糊成一坨”，这里做自适应下限
            # 最小描边不要超过字号的 6%，否则会显得“糊”
            adaptive_min = min(outline_min, max(1, int(round(font_size * 0.06))))
            if font_size <= 18:
                adaptive_min = min(adaptive_min, 1)
            elif font_size <= 24:
                adaptive_min = min(adaptive_min, 2)

            adaptive_max = max(1, min(outline_max, int(round(font_size * 0.30))))
            outline = int(max(1, min(adaptive_max, round(font_size * base_ratio))))
            outline = max(adaptive_min, outline)

        try:
            shadow = int(getattr(config, "SUBTITLE_SHADOW", 2) or 2)
        except Exception:
            shadow = 2
        shadow = int(max(0, min(8, shadow)))

        try:
            margin_ratio = float(getattr(config, "SUBTITLE_MARGIN_V_RATIO", 0.095) or 0.095)
        except Exception:
            margin_ratio = 0.095
        try:
            margin_min = int(getattr(config, "SUBTITLE_MARGIN_V_MIN", 60) or 60)
        except Exception:
            margin_min = 60
        margin_v = int(max(margin_min, round(v_h * margin_ratio)))

        try:
            margin_lr = int(getattr(config, "SUBTITLE_MARGIN_LR", 40) or 40)
        except Exception:
            margin_lr = 40
        margin_lr = int(max(0, min(200, margin_lr)))

        try:
            font_name = (getattr(config, "SUBTITLE_FONT_NAME", "Microsoft YaHei UI") or "Microsoft YaHei UI").strip()
        except Exception:
            font_name = "Microsoft YaHei UI"
        if not font_name:
            font_name = "Microsoft YaHei UI"

        style = (
            f"Fontname={font_name},"
            f"Fontsize={font_size},"
            "Bold=1,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BorderStyle=1,"
            f"Outline={outline},"
            f"Shadow={shadow},"
            "Alignment=2,"
            f"MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr}"
        )

        # ffmpeg subtitles filter 在 Windows 下需要转义盘符冒号
        filter_path = Path(sub_path).resolve().as_posix().replace(":", "\\:")
        vf = f"subtitles='{filter_path}':force_style='{style}'"

        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            str(Path(in_path).resolve()),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "copy",
            out_path,
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if proc.returncode == 0 and Path(out_path).exists():
                return out_path
            err = (proc.stderr or proc.stdout or "").strip()
            logger.warning(f"字幕烧录失败：{err[:200]}")
            return ""
        except Exception as e:
            logger.warning(f"字幕烧录异常：{e}")
            return ""

    def _get_video_height(self, video_path: str) -> int:
        """尽量获取视频高度，用于字幕字号/边距自适应。"""
        # 1) 优先 ffprobe（最可靠，避免 moviepy/解码失败回退导致字号巨大）
        try:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                ffmpeg = shutil.which("ffmpeg")
                if ffmpeg:
                    cand = str(Path(ffmpeg).resolve().parent / "ffprobe.exe")
                    if Path(cand).exists():
                        ffprobe = cand
            if ffprobe:
                # 取 width/height + rotate，得到“显示高度”（手机竖屏常见会带 rotate 元数据）
                cmd = [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height:stream_tags=rotate",
                    "-of",
                    "default=nw=1:nk=1",
                    str(Path(video_path).resolve()),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode == 0:
                    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
                    if len(lines) >= 2:
                        try:
                            w = int(float(lines[0]))
                            h = int(float(lines[1]))
                        except Exception:
                            w, h = 0, 0

                        rotate = 0
                        if len(lines) >= 3:
                            try:
                                rotate = int(float(lines[2]))
                            except Exception:
                                rotate = 0

                        if w > 0 and h > 0:
                            if rotate % 180 != 0:
                                # 90/270：显示宽高互换
                                w, h = h, w
                            if h > 0:
                                return h
        except Exception:
            pass
        
        # Fallback default
        return 1920

    def _prepare_job_dir(self, base_dir: Path, stem_safe: str) -> Path:
        """按输入文件名创建子目录；冲突时自动追加序号，避免覆盖。"""
        base_dir = Path(base_dir)
        candidate = base_dir / stem_safe
        if not candidate.exists():
            return candidate

        # 目录已存在：追加时间戳，确保每次生成不覆盖
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate2 = base_dir / f"{stem_safe}_{ts}"
        if not candidate2.exists():
            return candidate2
        # 极端碰撞：再加计数
        for i in range(1, 200):
            c = base_dir / f"{stem_safe}_{ts}_{i:03d}"
            if not c.exists():
                return c
        return candidate2

    def _safe_name(self, name: str) -> str:
        """生成 Windows 兼容的文件/文件夹名。"""
        s = (name or "").strip()
        if not s:
            return ""
        # 替换 Windows 不允许字符
        s = re.sub(r'[<>:"/\\|\?\*]+', "_", s)
        s = re.sub(r"\s+", " ", s).strip()
        # 末尾不能是点或空格
        s = s.rstrip(" .")
        # 过长截断
        if len(s) > 80:
            s = s[:80].rstrip(" .")
        return s

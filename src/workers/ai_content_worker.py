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

            api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
            if not api_key:
                logger.warning("AI_API_KEY 未配置")
                return None
            
            # 配置 OpenAI 兼容客户端
            client = openai.OpenAI(
                api_key=api_key,
                base_url=((getattr(config, "AI_BASE_URL", "") or "").strip() or "https://api.deepseek.com"),
            )

            # 火山方舟（Ark）深度思考：仅当用户显式配置且 base_url 为 Ark 时透传。
            base_url_now = ""
            try:
                base_url_now = (getattr(config, "AI_BASE_URL", "") or "").strip()
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

            use_model = (
                (self.model or "").strip()
                or (getattr(config, "AI_MODEL", "") or "deepseek-chat")
            )

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
                    "max_tokens": 1000,
                    "temperature": 0.5,
                }
                if ark_extra:
                    kwargs["extra_body"] = ark_extra
                    
                response = client.chat.completions.create(**kwargs)
                
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
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()

        def _try(p: str) -> None:
            tts_synthesize(text=text, out_path=audio_path, provider=p)

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

    def synthesize_timeline_voice(self, timeline: list[dict]) -> tuple[str, str]:
        """根据时间轴逐段合成语音，并做弹性对齐。"""
        try:
            from moviepy import AudioFileClip, AudioClip, concatenate_audioclips
        except Exception as e:
            return "", f"MoviePy 依赖缺失：{e}"

        audio_path = Path(self.output_dir) / self._name_voice_timeline

        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()
        clips = []
        current_time = 0.0

        def _silence(duration: float):
            if duration <= 0:
                return None
            return AudioClip(lambda t: 0, duration=duration, fps=44100)

        try:
            for i, seg in enumerate(timeline):
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

                # gap
                if start > current_time:
                    gap = start - current_time
                    s = _silence(gap)
                    if s:
                        clips.append(s)
                        current_time += gap

                seg_out = Path(self.output_dir) / f"tts_seg_{i:03d}.mp3"
                try:
                    tts_synthesize(text=text, out_path=seg_out, provider=provider, emotion=emotion)
                except Exception as e:
                    if fallback:
                        try:
                            tts_synthesize(text=text, out_path=seg_out, provider=fallback, emotion=emotion)
                        except Exception as e2:
                            return "", f"TTS 分段失败：{e}；备用失败：{e2}"
                    else:
                        return "", f"TTS 分段失败：{e}"

                if not seg_out.exists():
                    return "", "分段配音文件未生成"

                clip = AudioFileClip(str(seg_out))
                slot = max(0.1, end - start)
                dur = float(getattr(clip, "duration", 0.0) or 0.0)

                # 弹性对齐
                if dur > slot:
                    factor = dur / slot
                    try:
                        clip = clip.with_speed_scaled(factor)
                    except Exception:
                        pass
                elif dur < slot:
                    pad = slot - dur
                    s = _silence(pad)
                    if s:
                        clips.append(clip)
                        clips.append(s)
                        current_time = end
                        continue

                clips.append(clip)
                current_time = end

            if not clips:
                return "", "时间轴为空或无法生成配音"

            final_audio = concatenate_audioclips(clips)
            final_audio.write_audiofile(str(audio_path), logger=None)
            return str(audio_path), ""
        except Exception as e:
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
            emotion = (seg.get("emotion", "neutral") or "neutral").strip()
            if not text or end <= start:
                continue
            cleaned.append({"start": start, "end": end, "text": text, "emotion": emotion})
        cleaned.sort(key=lambda x: x["start"])
        return cleaned
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
        """使用 MoviePy 混合音视频（原声 2% + 合成配音），并可选烧录字幕。"""
        try:
            # 懒加载 moviepy (Upgrade to 2.0+)
            from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx

            video = VideoFileClip(self.video_path)
            new_audio = AudioFileClip(audio_path)

            # 处理原声：降低音量到 2%
            if video.audio:
                original_audio = video.audio.with_volume_scaled(0.02)
                final_audio = CompositeAudioClip([original_audio, new_audio])
            else:
                final_audio = new_audio

            # 时长对齐
            if new_audio.duration > video.duration:
                # video = video.loop(duration=new_audio.duration) # OLD
                video = video.with_effects([vfx.Loop(duration=new_audio.duration)])

            # final_video = video.set_audio(final_audio) # OLD
            final_video = video.with_audio(final_audio)

            output_path = str((Path(self.output_dir) / self._name_remix).resolve())

            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                logger=None,
            )

            try:
                video.close()
                new_audio.close()
            except Exception:
                pass

            subtitle_srt_path = (subtitle_srt_path or "").strip()
            if subtitle_srt_path:
                try:
                    self.progress.emit(85, "🧩 正在烧录字幕到视频...")
                except Exception:
                    pass
                burned = self._burn_subtitles_ffmpeg(
                    input_video_path=output_path,
                    srt_path=subtitle_srt_path,
                )
                if burned:
                    try:
                        self.progress.emit(92, "✅ 字幕已烧录")
                    except Exception:
                        pass
                    return burned
                try:
                    self.progress.emit(92, "⚠️ 字幕烧录失败（已保留 .srt 文件）")
                except Exception:
                    pass

            return output_path

        except Exception as e:
            logger.error(f"音视频混合失败: {e}")
            return None

    def _save_subtitles(self, script_text: str, audio_path: str) -> str:
        """生成并落盘 SRT 字幕。

        - 以合成配音文本为来源
        - 时轴按音频总时长做均匀/按文本长度加权分配
        """
        try:
            from moviepy import AudioFileClip

            s = (script_text or "").strip()
            if not s:
                return ""

            audio = AudioFileClip(audio_path)
            duration = float(getattr(audio, "duration", 0.0) or 0.0)
            try:
                audio.close()
            except Exception:
                pass

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

        # 2) 回退 moviepy
        try:
            from moviepy import VideoFileClip

            clip = VideoFileClip(video_path)
            try:
                h = int(getattr(clip, "h", 0) or 0)
                if not h:
                    size = getattr(clip, "size", None)
                    if size and len(size) == 2:
                        h = int(size[1])
            finally:
                try:
                    clip.close()
                except Exception:
                    pass
            # 默认回退：优先按“手机竖屏高度”估算，保证字幕不至于过小
            return h if h > 0 else 1920
        except Exception:
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

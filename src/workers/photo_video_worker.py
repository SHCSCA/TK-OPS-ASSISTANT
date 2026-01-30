"""图转视频 Worker（Photo-to-Video Engine）

流程：
- 生成时间轴脚本（含情感标签）
- 逐段 TTS + 弹性对齐
- 图片流合成视频（Ken Burns）
- 混音输出 + 生成字幕
"""
from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime
import math
from pathlib import Path
from typing import Any

import config
from workers.base_worker import BaseWorker
from tts import synthesize as tts_synthesize
from utils.cloud_video import generate_video_from_image
from video.processor import VideoProcessor
from utils.ffmpeg import FFmpegUtils

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start : end + 1]
    try:
        obj = json.loads(s)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


class PhotoVideoWorker(BaseWorker):
    """图转视频 Worker。"""

    def __init__(
        self,
        images: list[str] | None = None,
        product_desc: str = "",
        output_dir: str = "",
        image_durations: list[float] | None = None,
        role_prompt: str = "",
        model: str = "",
        provider: str = "",
        bgm_path: str = "",
        total_duration: float = 15.0,
    ) -> None:
        super().__init__()
        self.images = [str(p) for p in (images or [])]
        self.product_desc = (product_desc or "").strip()
        self.output_dir = (output_dir or "").strip()
        self.image_durations = [float(x) for x in (image_durations or [])]
        self.role_prompt = (role_prompt or "").strip()
        self.model = (model or "").strip()
        self.provider = (provider or "").strip()
        self.bgm_path = (bgm_path or "").strip()
        self.total_duration = max(5.0, float(total_duration or 15.0))

        self._name_script = "脚本_图文.txt"
        self._name_audio = "配音_图文.mp3"
        self._name_srt = "字幕_图文.srt"
        self._name_video = "成片_图文.mp4"

    def generate_preview(self, images, desc, bgm, duration, image_durations, output_path, callback):
        """异步生成预览视频，完成后回调callback(path)"""
        import threading

        def _work():
            try:
                self.images = [str(p) for p in (images or [])]
                self.image_durations = [float(x) for x in (image_durations or [])]
                timeline = self._quick_timeline(images, desc, duration)
                audio_path = (bgm or "").strip()
                video_path = self._compose_photo_video(timeline, audio_path, Path(output_path))
                callback(video_path if video_path else None)
            except Exception:
                callback(None)

        threading.Thread(target=_work, daemon=True).start()

    def _quick_timeline(self, images, desc, duration):
        n = max(1, len(images or []))
        seg_dur = max(0.5, float(duration) / n)
        timeline = []
        for i, img in enumerate(images or []):
            timeline.append({
                "start": round(i * seg_dur, 2),
                "end": round((i + 1) * seg_dur, 2),
                "text": (desc or "").strip() if i == 0 else "",
                "emotion": "neutral",
                "image": img,
            })
        return timeline

    def _run_impl(self) -> None:
        if not self.images:
            self.emit_finished(False, "请先选择图片")
            return
        if not self.product_desc:
            self.emit_finished(False, "请先填写商品/文案描述")
            return

        out_dir = self._prepare_output_dir()
        self.emit_log(f"📁 输出目录：{out_dir}")

        timeline = self._generate_timeline()
        if not timeline:
            self.emit_finished(False, "时间轴脚本生成失败")
            return

        full_script = " ".join([x.get("text", "") for x in timeline if x.get("text")]).strip()
        self._save_text(out_dir / self._name_script, full_script)

        self.emit_log("🎙️ 正在合成语音（时间轴模式）...")
        audio_path, err = self._synthesize_timeline_audio(timeline, out_dir / self._name_audio)
        if not audio_path:
            self.emit_finished(False, f"语音合成失败：{err}")
            return

        self.emit_log("📝 正在生成字幕...")
        srt_path = self._save_srt_from_timeline(timeline, out_dir / self._name_srt)
        if not srt_path:
            self.emit_log("⚠️ 字幕生成失败，将继续输出无字幕视频")

        self.emit_log("🖼️ 正在生成图片流视频...")
        video_path = ""
        if bool(getattr(config, "VIDEO_CLOUD_ENABLED", False)):
            self.emit_log("☁️ 使用云端图转视频（真实生成）...")
            video_path = self._compose_cloud_video(timeline, out_dir / self._name_video)
        if not video_path:
            video_path = self._compose_photo_video(timeline, audio_path, out_dir / self._name_video)
        if not video_path:
            self.emit_finished(False, "图转视频失败")
            return

        # 二次校验成片是否真实落盘
        try:
            if not Path(video_path).exists():
                self.emit_log(f"❌ 成片未找到：{video_path}")
                self.emit_finished(False, "图转视频完成但未找到成片文件，请检查输出目录")
                return
        except Exception:
            pass

        self.emit_log(f"✅ 成片路径：{video_path}")

        # 可选：烧录字幕
        if srt_path:
            burned = self._burn_subtitles_ffmpeg(input_video_path=video_path, srt_path=str(srt_path))
            if burned:
                video_path = burned

        compressed = self._compress_for_tiktok(video_path)
        if compressed:
            video_path = compressed

        self.data_signal.emit({"video": str(video_path), "srt": str(srt_path) if srt_path else ""})
        self.emit_finished(True, "图转视频完成")

    def _compose_cloud_video(self, timeline: list[dict], out_path: Path) -> str:
        """使用云端图转视频生成主画面，并替换音频。"""
        try:
            if not self.images:
                self.emit_log("未提供图片，无法云端生成")
                return ""

            prompt = (self.product_desc or "").strip()
            if self.role_prompt:
                prompt = f"{prompt}\n风格要求：{self.role_prompt}"

            quality = (getattr(config, "VIDEO_CLOUD_QUALITY", "low") or "low").strip()
            fps = int(getattr(config, "PHOTO_VIDEO_FPS", 24) or 24)
            duration = float(self.total_duration or 6.0)

            # Determine which model to use for Video Generation
            # If self.model is a video model (e.g. Seedance), use it.
            # Otherwise use default from config.VIDEO_CLOUD_MODEL
            video_model_override = ""
            if self.model:
                m_low = self.model.lower()
                if any(k in m_low for k in ("seedance", "t2v", "i2v", "wan2.1", "wan2-1")):
                    video_model_override = self.model
                    self.emit_log(f"🎬 使用指定视频模型：{self.model}")

            ok, msg = generate_video_from_image(
                image_path=self.images[0],
                prompt=prompt,
                out_path=out_path,
                duration=duration,
                fps=fps,
                quality=quality,
                model=video_model_override,
            )
            if not ok:
                self.emit_log(f"云端生成失败：{msg}")
                return ""

            # 替换为时间轴配音（若存在）
            merged_path = out_path.with_name(out_path.stem + "_tts.mp4")
            from video.processor import VideoProcessor
            processor = VideoProcessor()
            audio_path = str((Path(self.output_dir) / self._name_audio).resolve())
            if Path(audio_path).exists():
                ok_merge, res = processor.merge_av(str(out_path), audio_path, str(merged_path))
                if ok_merge:
                    return str(merged_path)
            return str(out_path)
        except Exception as e:
            self.emit_log(f"云端图转视频异常：{e}")
            return ""

    def _prepare_output_dir(self) -> Path:
        base = Path(self.output_dir or getattr(config, "OUTPUT_DIR", Path("Output")))
        if base.name.lower() != "image_videos":
            base = base / "Image_Videos"
        base.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = base / ts
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _generate_timeline(self) -> list[dict]:
        try:
            import openai

            from utils.ai_routing import resolve_ai_profile

            profile = resolve_ai_profile("photo", model_override=self.model, provider_override=self.provider)
            api_key = (profile.get("api_key", "") or "").strip()
            if not api_key:
                self.emit_log("AI_API_KEY 未配置")
                return []

            base_url = (profile.get("base_url", "") or "").strip() or "https://api.deepseek.com"
            use_model = (profile.get("model", "") or "").strip() or "deepseek-chat"

            system = (
                "You are a TikTok short-form script writer. "
                "Output STRICT JSON only. No markdown. No extra keys."
            )
            if self.role_prompt:
                system += "\n[ROLE_PROMPT]\n" + self.role_prompt

            user = (
                "Generate a timeline voiceover script with timestamps and emotions.\n"
                f"Total duration: {self.total_duration:.1f} seconds.\n"
                "Constraints:\n"
                "- English pacing ~2.5 words/second.\n"
                "- Emotion must be one of: happy, sad, angry, surprise, neutral, excited, calm, serious, curious, persuasive, suspense, warm, firm, energetic.\n"
                "- Emotion selection guide: hook=excited/curious, pain=serious, solution=persuasive/warm, CTA=firm/energetic.\n"
                "- Structure guide: ensure segments roughly follow Hook -> Pain -> Solution -> CTA in order.\n"
                "- Output STRICT JSON object with key timeline only.\n\n"
                "JSON schema:\n"
                "{\n"
                "  \"timeline\": [\n"
                "    {\"start\":0, \"end\":3, \"text\":\"...\", \"emotion\":\"happy\"}\n"
                "  ]\n"
                "}\n\n"
                f"Product description:\n{self.product_desc}\n"
            )
            try:
                scene_mode = (getattr(config, "TTS_SCENE_MODE", "") or "").strip()
            except Exception:
                scene_mode = ""
            if scene_mode:
                user += f"\nScene mode: {scene_mode} (tone guidance)\n"

            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            # --- Model Capability Validation & Text Fallback ---
            # If the user configured a Video Model (e.g. Seedance) for this task,
            # we must fallback to a Text Model for the SCRIPT generation step,
            # while preserving the user's Video Model choice for the later video generation step.
            _model_lower = use_model.lower()
            if any(k in _model_lower for k in ("seedance", "t2v", "i2v", "wan2.1", "wan2-1")):
                self.emit_log(f"⚠️ 检测到视频模型 '{use_model}' 用于脚本生成")
                
                # Fallback to Global Text Model
                fallback_model = (getattr(config, "AI_MODEL", "") or "").strip() or "deepseek-chat"
                fallback_key = (getattr(config, "AI_API_KEY", "") or "").strip()
                fallback_base = (getattr(config, "AI_BASE_URL", "") or "").strip() or "https://api.deepseek.com"
                
                self.emit_log(f"🔄 自动切换至文本模型 '{fallback_model}' 进行脚本编写...")
                
                if not fallback_key:
                    self.emit_log("❌ 无法切换：全局 AI_API_KEY 未配置")
                    return []
                    
                client = openai.OpenAI(api_key=fallback_key, base_url=fallback_base)
                use_model = fallback_model

            # 2. DeepSeek Model Name Validation & Auto-Correction
            if "deepseek.com" in base_url:
                if use_model not in ("deepseek-chat", "deepseek-reasoner"):
                    original_model = use_model
                    # Auto-correct R1 variants to deepseek-reasoner
                    if "r1" in original_model.lower():
                        use_model = "deepseek-reasoner"
                        self.emit_log(f"⚠️ 自动修正：模型 '{original_model}' -> '{use_model}' (DeepSeek R1 官方名称)")
                    else:
                        # Auto-correct V3 variants to deepseek-chat
                        use_model = "deepseek-chat"
                        self.emit_log(f"⚠️ 自动修正：模型 '{original_model}' -> '{use_model}' (DeepSeek V3 官方名称)")
                    
                    self.emit_log("💡 提示：DeepSeek 官方 API 仅支持 'deepseek-chat' (V3) 和 'deepseek-reasoner' (R1)。")

            def _is_transient_error(err: Exception) -> bool:
                msg = str(err) or ""
                msg_low = msg.lower()
                if "internalserviceerror" in msg_low:
                    return True
                if "internal server error" in msg_low:
                    return True
                if "error code: 500" in msg_low or "http 500" in msg_low:
                    return True
                return False

            resp = None
            for attempt in range(1, 4):
                try:
                    resp = client.chat.completions.create(
                        model=use_model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.4,
                        max_tokens=4096,
                        response_format={"type": "json_object"},
                    )
                    break
                except Exception as e:
                    if _is_transient_error(e) and attempt < 3:
                        self.emit_log(f"⚠️ 时间轴生成失败（服务端错误），准备重试 {attempt}/3...")
                        time.sleep(1.2 * attempt)
                        continue
                    raise

            if resp is None:
                return []

            try:
                if resp and resp.usage:
                    u = resp.usage
                    self.emit_log(f"💰 Token 消耗: Prompt={u.prompt_tokens}, Completion={u.completion_tokens}, Total={u.total_tokens}")
            except Exception:
                pass

            payload = _extract_json_object(resp.choices[0].message.content or "")
            if not payload:
                return []

            timeline = payload.get("timeline")
            if not isinstance(timeline, list):
                return []

            return self._normalize_timeline(timeline)
        except Exception as e:
            # 强化错误提示
            err_msg = str(e)
            if "Error code: 404" in err_msg or "NotFound" in err_msg:
                friendly_msg = f"❌ 模型不存在或不可用 ({use_model})。请检查设置中的模型名称。"
                self.emit_log(friendly_msg)
                return []
            if "Error code: 400" in err_msg:
                 friendly_msg = f"❌ 请求参数错误 (400)。可能是当前模型 ({use_model}) 不支持所请求的功能（如 JSON 模式）。"
                 self.emit_log(friendly_msg)
                 return []
            
            logger.error(f"时间轴生成失败: {e}", exc_info=True)
            self.emit_log(f"时间轴生成失败：{e}")
            return []

    def _normalize_timeline(self, timeline: list[dict]) -> list[dict]:
        cleaned: list[dict] = []
        for item in timeline:
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start", 0))
                end = float(item.get("end", 0))
            except Exception:
                continue
            text = (item.get("text", "") or "").strip()
            emotion = (item.get("emotion", "neutral") or "neutral").strip().lower()
            if not text or end <= start:
                continue
            cleaned.append({"start": start, "end": end, "text": text, "emotion": emotion})

        if not cleaned:
            return []

        cleaned.sort(key=lambda x: x["start"])
        out: list[dict] = []
        for seg in cleaned:
            if seg["start"] >= self.total_duration:
                continue
            seg["end"] = min(seg["end"], self.total_duration)
            if seg["end"] <= seg["start"]:
                continue
            out.append(seg)
        return out

    def _synthesize_timeline_audio(self, timeline: list[dict], out_path: Path) -> tuple[str, str]:
        processor = VideoProcessor()
        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()

        audio_segments = []
        cleanup_files = []
        current_time = 0.0

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

                # Handle Gap
                if start > current_time:
                    gap = start - current_time
                    if gap > 0.05:
                        gap_file = out_path.parent / f"silence_gap_{i}_{int(time.time())}.mp3"
                        if processor.generate_silence(gap, str(gap_file)):
                            audio_segments.append(str(gap_file))
                            cleanup_files.append(gap_file)
                        current_time += gap

                # Generate TTS
                seg_out = out_path.parent / f"tts_seg_{i:03d}.mp3"
                try:
                    tts_synthesize(text=text, out_path=seg_out, provider=provider, emotion=emotion)
                    cleanup_files.append(seg_out)
                except Exception as e:
                    if fallback:
                        try:
                            tts_synthesize(text=text, out_path=seg_out, provider=fallback, emotion=emotion)
                            cleanup_files.append(seg_out)
                        except Exception as e2:
                            return "", f"TTS failed: {e}; Fallback failed: {e2}"
                    else:
                        return "", f"TTS failed: {e}"

                if not seg_out.exists():
                     return "", "TTS file not generated"

                # Adjust duration
                dur = processor.get_audio_duration(str(seg_out))
                slot = max(0.1, end - start)
                
                final_seg_path = seg_out
                
                if dur > slot + 0.1: # Allow small tolerance
                    # Speed up
                    factor = dur / slot
                    # Cap speedup to avoid chipmunk effect if possible, but timeline constraints are strict
                    adjusted_path = out_path.parent / f"tts_seg_{i:03d}_adj.mp3"
                    if processor.adjust_audio_speed(str(seg_out), str(adjusted_path), factor):
                         final_seg_path = adjusted_path
                         cleanup_files.append(adjusted_path)
                    else:
                         return "", "Audio speed adjustment failed"
                elif dur < slot - 0.1:
                    # Pad with silence
                    audio_segments.append(str(final_seg_path))
                    
                    pad = slot - dur
                    pad_file = out_path.parent / f"silence_pad_{i}_{int(time.time())}.mp3"
                    if processor.generate_silence(pad, str(pad_file)):
                        audio_segments.append(str(pad_file))
                        cleanup_files.append(pad_file)
                    
                    current_time = end
                    continue # Skip default append

                audio_segments.append(str(final_seg_path))
                current_time = end

            if not audio_segments:
                return "", "Empty timeline"

            # Merge all segments
            # Generate temp concat output without BGM first
            temp_voice = out_path.parent / f"voice_combined_{int(time.time())}.mp3"
            if not processor.concat_audio_files(audio_segments, str(temp_voice)):
                return "", "Audio concatenation failed"
            
            cleanup_files.append(temp_voice)

            # Mix with BGM
            if self.bgm_path and Path(self.bgm_path).exists():
                # Use ffmpeg amix
                # ffmpeg -i voice.mp3 -i bgm.mp3 -filter_complex "[1:a]volume=0.2[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2" out.mp3
                ffmpeg = FFmpegUtils.get_ffmpeg()
                if ffmpeg:
                     cmd = [
                         ffmpeg, "-y",
                         "-i", str(temp_voice),
                         "-i", self.bgm_path,
                         "-filter_complex", "[1:a]volume=0.2[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0.5",
                         "-c:a", "libmp3lame",
                         "-q:a", "2",
                         str(out_path)
                     ]
                     ok, err = FFmpegUtils.run_cmd(cmd)
                     if not ok:
                         # Fallback to just voice
                         import shutil
                         shutil.copy2(temp_voice, out_path)
                else:
                    import shutil
                    shutil.copy2(temp_voice, out_path)
            else:
                import shutil
                shutil.copy2(temp_voice, out_path)

            return str(out_path), ""
            
        finally:
            # Cleanup temp files
            for f in cleanup_files:
                try:
                    if f.exists(): os.remove(f)
                except:
                    pass

    def _compose_photo_video(self, timeline: list[dict], audio_path: str, out_path: Path) -> str:
        ffmpeg = FFmpegUtils.get_ffmpeg()
        if not ffmpeg:
            self.emit_log("FFmpeg not found")
            return ""

        cleanup_files = []
        
        try:
            if not self.images:
                self.emit_log("No images provided")
                return ""

            # Determine durations
            if self.image_durations and len(self.image_durations) == len(self.images):
                durations = [max(0.1, float(d)) for d in self.image_durations]
            else:
                durations = [
                    max(0.1, float(seg.get("end", 0)) - float(seg.get("start", 0)))
                    for seg in timeline
                ]
                if not durations:
                    durations = [max(0.1, float(self.total_duration) / len(self.images))] * len(self.images)

            # Adjust durations to match audio if exists
            # (In FFmpeg workflow, we usually build video to match audio length or loop video)
            # Here we follow original logic: scale video durations to match audio.
            audio_duration = 0.0
            if audio_path and Path(audio_path).exists():
                audio_duration = FFmpegUtils.get_duration(audio_path)
            
            if audio_duration > 0 and sum(durations) > 0:
                factor = audio_duration / sum(durations)
                durations = [max(0.1, d * factor) for d in durations]

            video_segments = []
            
            fps = 24
            try:
                fps = int(getattr(config, "PHOTO_VIDEO_FPS", 24) or 24)
            except Exception:
                fps = 24

            for i, dur in enumerate(durations):
                img_path = self.images[i % len(self.images)]
                temp_seg = out_path.parent / f"v_seg_{i}_{int(time.time())}.mp4"
                
                # Ken Burns Loop + Zoom
                # zoompan: 
                #   z='min(zoom+0.0015,1.5)' : Zoom in slowly
                #   d=25*dur : Duration in frames (approx, assume 25fps for calc, but actual fps set in output)
                #   s=1080x1920 : Output size
                #   fps=fps : Output fps
                # Note: zoompan requires input frames. Image is 1 frame.
                # We loop image to needed duration.
                
                # Filter chain:
                # 1. scale/crop to aspect ratio first to avoid distortion in zoompan? 
                #    Actually zoompan resets SAR/DAR sometimes.
                #    Best practice: Pad/Crop to 1080p, then zoompan? 
                #    Or just zoompan directly on image.
                # Let's try direct zoompan on input image loop.
                
                frames = int(dur * fps)
                
                # Randomize zoom direction (in or out)
                # Zoom In: z='min(zoom+0.0015,1.5)'
                # Zoom Out: z='if(eq(on,1),1.5,max(1.0,zoom-0.0015))' ... complex init.
                # Keep simple: Always Zoom In for now.
                
                # s=1080x1920
                
                # Construct filter
                # We need input loop. -loop 1 -t duration
                
                # zoompan logic:
                # z='min(zoom+0.002,1.2)' -> 0.002 per frame. 25fps -> 0.05 per sec. 5 sec -> 0.25 zoom. 1.0 -> 1.25. (Nice slow zoom)
                
                zoom_speed = 0.0015
                vf = (
                    f"scale=1080*2:-1," # Scale up first for quality? Or just use raw.
                    f"zoompan=z='min(zoom+{zoom_speed},1.5)':d={frames}:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
                )
                
                # Ensure even numbers for encoders (yuv420p)
                vf += ",setsar=1"
                
                cmd = [
                    ffmpeg, "-y",
                    "-loop", "1",
                    "-t", str(dur),
                    "-i", str(img_path),
                    "-vf", vf,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-pix_fmt", "yuv420p",
                    str(temp_seg)
                ]
                
                ok, err = FFmpegUtils.run_cmd(cmd)
                if ok:
                    video_segments.append(str(temp_seg))
                    cleanup_files.append(temp_seg)
                else:
                    self.emit_log(f"Segment {i} generation failed: {err}")
                    pass # Skip? Or fail?

            if not video_segments:
                return ""

            # Concat video segments
            temp_video = out_path.parent / f"video_combined_{int(time.time())}.mp4"
            
            # Create list file
            list_path = out_path.parent / f"concat_v_list_{int(time.time())}.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for p in video_segments:
                    safe_path = Path(p).resolve().as_posix().replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
            cleanup_files.append(list_path)

            cmd_concat = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(temp_video)
            ]
            ok, err = FFmpegUtils.run_cmd(cmd_concat)
            if not ok:
                self.emit_log(f"Video concat failed: {err}")
                return ""
            cleanup_files.append(temp_video)

            # Merge with audio
            if audio_path and Path(audio_path).exists():
                cmd_merge = [
                    ffmpeg, "-y",
                    "-i", str(temp_video),
                    "-i", str(audio_path),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest", # Stop when shortest stream ends (usually video or audio)
                    str(out_path)
                ]
                ok, err = FFmpegUtils.run_cmd(cmd_merge)
                if not ok:
                     self.emit_log(f"Merge audio failed: {err}")
                     return ""
            else:
                import shutil
                shutil.copy2(temp_video, out_path)

            return str(out_path)
        except Exception as e:
            self.emit_log(f"Photo video composition exception: {e}")
            return ""
        finally:
            for f in cleanup_files:
                try:
                    if os.path.exists(f): os.remove(f)
                except:
                    pass

    def _burn_subtitles_ffmpeg(self, *, input_video_path: str, srt_path: str) -> str:
        """使用 ffmpeg 将 srt 字幕烧录到视频中。"""
        in_path = (input_video_path or "").strip()
        sub_path = (srt_path or "").strip()
        if not in_path or not sub_path:
            return ""

        try:
            if not bool(getattr(config, "SUBTITLE_BURN_ENABLED", True)):
                return ""
        except Exception:
            pass

        import shutil
        import subprocess

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return ""

        in_p = Path(in_path)
        out_path = str((in_p.parent / (Path(in_path).stem + "_带字幕.mp4")).resolve())

        # 字幕样式
        v_h = self._get_video_height(in_path)
        try:
            font_name = (getattr(config, "SUBTITLE_FONT_NAME", "Microsoft YaHei UI") or "Microsoft YaHei UI").strip()
        except Exception:
            font_name = "Microsoft YaHei UI"

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
            outline = int(max(0, outline_px))
        else:
            base_ratio = 0.09
            try:
                outline_min = int(getattr(config, "SUBTITLE_OUTLINE_MIN", 2) or 2)
            except Exception:
                outline_min = 2
            try:
                outline_max = int(getattr(config, "SUBTITLE_OUTLINE_MAX", 10) or 10)
            except Exception:
                outline_max = 10
            adaptive_min = min(outline_min, max(1, int(round(font_size * 0.06))))
            adaptive_max = max(1, min(outline_max, int(round(font_size * 0.30))))
            outline = int(max(adaptive_min, min(adaptive_max, round(font_size * base_ratio))))

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
            subprocess.run(cmd, check=True, capture_output=True)
            return out_path
        except Exception:
            return ""

    def _compress_for_tiktok(self, input_video_path: str) -> str:
        """输出前压缩到 TikTok 推荐码率。"""
        in_path = (input_video_path or "").strip()
        if not in_path:
            return ""

        import shutil
        import subprocess

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            try:
                import imageio_ffmpeg  # type: ignore
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_path = None
        if not ffmpeg_path:
            self.emit_log("⚠️ 未找到 ffmpeg，跳过压缩")
            return ""

        in_p = Path(in_path)
        out_path = str((in_p.parent / (in_p.stem + "_tiktok.mp4")).resolve())

        v_bitrate = str(getattr(config, "TIKTOK_VIDEO_BITRATE", "3500k") or "3500k")
        v_maxrate = str(getattr(config, "TIKTOK_MAXRATE", v_bitrate) or v_bitrate)
        v_bufsize = str(getattr(config, "TIKTOK_BUFSIZE", "7000k") or "7000k")
        a_bitrate = str(getattr(config, "TIKTOK_AUDIO_BITRATE", "128k") or "128k")

        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            in_path,
            "-c:v",
            "libx264",
            "-b:v",
            v_bitrate,
            "-maxrate",
            v_maxrate,
            "-bufsize",
            v_bufsize,
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            a_bitrate,
            "-movflags",
            "+faststart",
            out_path,
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return out_path if Path(out_path).exists() else ""
        except Exception:
            self.emit_log("⚠️ TikTok 压缩失败，使用原视频")
            return ""

    def _get_video_height(self, video_path: str) -> int:
        try:
            import subprocess
            import json
            ffprobe = "ffprobe"
            cmd = [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=height",
                "-of",
                "json",
                str(Path(video_path).resolve()),
            ]
            res = subprocess.run(cmd, check=True, capture_output=True)
            data = json.loads(res.stdout.decode("utf-8", errors="ignore"))
            streams = data.get("streams") or []
            if streams:
                return int(streams[0].get("height") or 1080)
        except Exception:
            pass
        return 1080

    def _save_srt_from_timeline(self, timeline: list[dict], out_path: Path) -> str:
        try:
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
            out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
            return str(out_path)
        except Exception:
            return ""

    def _fmt_srt_ts(self, seconds: float) -> str:
        ms = int(max(0.0, seconds) * 1000)
        h = ms // 3600000
        ms = ms % 3600000
        m = ms // 60000
        ms = ms % 60000
        s = ms // 1000
        ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _save_text(self, path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((text or "").strip() + "\n", encoding="utf-8")
        except Exception:
            pass

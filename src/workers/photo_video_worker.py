"""图文成片 Worker（Photo-to-Video Engine）

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
from datetime import datetime
import math
from pathlib import Path
from typing import Any

import config
from workers.base_worker import BaseWorker
from tts import synthesize as tts_synthesize

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
    """图文成片 Worker。"""

    def __init__(
        self,
        images: list[str] | None = None,
        product_desc: str = "",
        output_dir: str = "",
        image_durations: list[float] | None = None,
        role_prompt: str = "",
        model: str = "",
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
        video_path = self._compose_photo_video(timeline, audio_path, out_dir / self._name_video)
        if not video_path:
            self.emit_finished(False, "图文成片失败")
            return

        # 可选：烧录字幕
        if srt_path:
            burned = self._burn_subtitles_ffmpeg(input_video_path=video_path, srt_path=str(srt_path))
            if burned:
                video_path = burned

        compressed = self._compress_for_tiktok(video_path)
        if compressed:
            video_path = compressed

        self.data_signal.emit({"video": str(video_path), "srt": str(srt_path) if srt_path else ""})
        self.emit_finished(True, "图文成片完成")

    def _prepare_output_dir(self) -> Path:
        base = Path(self.output_dir or getattr(config, "OUTPUT_DIR", Path("Output"))) / "Photo_Videos"
        base.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = base / ts
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _generate_timeline(self) -> list[dict]:
        try:
            import openai

            api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
            if not api_key:
                self.emit_log("AI_API_KEY 未配置")
                return []

            base_url = ((getattr(config, "AI_BASE_URL", "") or "").strip() or "https://api.deepseek.com")
            use_model = self.model or (getattr(config, "AI_MODEL", "") or "deepseek-chat")

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
                "- Emotion must be one of: happy, sad, angry, surprise, neutral.\n"
                "- Output STRICT JSON object with key timeline only.\n\n"
                "JSON schema:\n"
                "{\n"
                "  \"timeline\": [\n"
                "    {\"start\":0, \"end\":3, \"text\":\"...\", \"emotion\":\"happy\"}\n"
                "  ]\n"
                "}\n\n"
                f"Product description:\n{self.product_desc}\n"
            )

            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model=use_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )

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
        try:
            from moviepy import AudioFileClip, AudioClip, concatenate_audioclips, CompositeAudioClip
        except Exception as e:
            return "", f"MoviePy 依赖缺失：{e}"

        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()

        clips = []
        current_time = 0.0

        def _silence(duration: float):
            if duration <= 0:
                return None
            return AudioClip(lambda t: 0, duration=duration, fps=44100)

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

            if start > current_time:
                gap = start - current_time
                s = _silence(gap)
                if s:
                    clips.append(s)
                    current_time += gap

            seg_out = out_path.parent / f"tts_seg_{i:03d}.mp3"
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

        # BGM 混音（可选）
        if self.bgm_path:
            try:
                bgm = AudioFileClip(self.bgm_path).with_volume_scaled(0.2)
                bgm = bgm.with_duration(final_audio.duration)
                final_audio = CompositeAudioClip([bgm, final_audio])
            except Exception:
                pass

        final_audio.write_audiofile(str(out_path), logger=None)
        return str(out_path), ""

    def _compose_photo_video(self, timeline: list[dict], audio_path: str, out_path: Path) -> str:
        try:
            from moviepy import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, ColorClip
        except Exception as e:
            self.emit_log(f"MoviePy 依赖缺失：{e}")
            return ""

        target_w, target_h = 1080, 1920

        def _make_clip(img_path: str, duration: float):
            clip = ImageClip(img_path).with_duration(duration)
            try:
                clip = clip.resized(height=target_h)
                if clip.w < target_w:
                    clip = clip.resized(width=target_w)
            except Exception:
                pass

            base_w, base_h = clip.w, clip.h

            def _ease(t: float) -> float:
                if duration <= 0.1:
                    return 0.0
                x = max(0.0, min(1.0, t / duration))
                return 0.5 - 0.5 * math.cos(math.pi * x)

            zoom_max = 0.08

            def _scale(t: float) -> float:
                return 1.0 + zoom_max * _ease(t)

            try:
                clip = clip.resized(lambda t: _scale(t))
            except Exception:
                pass

            def _pos(t: float):
                s = _scale(t)
                w = base_w * s
                h = base_h * s
                pan = _ease(t)
                # 位置范围：[target - size, 0]
                x = (target_w - w) * pan
                y = (target_h - h) * (1.0 - pan)
                return (x, y)

            try:
                clip = clip.with_position(_pos)
            except Exception:
                pass

            # 叠到黑底上，确保尺寸一致
            bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).with_duration(duration)
            return CompositeVideoClip([bg, clip], size=(target_w, target_h))

        try:
            clips = []
            if not self.images:
                self.emit_log("未提供图片，无法合成")
                return ""
            if self.image_durations and len(self.image_durations) == len(self.images):
                durations = [max(0.1, float(d)) for d in self.image_durations]
            else:
                durations = [
                    max(0.1, float(seg.get("end", 0)) - float(seg.get("start", 0)))
                    for seg in timeline
                ]
                if not durations:
                    durations = [max(0.1, float(self.total_duration) / len(self.images))] * len(self.images)

            audio_duration = None
            if audio_path:
                try:
                    audio = AudioFileClip(audio_path)
                    audio_duration = float(getattr(audio, "duration", 0.0) or 0.0)
                except Exception:
                    audio = None
            else:
                audio = None

            if audio_duration and sum(durations) > 0:
                factor = audio_duration / sum(durations)
                durations = [max(0.1, d * factor) for d in durations]

            for i, dur in enumerate(durations):
                img_path = self.images[i % len(self.images)]
                clips.append(_make_clip(img_path, dur))

            video = concatenate_videoclips(clips, method="compose")
            if audio is not None:
                try:
                    video = video.with_audio(audio)
                except Exception:
                    pass
            fps = 24
            try:
                fps = int(getattr(config, "PHOTO_VIDEO_FPS", 24) or 24)
            except Exception:
                fps = 24
            video.write_videofile(str(out_path), codec="libx264", audio_codec="aac", fps=fps, logger=None)
            return str(out_path)
        except Exception as e:
            self.emit_log(f"图文成片失败：{e}")
            return ""

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

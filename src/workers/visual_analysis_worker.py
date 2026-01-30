"""视觉分析 Worker

流程：
- 视频抽帧（每 N 秒）
- Base64 编码
- 调用视觉模型分析
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from workers.base_worker import BaseWorker
from api.visual_ai_assistant import VisualAIAssistant
from utils.ffmpeg import FFmpegUtils
import config

logger = logging.getLogger(__name__)


class VisualAnalysisWorker(BaseWorker):
    """视频拆解与脚本反推 Worker。"""

    def __init__(
        self,
        video_path: str,
        interval_sec: float = 2.0,
        prompt: str = "",
        model: str = "",
        provider: str = "",
        role_prompt: str = "",
    ) -> None:
        super().__init__()
        self.video_path = (video_path or "").strip()
        self.interval_sec = max(0.5, float(interval_sec or 2.0))
        self.prompt = (prompt or "").strip()
        self.model = (model or "").strip()
        self.provider = (provider or "").strip()
        self.role_prompt = (role_prompt or "").strip()

    def _run_impl(self) -> None:
        if not self.video_path:
            self.emit_finished(False, "请选择视频文件")
            return

        vp = Path(self.video_path)
        if not vp.exists():
            self.emit_finished(False, "视频文件不存在")
            return

        try:
            self.emit_log("🎞️ 开始抽帧...")
            frames = self._extract_frames()
            if not frames:
                self.emit_finished(False, "抽帧失败或未获取到帧")
                return

            self.emit_log(f"🧠 已抽帧 {len(frames)} 张，开始视觉分析...")
            assistant = VisualAIAssistant(model=self.model, provider=self.provider, role_prompt=self.role_prompt)
            result_text = assistant.analyze_frames(frames, self.prompt)
            if not result_text:
                self.emit_finished(False, "视觉模型未返回有效内容")
                return

            self.data_signal.emit(result_text)
            self.emit_finished(True, "视觉分析完成")
        except Exception as e:
            logger.error(f"视觉分析失败: {e}", exc_info=True)
            self.emit_finished(False, f"视觉分析失败：{e}")

    def _extract_frames(self) -> List[str]:
        """抽帧并返回 base64 列表。"""
        frames_b64: List[str] = []
        out_dir = self._prepare_output_dir()

        ffmpeg = FFmpegUtils.get_ffmpeg()
        if not ffmpeg:
            logger.error("FFmpeg not found")
            return []

        try:
            # fps=1/interval_sec
            fps = 1.0 / self.interval_sec
            output_pattern = str(out_dir / "frame_%03d.jpg")
            
            cmd = [
                ffmpeg, "-y",
                "-i", self.video_path,
                "-vf", f"fps={fps}",
                "-q:v", "2",
                output_pattern
            ]
            
            ok, err = FFmpegUtils.run_cmd(cmd)
            if not ok:
                 logger.error(f"Frame extraction failed: {err}")
                 return []

            for img_file in sorted(out_dir.glob("frame_*.jpg")):
                if self.should_stop():
                    break
                try:
                    b64 = base64.b64encode(img_file.read_bytes()).decode("utf-8")
                    frames_b64.append(b64)
                except Exception:
                    pass
            
            return frames_b64

        except Exception as e:
            logger.error(f"抽帧异常: {e}")
            return []

    def _prepare_output_dir(self) -> Path:
        base_dir = Path(getattr(config, "OUTPUT_DIR", Path("Output"))) / "Visual_Lab"
        base_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = base_dir / ts
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

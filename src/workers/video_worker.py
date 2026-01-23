"""
Video Processing Worker - runs in QThread
"""
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from PyQt5.QtCore import pyqtSignal

import config
from workers.base_worker import BaseWorker
from utils.excel_export import export_video_processing_log


class VideoWorker(BaseWorker):
    """Worker for batch video processing"""

    item_finished_signal = pyqtSignal(str, bool, str)  # Path, Success, Message
    
    def __init__(
        self, 
        video_files: List[str] = None, 
        trim_head: float = 0.5,
        trim_tail: float = 0.5,
        speed: float | None = None,
        apply_flip: bool = True,
        deep_remix_enabled: bool = False,
        micro_zoom: bool = True,
        add_noise: bool = False,
        strip_metadata: bool = True,
        parallel_jobs: int = 1,
        max_retries: int = 0,
        output_dir: str = None,
        **kwargs
    ):
        """
        Initialize video worker
        
        Args:
            video_files: List of video file paths to process
            trim_head: Seconds to cut from start
            trim_tail: Seconds to cut from end
            speed: Speed multiplier
            apply_flip: Whether to horizontally flip
            output_dir: Custom output directory
            **kwargs: Additional parameters
        """
        super().__init__()
        self.video_files = video_files or []
        self.trim_head = trim_head
        self.trim_tail = trim_tail
        self.speed = None if speed is None else speed
        self.apply_flip = apply_flip

        self.deep_remix_enabled = deep_remix_enabled
        self.micro_zoom = micro_zoom
        self.add_noise = add_noise
        self.strip_metadata = strip_metadata
        self.output_dir = output_dir

        try:
            self.parallel_jobs = max(1, int(parallel_jobs))
        except Exception:
            self.parallel_jobs = 1

        try:
            self.max_retries = max(0, int(max_retries))
        except Exception:
            self.max_retries = 0

        # 懒加载：避免启动阶段导入 moviepy/numpy 等重依赖
        self.processor = None
        self.processing_results = []
    
    def _run_impl(self):
        """Execute video processing"""
        self.emit_log("开始批量视频处理...")
        self.emit_progress(0)

        # Log parameters
        self.emit_log(
            f"参数设置：变速=无级随机(1.10-1.35/秒)，去头={self.trim_head}s，去尾={self.trim_tail}s，翻转={'是' if self.apply_flip else '否'}"
        )
        self.emit_log(
            f"深度去重：{'开' if self.deep_remix_enabled else '关'}"
            f"（微缩放={'开' if self.micro_zoom else '关'}，加噪点={'开' if self.add_noise else '关'}，清除元数据={'开' if self.strip_metadata else '关'}）"
        )
            
        total_videos = len(self.video_files)

        if not self.video_files:
            self.emit_error("未提供待处理的视频文件")
            self.emit_finished(False, "未提供视频文件")
            return

        self.emit_log(f"待处理视频：{total_videos} 个")

        success_count = 0
        fail_count = 0

        # 执行处理（支持并行）
        completed = 0
        self.processing_results = []

        if self.parallel_jobs <= 1:
            for idx, video_path in enumerate(self.video_files, 1):
                if self.should_stop():
                    self.emit_finished(False, "任务已停止")
                    return
                self.emit_log(f"▶ [{idx}/{total_videos}] 处理：{Path(video_path).name}")
                _, (ok, msg) = self._process_one_with_retry(video_path)
                if ok:
                    success_count += 1
                    self.emit_log(f"✅ 完成 [{idx}/{total_videos}]：{msg}")
                    self.item_finished_signal.emit(video_path, True, msg)
                else:
                    fail_count += 1
                    self.emit_log(f"❌ 失败 [{idx}/{total_videos}]：{msg[:100]}")
                    self.item_finished_signal.emit(video_path, False, msg)
                self.processing_results.append({
                    "input": video_path,
                    "ok": ok,
                    "message": msg,
                })
                completed += 1
                percent = int(completed / total_videos * 100)
                self.emit_progress(percent)
                self.emit_log(f"进度：{percent}%")
        else:
            with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
                future_map = {executor.submit(self._process_one_with_retry, p): p for p in self.video_files}
                for future in as_completed(future_map):
                    if self.should_stop():
                        try:
                            for f in future_map:
                                f.cancel()
                        except Exception:
                            pass
                        self.emit_finished(False, "任务已停止")
                        return
                    try:
                        _path, (ok, msg) = future.result()
                    except Exception as e:
                        ok, msg = False, str(e)
                        _path = future_map.get(future, "")

                    name = Path(_path).name if _path else "(unknown)"
                    if ok:
                        success_count += 1
                        self.emit_log(f"✅ 完成：{msg}")
                        self.item_finished_signal.emit(_path, True, msg)
                    else:
                        fail_count += 1
                        self.emit_log(f"❌ 失败：{msg[:100]}")
                        self.item_finished_signal.emit(_path, False, msg)

                    self.processing_results.append({
                        "input": _path,
                        "ok": ok,
                        "message": msg,
                    })
                    completed += 1
                    percent = int(completed / total_videos * 100)
                    self.emit_progress(percent)
                    self.emit_log(f"进度：{percent}%")

        self.emit_log(f"处理完成：成功 {success_count} / 失败 {fail_count}")
        self.emit_progress(100)
        self.emit_finished(True, "处理完成")


    def _guess_output_filename(self, input_path: str) -> str:
        """猜测输出文件名（带后缀）"""
        try:
            p = Path(input_path)
            suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
            return f"{p.stem}{suffix}{p.suffix}"
        except Exception:
            return ""

    def _process_one_with_retry(self, video_path: str):
        """带重试的视频处理逻辑，支持 self 作用域。"""
        last_msg = ""
        for attempt in range(self.max_retries + 1):
            if self.should_stop():
                return video_path, (False, "已停止")
            from video.processor import VideoProcessor
            processor = VideoProcessor()
            ok, msg = processor.process_video(
                video_path,
                trim_head=self.trim_head,
                trim_tail=self.trim_tail,
                speed=self.speed,
                apply_flip=self.apply_flip,
                deep_remix_enabled=self.deep_remix_enabled,
                micro_zoom=self.micro_zoom,
                add_noise=self.add_noise,
                strip_metadata=self.strip_metadata,
                custom_output_dir=self.output_dir,
            )
            last_msg = msg
            if ok:
                return video_path, (True, msg)
            if attempt < self.max_retries:
                self.emit_log(f"[WARN] 失败重试 {attempt + 1}/{self.max_retries}：{Path(video_path).name}")
        return video_path, (False, last_msg)


# =================== 半人马拼接 Worker ===================
class CyborgComposeWorker(BaseWorker):
    """半人马拼接 Worker（FFmpeg 一次性拼接）。"""

    def __init__(
        self,
        intro_path: str,
        mid_path: str,
        outro_path: str,
        output_dir: str | None = None,
        do_deep_remix: bool = False,
    ) -> None:
        super().__init__()
        self.intro_path = (intro_path or "").strip()
        self.mid_path = (mid_path or "").strip()
        self.outro_path = (outro_path or "").strip()
        self.output_dir = output_dir
        self.do_deep_remix = bool(do_deep_remix)

    def _run_impl(self) -> None:
        """执行半人马拼接并回传结果。"""
        try:
            if not self.intro_path or not self.mid_path or not self.outro_path:
                self.emit_finished(False, "半人马拼接缺少素材路径")
                return

            self.emit_log("🧩 半人马拼接：开始处理...")
            self.emit_progress(20)

            from video.processor import VideoProcessor

            processor = VideoProcessor()
            ok, msg = processor.compose_cyborg_video(
                intro_path=self.intro_path,
                mid_path=self.mid_path,
                outro_path=self.outro_path,
                custom_output_dir=self.output_dir,
            )

            if not ok:
                self.emit_finished(False, msg)
                return

            final_path = msg
            self.emit_progress(80)

            # Deep Remix Logic
            if self.do_deep_remix:
                try:
                    self.emit_log("🔨 正在进行深度混剪 (Remix)...")
                    ok_remix, res_remix = processor.process_video_ffmpeg_remix(
                        input_path=final_path, 
                        custom_output_dir=self.output_dir
                    )
                    if ok_remix:
                        final_path = res_remix
                        self.emit_log("✅ 深度混剪完成")
                    else:
                        self.emit_log(f"⚠️ 深度混剪失败 ({res_remix})，保留拼接原片")
                except Exception as e:
                    self.emit_log(f"⚠️ 深度混剪异常：{e}，保留拼接原片")

            self.emit_progress(100)
            self.emit_finished(True, final_path)

        except Exception as e:
            self.emit_log(f"❌ 半人马拼接异常：{e}")
            self.emit_finished(False, f"半人马拼接异常：{e}")

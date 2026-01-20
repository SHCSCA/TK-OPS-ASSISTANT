"""
Video Processing Worker - runs in QThread
"""
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import config
from workers.base_worker import BaseWorker
from utils.excel_export import export_video_processing_log


class VideoWorker(BaseWorker):
    """Worker for batch video processing"""
    
    def __init__(
        self, 
        video_files: List[str] = None, 
        trim_head: float = 0.5,
        trim_tail: float = 0.5,
        speed: float = 1.1,
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
        self.speed = speed
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
            f"参数设置：速度={self.speed}x，去头={self.trim_head}s，去尾={self.trim_tail}s，翻转={'是' if self.apply_flip else '否'}"
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
    ) -> None:
        super().__init__()
        self.intro_path = (intro_path or "").strip()
        self.mid_path = (mid_path or "").strip()
        self.outro_path = (outro_path or "").strip()
        self.output_dir = output_dir

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

            self.emit_progress(90)
            if ok:
                self.emit_log(f"✅ 半人马拼接完成：{msg}")
                try:
                    self.data_signal.emit({"output": msg})
                except Exception:
                    pass
                self.emit_progress(100)
                self.emit_finished(True, "半人马拼接完成")
            else:
                self.emit_log(f"❌ 半人马拼接失败：{msg}")
                self.emit_finished(False, msg)
        except Exception as e:
            self.emit_log(f"❌ 半人马拼接异常：{e}")
            self.emit_finished(False, f"半人马拼接异常：{e}")
        else:
            self.emit_log(f"并行模式：{self.parallel_jobs} 线程处理")
            completed = 0
            with ThreadPoolExecutor(max_workers=self.parallel_jobs) as pool:
                futures = {pool.submit(self._process_one_with_retry, p): p for p in self.video_files}

                for fut in as_completed(futures):
                    completed += 1

                    if self.should_stop():
                        # 无法强制中断正在运行的 ffmpeg/moviepy，停止继续等待即可
                        self.emit_log("已请求停止：等待中的任务将不再汇报（正在处理的视频可能仍会完成输出）。")
                        break

                    input_path = ""
                    start_ts = time.perf_counter()
                    try:
                        path, (success, message) = fut.result()
                    except Exception as e:
                        path = ""
                        success, message = False, f"✗ 处理失败：{e}"
                    elapsed = time.perf_counter() - start_ts

                    # 并行模式下尽量记录耗时（粗略：以 future 完成为准）
                    try:
                        input_path = futures.get(fut, "")
                    except Exception:
                        input_path = ""

                    self.emit_log(message)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1

                    input_file = input_path or path
                    input_name = Path(input_file).name if input_file else ""
                    self.processing_results.append(
                        {
                            "status": "成功" if success else "失败",
                            "input": input_name,
                            "output": self._guess_output_filename(input_file) if input_file else "",
                            "elapsed": float(f"{elapsed:.2f}") if elapsed else 0.0,
                            "error": "" if success else message,
                            # 兼容导出字段
                            "input_filename": input_name,
                            "output_filename": self._guess_output_filename(input_file) if input_file else "",
                            "original_duration": 0,
                            "processed_duration": 0,
                            "process_time": f"{elapsed:.2f}" if elapsed else "",
                            "notes": message,
                            # 兼容旧字段
                            "success": success,
                            "message": message,
                        }
                    )

                    progress = int((completed / total_videos) * 100)
                    self.emit_progress(progress)
            
        # Summary
        self.emit_log("\n✓ 处理完成！")
        self.emit_log(f"  成功：{success_count}")
        self.emit_log(f"  失败：{fail_count}")

        # Export results
        try:
            export_file = export_video_processing_log(self.processing_results, emit_log=self.emit_log)
            self.emit_log(f"已导出结果到：{export_file}")
        except Exception as e:
            self.emit_log(f"导出结果失败：{str(e)}")

        try:
            self.data_signal.emit(self.processing_results)
        except Exception:
            pass

        self.emit_progress(100)
        self.emit_finished(True, "视频处理完成")
    
    def add_video_file(self, video_path: str) -> bool:
        """
        Add a video file to processing queue
        
        Args:
            video_path: Path to video file
            
        Returns:
            True if file was added
        """
        video_file = Path(video_path)
        if video_file.exists() and video_file.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
            self.video_files.append(str(video_file))
            return True
        return False
    
    def clear_queue(self):
        """Clear the processing queue"""
        self.video_files = []
        self.processing_results = []

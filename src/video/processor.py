"""
Video processor using moviepy for V1.0
"""
from pathlib import Path
from typing import Tuple, Optional
import time
import random
import shutil
import subprocess
import config


class VideoProcessor:
    """基于 moviepy 的视频处理器"""
    
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0

    def _lazy_moviepy(self):
        """延迟导入 moviepy，避免应用启动阶段拉起重依赖（numpy/imageio/ffmpeg）。"""
        try:
            # Upgrade to moviepy 2.0+
            from moviepy import VideoFileClip, vfx
            return VideoFileClip, vfx
        except Exception as e:
            raise ImportError(
                "无法导入 moviepy（视频处理依赖）。\n"
                "请先运行 start.bat 安装依赖，或在当前环境执行：pip install -r requirements.txt\n"
                f"原始错误：{e}"
            )
    
    def _find_ffmpeg(self) -> Optional[str]:
        """查找 ffmpeg 可执行文件路径（moviepy 依赖它，但环境可能不完整）。"""
        return shutil.which("ffmpeg")

    def _run_ffmpeg(self, args: list) -> Tuple[bool, str]:
        """运行 ffmpeg（不抛异常，返回成功与错误信息）。"""
        try:
            proc = subprocess.run(args, capture_output=True, text=True)
            if proc.returncode == 0:
                return True, ""
            err = (proc.stderr or proc.stdout or "").strip()
            return False, err[-2000:] if err else "ffmpeg 执行失败（无输出）"
        except Exception as e:
            return False, str(e)

    def process_video(
        self,
        input_path: str,
        output_path: str = None,
        trim_head: float | None = None,
        trim_tail: float | None = None,
        speed: float | None = None,
        apply_flip: bool = True,
        deep_remix_enabled: bool = False,
        micro_zoom: bool = True,
        add_noise: bool = False,
        strip_metadata: bool = True,
        custom_output_dir: str = None,
    ) -> Tuple[bool, str]:
        """
        对视频进行去重处理 (剪辑/加速/翻转)
        
        参数:
            input_path: 输入文件路径
            output_path: 输出文件路径 (如果为 None 则自动生成)
            trim_head: 去片头秒数
            trim_tail: 去片尾秒数
            speed: 加速倍率 (1.1 = 1.1倍速)
            apply_flip: 是否水平翻转
            custom_output_dir: 自定义输出目录
            
        返回:
            (是否成功, 消息提示)
        """
        try:
            VideoFileClip, vfx = self._lazy_moviepy()
            input_file = Path(input_path)
            if not input_file.exists():
                return False, f"未找到输入文件: {input_path}"

            # 动态默认值：避免 import-time 常量导致“保存后不生效”
            if trim_head is None:
                trim_head = getattr(config, "VIDEO_TRIM_HEAD", 0.5)
            if trim_tail is None:
                trim_tail = getattr(config, "VIDEO_TRIM_TAIL", 0.5)
            if speed is None:
                speed = getattr(config, "VIDEO_SPEED_MULTIPLIER", 1.1)
            
            # Generate output path if not provided
            if output_path is None:
                stem = input_file.stem
                suffix = input_file.suffix
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{stem}{output_suffix}{suffix}"
                
                # Check custom output dir
                if custom_output_dir:
                    out_dir = Path(custom_output_dir)
                else:
                    out_dir = config.OUTPUT_DIR
                
                output_path = out_dir / output_filename
            else:
                output_path = Path(output_path)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            clip = None
            final_clip = None
            # Load video
            clip = VideoFileClip(input_path)
            original_duration = float(getattr(clip, "duration", 0) or 0)
            original_size = getattr(clip, "size", None)  # [w, h]
            
            # 1. Trim head/tail
            if trim_head > 0 or trim_tail > 0:
                trim_end = max(0, original_duration - trim_tail)
                clip = clip.subclipped(trim_head, trim_end)
            
            # 2. Horizontal flip (mirror)
            if apply_flip:
                clip = clip.with_effects([vfx.MirrorX()])
            
            # 3. Global speed up
            if speed != 1.0:
                clip = clip.with_speed_scaled(speed)

            # 4. Deep remix (micro zoom / subtle variations)
            # 说明：这里的目标不是“过度加工”，而是做轻量的、可控的差异化。
            if deep_remix_enabled and micro_zoom and original_size:
                try:
                    w, h = int(original_size[0]), int(original_size[1])
                    zoom_factor = random.uniform(1.01, 1.04)
                    clip = clip.resized(new_size=zoom_factor)
                    # 居中裁切回原尺寸，避免分辨率变化
                    clip = clip.cropped(
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                        width=w,
                        height=h,
                    )
                except Exception:
                    # 缩放失败不影响主流程
                    pass
            
            # 5. Write output (preserves audio with AAC codec)
            clip.write_videofile(
                str(output_path),
                logger=None,
                audio_codec='aac'
            )

            # 6. 可选：噪点滤镜 + 元数据清洗（ffmpeg）
            if deep_remix_enabled and (add_noise or strip_metadata):
                ffmpeg = self._find_ffmpeg()
                if not ffmpeg:
                    # 环境缺少 ffmpeg 时安全降级
                    pass
                else:
                    temp_path = output_path.with_name(output_path.stem + "_tmp" + output_path.suffix)

                    # 仅清元数据（不重新编码）
                    if strip_metadata and not add_noise:
                        ok, err = self._run_ffmpeg(
                            [
                                ffmpeg,
                                "-y",
                                "-i",
                                str(output_path),
                                "-map_metadata",
                                "-1",
                                "-c",
                                "copy",
                                str(temp_path),
                            ]
                        )
                        if ok:
                            try:
                                output_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                            try:
                                temp_path.replace(output_path)
                            except Exception:
                                pass
                        else:
                            # 失败则不影响主流程
                            try:
                                temp_path.unlink(missing_ok=True)
                            except Exception:
                                pass

                    # 加噪点需要重编码（同时可顺便清元数据）
                    if add_noise:
                        vf = "noise=alls=10:allf=t+u"
                        ok, err = self._run_ffmpeg(
                            [
                                ffmpeg,
                                "-y",
                                "-i",
                                str(output_path),
                                "-vf",
                                vf,
                                "-c:v",
                                "libx264",
                                "-preset",
                                "veryfast",
                                "-crf",
                                "23",
                                "-c:a",
                                "aac",
                                "-map_metadata",
                                "-1" if strip_metadata else "0",
                                str(temp_path),
                            ]
                        )
                        if ok:
                            try:
                                output_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                            try:
                                temp_path.replace(output_path)
                            except Exception:
                                pass
                        else:
                            try:
                                temp_path.unlink(missing_ok=True)
                            except Exception:
                                pass
            
            # Get final duration（尽量复用 clip 计算，减少二次打开文件）
            try:
                final_duration = float(getattr(clip, "duration", 0) or 0)
            except Exception:
                final_duration = 0.0

            # Clean up
            try:
                if final_clip is not None:
                    final_clip.close()
            except Exception:
                pass
            try:
                if clip is not None:
                    clip.close()
            except Exception:
                pass
            
            self.processed_count += 1
            message = f"✓ 处理成功: {input_file.name} ({original_duration:.1f}s → {final_duration:.1f}s)"
            return True, message
        
        except Exception as e:
            self.failed_count += 1
            return False, f"✗ 处理失败: {str(e)}"
    
    def batch_process(
        self,
        input_dir: str,
        extensions: Tuple[str, ...] = ('.mp4', '.avi', '.mov', '.mkv')
    ) -> dict:
        """
        批量处理文件夹内的视频
        
        参数:
            input_dir: 输入文件夹路径
            extensions: 要处理的文件后缀元组
            
        返回:
            处理结果字典
        """
        input_path = Path(input_dir)
        if not input_path.is_dir():
            return {"success": False, "message": "无效的文件夹"}
        
        video_files = [
            f for f in input_path.iterdir()
            if f.suffix.lower() in extensions
        ]
        
        results = []
        for video_file in video_files:
            success, message = self.process_video(str(video_file))
            results.append({
                "file": video_file.name,
                "success": success,
                "message": message
            })
        
        return {
            "success": True,
            "total": len(video_files),
            "processed": self.processed_count,
            "failed": self.failed_count,
            "results": results
        }

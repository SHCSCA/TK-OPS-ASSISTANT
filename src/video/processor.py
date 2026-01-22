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

    def _has_audio_stream(self, video_path: str) -> bool:
        """检测视频是否包含音轨（用于半人马拼接）。"""
        try:
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

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长 (sec)"""
        try:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                return 0.0
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            return float(proc.stdout.strip())
        except Exception:
            return 0.0

    def adjust_audio_speed(self, input_path: str, output_path: str, speed: float) -> bool:
        """调整音频速度 (atempo)"""
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg: return False
            
            # atempo limited to 0.5 to 2.0. Chain if needed.
            # Simplified: assuming speed is within reasonable range (0.5 - 10.0)
            # For > 2.0, need multiple filters.
            
            # We construct filter chain
            filter_str = ""
            remaining = speed
            while remaining > 2.0:
                filter_str += "atempo=2.0,"
                remaining /= 2.0
            while remaining < 0.5:
                filter_str += "atempo=0.5,"
                remaining /= 0.5
            
            filter_str += f"atempo={remaining}"
            
            cmd = [
                ffmpeg, "-y",
                "-i", str(input_path),
                "-filter:a", filter_str,
                "-vn", str(output_path)
            ]
            ok, err = self._run_ffmpeg(cmd)
            return ok
        except Exception:
            return False

    def generate_silence(self, duration: float, output_path: str) -> bool:
        """生成静音片段"""
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg: return False
            
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(duration),
                str(output_path)
            ]
            ok, err = self._run_ffmpeg(cmd)
            return ok
        except Exception:
            return False

    def concat_audio_files(self, file_paths: list[str], output_path: str) -> bool:
        """拼接音频文件列表 (concat demuxer)"""
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg: return False
            
            # Create list file
            list_path = Path(output_path).parent / f"concat_list_{int(time.time()*1000)}.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for p in file_paths:
                    # Escape path for ffmpeg concat demuxer
                    safe_path = str(Path(p).resolve()).replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
            
            cmd = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(output_path)
            ]
            ok, err = self._run_ffmpeg(cmd)
            
            # Cleanup list file
            try:
                os.remove(list_path)
            except:
                pass
                
            return ok
        except Exception:
            return False

    def merge_av(self, video_path: str, audio_path: str, output_path: str) -> Tuple[bool, str]:
        """合并音视频 (替换原音频)"""
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg: return False, "No ffmpeg"
            
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                str(output_path)
            ]
            ok, err = self._run_ffmpeg(cmd)
            if not ok: return False, err
            return True, str(output_path)
        except Exception as e:
            return False, str(e)

    def compose_cyborg_video(
        self,
        intro_path: str,
        mid_path: str,
        outro_path: str,
        output_path: str | None = None,
        custom_output_dir: str | None = None,
    ) -> Tuple[bool, str]:
        """“半人马”内容策略拼接：

        结构：[0-2秒 原创] + [中间 混剪] + [5-7秒 原创]
        使用 FFmpeg 一次性 concat，保证速度与稳定性。
        """
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                return False, "未检测到 ffmpeg，无法执行半人马拼接。"

            intro_file = Path(intro_path)
            mid_file = Path(mid_path)
            outro_file = Path(outro_path)
            if not intro_file.exists() or not mid_file.exists() or not outro_file.exists():
                return False, "半人马拼接失败：素材文件不存在。"

            if output_path is None:
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{mid_file.stem}_cyborg{output_suffix}{mid_file.suffix}"
                if custom_output_dir:
                    out_dir = Path(custom_output_dir)
                else:
                    out_dir = config.OUTPUT_DIR
                output_path = out_dir / output_filename
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            intro_sec = float(getattr(config, "CYBORG_INTRO_SEC", 2.0) or 2.0)
            outro_sec = float(getattr(config, "CYBORG_OUTRO_SEC", 2.0) or 2.0)

            has_audio = all([
                self._has_audio_stream(str(intro_file)),
                self._has_audio_stream(str(mid_file)),
                self._has_audio_stream(str(outro_file)),
            ])

            # 构造 filter_complex
            vf_parts = [
                f"[0:v]trim=0:{intro_sec},setpts=PTS-STARTPTS[v0]",
                "[1:v]setpts=PTS-STARTPTS[v1]",
                f"[2:v]trim=0:{outro_sec},setpts=PTS-STARTPTS[v2]",
            ]
            af_parts = []
            if has_audio:
                af_parts = [
                    f"[0:a]atrim=0:{intro_sec},asetpts=PTS-STARTPTS[a0]",
                    "[1:a]asetpts=PTS-STARTPTS[a1]",
                    f"[2:a]atrim=0:{outro_sec},asetpts=PTS-STARTPTS[a2]",
                ]

            concat_part = "[v0][v1][v2]concat=n=3:v=1:a=0[vout]"
            if has_audio:
                concat_part = "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vout][aout]"

            filter_complex = ";".join(vf_parts + af_parts + [concat_part])

            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(intro_file),
                "-i",
                str(mid_file),
                "-i",
                str(outro_file),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
            ]
            if has_audio:
                cmd.extend(["-map", "[aout]"])
            cmd.extend([
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                str(output_path),
            ])

            ok, err = self._run_ffmpeg(cmd)
            if not ok:
                return False, f"半人马拼接失败: {err}"
            return True, str(output_path)
        except Exception as e:
            return False, f"半人马拼接异常: {e}"

    def process_video_ffmpeg_remix(
        self,
        input_path: str,
        output_path: str | None = None,
        custom_output_dir: str | None = None,
    ) -> Tuple[bool, str]:
        """使用 FFmpeg 完成素材清洗（非线性变速 + 色彩微调 + 像素位移）。"""
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                return False, "未检测到 ffmpeg，无法执行素材清洗。"

            input_file = Path(input_path)
            if not input_file.exists():
                return False, f"未找到输入文件: {input_path}"

            if output_path is None:
                stem = input_file.stem
                suffix = input_file.suffix
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{stem}{output_suffix}{suffix}"
                if custom_output_dir:
                    out_dir = Path(custom_output_dir)
                else:
                    out_dir = config.OUTPUT_DIR
                output_path = out_dir / output_filename
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # === 非线性变速（心跳剪辑）===
            speed_min = float(getattr(config, "HEARTBEAT_SPEED_MIN", 0.9) or 0.9)
            speed_max = float(getattr(config, "HEARTBEAT_SPEED_MAX", 1.1) or 1.1)
            period = float(getattr(config, "HEARTBEAT_PERIOD_SEC", 4.0) or 4.0)
            # 速度曲线：1 + A * sin(2πt/period)
            amp = max(0.0, min(0.3, (speed_max - speed_min) / 2.0))
            setpts = f"setpts=PTS/(1+{amp}*sin(2*PI*t/{period}))"

            # === 光影重构（随机微调）===
            gamma = round(random.uniform(0.97, 1.03), 3)
            saturation = round(random.uniform(0.97, 1.03), 3)
            eq = f"eq=gamma={gamma}:saturation={saturation}"

            # === 像素级位移（放大 102% + 平移 2px）===
            shift = random.choice([-2, 2])
            scale = "scale=iw*1.02:ih*1.02"
            crop = f"crop=iw:ih:{shift}:0"

            vf = ",".join([setpts, eq, scale, crop])

            args = [
                ffmpeg,
                "-y",
                "-i",
                str(input_file),
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
                "-1",
                str(output_path),
            ]

            ok, err = self._run_ffmpeg(args)
            if not ok:
                return False, f"素材清洗失败: {err}"

            return True, str(output_path)
        except Exception as e:
            return False, f"素材清洗异常: {e}"

    def _get_duration(self, video_path: str) -> float:
        """获取视频时长（秒）。"""
        try:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                return 0.0
            cmd = [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(Path(video_path).resolve()),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            return float(proc.stdout.strip())
        except Exception:
            return 0.0

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
        对视频进行去重处理 (全流程 FFmpeg 实现，极大提升性能)
        
        参数:
            input_path: 输入文件路径
            output_path: 输出文件路径 (如果为 None 则自动生成)
            trim_head: 去片头秒数
            trim_tail: 去片尾秒数
            speed: 加速倍率 (1.1 = 1.1倍速)
            apply_flip: 是否水平翻转
            micro_zoom: 是否应用微缩放裁剪 (1.02x)
            add_noise: 是否添加噪点 (抗指纹)
            strip_metadata: 是否清除元数据
            custom_output_dir: 自定义输出目录
            
        返回:
            (是否成功, 消息提示/输出路径)
        """
        try:
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                return False, "未检测到 ffmpeg，请确保系统路径或 venv 中包含 ffmpeg。"

            input_file = Path(input_path)
            if not input_file.exists():
                return False, f"未找到输入文件: {input_path}"

            # 动态默认值
            trim_head = float(trim_head if trim_head is not None else getattr(config, "VIDEO_TRIM_HEAD", 0.5))
            trim_tail = float(trim_tail if trim_tail is not None else getattr(config, "VIDEO_TRIM_TAIL", 0.5))
            speed = float(speed if speed is not None else getattr(config, "VIDEO_SPEED_MULTIPLIER", 1.1))

            # Generate output path
            if output_path is None:
                stem = input_file.stem
                suffix = input_file.suffix
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{stem}{output_suffix}{suffix}"
                
                if custom_output_dir:
                    out_dir = Path(custom_output_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    output_path_obj = out_dir / output_filename
                else:
                    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    output_path_obj = config.OUTPUT_DIR / output_filename
            else:
                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            logger_msg = f"开始 FFmpeg 处理: {input_file.name} (Speed={speed}, Trim={trim_head}/{trim_tail})"
            print(f"[FFmpeg] {logger_msg}") # Console feedback

            # 构建 Filter Chain
            filters = []

            # 1. 剪辑 (Trim) - 优选此时长计算
            duration = self._get_duration(str(input_file))
            if duration > 0:
                end_time = max(0.0, duration - trim_tail)
                # 使用 trim 滤镜比 -ss 更精确控制流
                # 视频 trim
                filters.append(f"trim=start={trim_head}:end={end_time},setpts=PTS-STARTPTS")
                # 音频 trim (必须同步)
                # 注意：如果下面用了 filter_complex，音频也需要处理
            else:
                # 无法获取时长，仅去头
                filters.append(f"trim=start={trim_head},setpts=PTS-STARTPTS")

            # 2. 变速 (Speed)
            if deep_remix_enabled:
                # 非线性心跳变速
                speed_min = 0.9
                speed_max = 1.1
                period = 4.0
                amp = (speed_max - speed_min) / 2.0
                # 叠加基础倍速 speed (如果 speed=1.1, 则整体快一点)
                # filters.append(f"setpts=PTS/({speed}*(1+{amp}*sin(2*PI*t/{period})))") 
                # 简化：仅使用非线性，忽略线性 speed 参数，或者将 linear speed 乘进去
                filters.append(f"setpts=PTS/(1+{amp}*sin(2*PI*t/{period}))")
            elif abs(speed - 1.0) > 0.01:
                filters.append(f"setpts=PTS/{speed}")
                
            # 3. 翻转 (Flip)
            if apply_flip:
                filters.append("hflip")

            # 4. 微缩放 (Zoom & Crop) / 像素位移
            if deep_remix_enabled:
                # 随机位移
                shift_x = random.choice([-2, 2])
                filters.append(f"scale=iw*1.02:ih*1.02,crop=iw:ih:{shift_x}:0")
                
                # 色彩微调
                gamma = round(random.uniform(0.97, 1.03), 3)
                sat = round(random.uniform(0.97, 1.03), 3)
                filters.append(f"eq=gamma={gamma}:saturation={sat}")
            elif micro_zoom:
                # 放大 3% 然后居中裁剪回原尺寸，能够破坏原有指纹
                filters.append("scale=iw*1.03:ih*1.03,crop=iw/1.03:ih/1.03")

            # 5. 噪点 (Noise)

            # 5. 噪点 (Noise)
            if add_noise:
                filters.append("noise=alls=5:allf=t+u")

            vf_string = ",".join(filters)
            
            # 音频滤镜 (Audio Filters)
            af_filters = []
            if duration > 0:
                 actual_end = max(0.0, duration - trim_tail)
                 af_filters.append(f"atrim=start={trim_head}:end={actual_end},asetpts=PTS-STARTPTS")
            else:
                 af_filters.append(f"atrim=start={trim_head},asetpts=PTS-STARTPTS")

            if abs(speed - 1.0) > 0.01:
                af_filters.append(f"atempo={speed}")

            af_string = ",".join(af_filters)

            cmd = [
                ffmpeg,
                "-y",  # 覆盖输出
                "-i", str(input_file),
                "-filter_complex", f"[0:v]{vf_string}[v];[0:a]{af_string}[a]",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-preset", "veryfast", # 速度优先
                "-crf", "23",          # 平衡画质
                "-c:a", "aac",
                str(output_path_obj)
            ]
            
            if strip_metadata:
                cmd.extend(["-map_metadata", "-1"])

            ok, err = self._run_ffmpeg(cmd)
            
            if ok:
                self.processed_count += 1
                return True, str(output_path_obj)
            else:
                # Fallback check: 如果是因为没有音频流导致 map [a] 失败?
                # 简单重试无音频模式
                if "Stream map '0:a' matches no streams" in err:
                     cmd = [
                        ffmpeg, "-y", "-i", str(input_file),
                        "-vf", vf_string,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        str(output_path_obj)
                     ]
                     ok2, err2 = self._run_ffmpeg(cmd)
                     if ok2:
                         self.processed_count += 1
                         return True, str(output_path_obj)
                     else:
                         self.failed_count += 1
                         return False, f"FFmpeg Error (Retry): {err2}"
                
                self.failed_count += 1
                return False, f"FFmpeg Error: {err}"

        except Exception as e:
            self.failed_count += 1
            return False, f"处理异常: {e}"

    def process_video_legacy(
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
        [DEPRECATED] 对视频进行去重处理 (Original MoviePy Implementation)
        保留此方法作为备用 fallback。
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

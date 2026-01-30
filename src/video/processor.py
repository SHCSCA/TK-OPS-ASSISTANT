"""
Video processor using FFmpeg (No MoviePy dependency)
"""
import shutil
import subprocess
import os
import random
import tempfile
import logging
import math
from pathlib import Path
from typing import Tuple, List, Optional

import config
from utils.ffmpeg import FFmpegUtils

logger = logging.getLogger(__name__)

class VideoProcessor:
    """基于 FFmpeg 的视频处理器 (Pure FFmpeg Implementation)"""
    
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长 (sec)"""
        return FFmpegUtils.get_duration(audio_path)

    def adjust_audio_speed(self, input_path: str, output_path: str, speed: float) -> bool:
        """调整音频速度 (atempo)"""
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg: return False
            
            # atempo limited to 0.5 to 2.0. Chain if needed.
            filter_str = ""
            remaining = speed
            # Simple chaining logic
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
            ok, _ = FFmpegUtils.run_cmd(cmd)
            return ok
        except Exception:
            return False

    def generate_silence(self, duration: float, output_path: str) -> bool:
        """生成静音片段"""
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg: return False
            
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(duration),
                str(output_path)
            ]
            ok, _ = FFmpegUtils.run_cmd(cmd)
            return ok
        except Exception:
            return False

    def concat_audio_files(self, file_paths: list[str], output_path: str) -> bool:
        """拼接音频文件列表 (concat demuxer)"""
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg: return False
            
            # Create list file
            list_path = Path(output_path).parent / f"concat_list_{random.randint(1000,9999)}.txt"
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
            ok, _ = FFmpegUtils.run_cmd(cmd)
            
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
            ffmpeg = FFmpegUtils.get_ffmpeg()
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
            ok, err = FFmpegUtils.run_cmd(cmd)
            if not ok: return False, err
            return True, str(output_path)
        except Exception as e:
            return False, str(e)

    def _estimate_filter_complex_length(self, filter_complex: str) -> int:
        cmd_overhead = 500
        return len(filter_complex) + cmd_overhead

    def _run_ffmpeg_with_script(self, args: list, filter_complex: str) -> Tuple[bool, str]:
        """Run FFmpeg dealing with command line length limits on Windows"""
        estimated_len = self._estimate_filter_complex_length(filter_complex)
        CMD_LIMIT = 8191
        
        if estimated_len > CMD_LIMIT - 200:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as script_file:
                    script_file.write(filter_complex)
                    script_path = script_file.name
                
                new_args = []
                i = 0
                while i < len(args):
                    if args[i] == '-filter_complex':
                        new_args.append('-filter_complex_script')
                        new_args.append(script_path)
                        i += 2
                    else:
                        new_args.append(args[i])
                        i += 1
                
                ok, err = FFmpegUtils.run_cmd(new_args)
                try:
                    os.unlink(script_path)
                except:
                    pass
                return ok, err
            except Exception as e:
                return False, f"Script mode failure: {str(e)}"
        else:
             return FFmpegUtils.run_cmd(args)

    def compose_cyborg_video(
        self,
        intro_path: str,
        mid_path: str,
        outro_path: str,
        output_path: str | None = None,
        custom_output_dir: str | None = None,
    ) -> Tuple[bool, str]:
        """Cyborg (Centaur) Content Strategy Concatenation"""
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg:
                return False, "FFmpeg binary not found"

            intro_file = Path(intro_path)
            mid_file = Path(mid_path)
            outro_file = Path(outro_path)
            
            if not (intro_file.exists() and mid_file.exists() and outro_file.exists()):
                 return False, "One or more input files missing"

            if output_path is None:
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{mid_file.stem}_cyborg{output_suffix}{mid_file.suffix}"
                out_dir = Path(custom_output_dir) if custom_output_dir else config.OUTPUT_DIR
                output_path = out_dir / output_filename
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            intro_sec = float(getattr(config, "CYBORG_INTRO_SEC", 2.0) or 2.0)
            outro_sec = float(getattr(config, "CYBORG_OUTRO_SEC", 2.0) or 2.0)

            has_audio = all([
                FFmpegUtils.has_audio(str(intro_file)),
                FFmpegUtils.has_audio(str(mid_file)),
                FFmpegUtils.has_audio(str(outro_file)),
            ])

            scale_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
            
            vf_parts = [
                f"[0:v]trim=0:{intro_sec},{scale_filter},setpts=PTS-STARTPTS[v0]",
                f"[1:v]{scale_filter},setpts=PTS-STARTPTS[v1]",
                f"[2:v]trim=0:{outro_sec},{scale_filter},setpts=PTS-STARTPTS[v2]",
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
                ffmpeg, "-y",
                "-i", str(intro_file),
                "-i", str(mid_file),
                "-i", str(outro_file),
                "-filter_complex", filter_complex,
                "-map", "[vout]",
            ]
            if has_audio:
                cmd.extend(["-map", "[aout]"])
            
            cmd.extend([
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                str(output_path),
            ])

            ok, err = FFmpegUtils.run_cmd(cmd)
            if not ok: return False, f"Cyborg concat failed: {err}"
            return True, str(output_path)
            
        except Exception as e:
            return False, f"Cyborg exception: {e}"

    def process_video_ffmpeg_remix(
        self,
        input_path: str,
        output_path: str | None = None,
        custom_output_dir: str | None = None,
    ) -> Tuple[bool, str]:
        """Video Remix (Non-linear speed + color + shift)"""
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg: return False, "FFmpeg not found"

            input_file = Path(input_path)
            if not input_file.exists(): return False, "Input not found"

            if output_path is None:
                output_filename = f"{input_file.stem}_remix{input_file.suffix}"
                out_dir = Path(custom_output_dir) if custom_output_dir else config.OUTPUT_DIR
                output_path = out_dir / output_filename
            else:
                output_path = Path(output_path)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Effects
            speed_min = float(getattr(config, "HEARTBEAT_SPEED_MIN", 0.9) or 0.9)
            speed_max = float(getattr(config, "HEARTBEAT_SPEED_MAX", 1.1) or 1.1)
            period = float(getattr(config, "HEARTBEAT_PERIOD_SEC", 4.0) or 4.0)
            amp = max(0.0, min(0.3, (speed_max - speed_min) / 2.0))
            
            setpts = f"setpts=PTS/(1+{amp}*sin(2*PI*t/{period}))"
            
            gamma = round(random.uniform(0.97, 1.03), 3)
            saturation = round(random.uniform(0.97, 1.03), 3)
            eq = f"eq=gamma={gamma}:saturation={saturation}"
            
            shift = random.choice([-2, 2])
            scale = "scale=iw*1.02:ih*1.02"
            crop = f"crop=iw:ih:{shift}:0"

            vf = ",".join([setpts, eq, scale, crop])

            cmd = [
                ffmpeg, "-y",
                "-i", str(input_file),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-map_metadata", "-1",
                str(output_path)
            ]
            
            ok, err = FFmpegUtils.run_cmd(cmd)
            if not ok: return False, f"Remix failed: {err}"
            return True, str(output_path)
        except Exception as e:
            return False, f"Remix exception: {e}"

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
        Comprehensive Video Processing using FFmpeg
        """
        try:
            ffmpeg = FFmpegUtils.get_ffmpeg()
            if not ffmpeg: return False, "FFmpeg binary not found"

            input_file = Path(input_path)
            if not input_file.exists(): return False, f"Input not found: {input_path}"

            # Defaults
            trim_head = float(trim_head if trim_head is not None else getattr(config, "VIDEO_TRIM_HEAD", 0.5))
            trim_tail = float(trim_tail if trim_tail is not None else getattr(config, "VIDEO_TRIM_TAIL", 0.5))

            # Output path setup
            if output_path is None:
                suffix = input_file.suffix
                output_suffix = getattr(config, "VIDEO_OUTPUT_SUFFIX", "_processed")
                output_filename = f"{input_file.stem}{output_suffix}{suffix}"
                out_dir = Path(custom_output_dir) if custom_output_dir else config.OUTPUT_DIR
                output_path_obj = out_dir / output_filename
            else:
                output_path_obj = Path(output_path)
            
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Get duration
            duration = FFmpegUtils.get_duration(str(input_file))
            if duration <= 0: return False, "Could not get video duration"

            start_time = max(0.0, trim_head)
            end_time = max(0.0, duration - trim_tail)
            if end_time <= start_time: return False, "Video too short after trimming"

            # Construct chunks with variable speed
            speed_min, speed_max = 1.10, 1.35
            
            v_segments = []
            a_segments = []
            t = start_time
            seg_idx = 0
            
            while t < end_time - 1e-6:
                seg_end = min(t + 1.0, end_time)
                s = round(random.uniform(speed_min, speed_max), 3)
                
                v_segments.append(
                    f"[0:v]trim=start={t}:end={seg_end},setpts=PTS-STARTPTS,setpts=PTS/{s}[v{seg_idx}]"
                )
                a_segments.append(
                    f"[0:a]atrim=start={t}:end={seg_end},asetpts=PTS-STARTPTS,atempo={s}[a{seg_idx}]"
                )
                seg_idx += 1
                t = seg_end
            
            # Post effects
            post_vf = []
            if apply_flip: post_vf.append("hflip")
            
            if deep_remix_enabled:
                shift_x = random.choice([-2, 2])
                post_vf.append(f"scale=iw*1.02:ih*1.02,crop=iw:ih:{shift_x}:0")
                gamma = round(random.uniform(0.97, 1.03), 3)
                sat = round(random.uniform(0.97, 1.03), 3)
                post_vf.append(f"eq=gamma={gamma}:saturation={sat}")
            elif micro_zoom:
                post_vf.append("scale=iw*1.03:ih*1.03,crop=iw/1.03:ih/1.03")
                
            if add_noise:
                post_vf.append("noise=alls=5:allf=t+u")

            # Concat Filter construction
            concat_inputs = "".join([f"[v{i}][a{i}]" for i in range(seg_idx)])
            concat_filter = f"{concat_inputs}concat=n={seg_idx}:v=1:a=1[v0][a0]"

            if post_vf:
                post_vf_str = ",".join(post_vf)
                v_out = f"[v0]{post_vf_str}[v]"
            else:
                v_out = "[v0]null[v]"
            a_out = "[a0]anull[a]"

            filter_complex_av = ";".join(v_segments + a_segments + [concat_filter, v_out, a_out])
            
            # No-Audio Fallback Filter construction
            concat_v_inputs = "".join([f"[v{i}]" for i in range(seg_idx)])
            concat_v = f"{concat_v_inputs}concat=n={seg_idx}:v=1:a=0[v0]"
            
            if post_vf:
                v_only = f"[v0]{post_vf_str}[v]"
            else:
                v_only = "[v0]null[v]"
            
            filter_complex_v = ";".join(v_segments + [concat_v, v_only])

            # Try processing
            cmd = [
                ffmpeg, "-y",
                "-i", str(input_file),
                "-filter_complex", filter_complex_av,
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                str(output_path_obj)
            ]
            if strip_metadata: cmd.extend(["-map_metadata", "-1"])

            ok, err = self._run_ffmpeg_with_script(cmd, filter_complex_av)
            
            if ok:
                self.processed_count += 1
                return True, str(output_path_obj)
            else:
                # Retry without audio if audio map failed
                if "Stream map '0:a' matches no streams" in err:
                    cmd_v = [
                        ffmpeg, "-y", "-i", str(input_file),
                        "-filter_complex", filter_complex_v,
                        "-map", "[v]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        str(output_path_obj)
                    ]
                    if strip_metadata: cmd_v.extend(["-map_metadata", "-1"])
                    
                    ok2, err2 = self._run_ffmpeg_with_script(cmd_v, filter_complex_v)
                    if ok2:
                        self.processed_count += 1
                        return True, str(output_path_obj)
                    else:
                        self.failed_count += 1
                        return False, f"FFmpeg Retry Failed: {err2}"
                
                self.failed_count += 1
                return False, f"FFmpeg Error: {err}"

        except Exception as e:
            self.failed_count += 1
            return False, f"Exception: {e}"

    def batch_process(
        self,
        input_dir: str,
        extensions: Tuple[str, ...] = ('.mp4', '.avi', '.mov', '.mkv')
    ) -> dict:
        """批量处理文件夹内的视频"""
        input_path = Path(input_dir)
        if not input_path.is_dir():
            return {"success": False, "message": "Invalid directory"}
        
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

import sys
import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, List
import config

logger = logging.getLogger(__name__)

class FFmpegUtils:
    _ffmpeg_path: Optional[str] = None
    _ffprobe_path: Optional[str] = None

    @classmethod
    def _detect_binaries(cls):
        """Detect ffmpeg and ffprobe binaries."""
        if cls._ffmpeg_path and cls._ffprobe_path:
            return

        bin_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
        probe_name = "ffprobe.exe" if os.name == 'nt' else "ffprobe"

        # 1. Search in bundled bin directory (highest priority)
        # In frozen mode: sys._MEIPASS/bin
        # In source mode: project_root/bin
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = config.BASE_DIR

        # Check standard locations
        possible_paths = [
            base_path / "bin",
            base_path / "tools",
            base_path / ".." / "bin", # Fallback for some source structures
        ]

        for p in possible_paths:
            ffmpeg = p / bin_name
            ffprobe = p / probe_name
            if ffmpeg.exists() and ffprobe.exists():
                cls._ffmpeg_path = str(ffmpeg.resolve())
                cls._ffprobe_path = str(ffprobe.resolve())
                logger.info(f"Using bundled FFmpeg: {cls._ffmpeg_path}")
                return

        # 2. Search in system PATH
        sys_ffmpeg = shutil.which("ffmpeg")
        sys_ffprobe = shutil.which("ffprobe")
        
        if sys_ffmpeg and sys_ffprobe:
             cls._ffmpeg_path = sys_ffmpeg
             cls._ffprobe_path = sys_ffprobe
             logger.info(f"Using system FFmpeg: {sys_ffmpeg}")
             return
             
        # 3. Last resort: just try calling "ffmpeg" and hope for the best
        cls._ffmpeg_path = "ffmpeg"
        cls._ffprobe_path = "ffprobe"
        logger.warning("FFmpeg not found in bin/ or PATH. Defaulting to 'ffmpeg' command.")

    @classmethod
    def get_ffmpeg(cls) -> str:
        cls._detect_binaries()
        return cls._ffmpeg_path

    @classmethod
    def get_ffprobe(cls) -> str:
        cls._detect_binaries()
        return cls._ffprobe_path

    @classmethod
    def run_cmd(cls, cmd: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
        """Run a command (ffmpeg/ffprobe) and return success/output."""
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                # startupinfo.wShowWindow = subprocess.SW_HIDE

            # Make sure the executable path is absolute if we found one
            # otherwise subprocess might fail if it's not in PATH
            if cmd[0] in ['ffmpeg', 'ffprobe'] and (cls._ffmpeg_path and os.path.isabs(cls._ffmpeg_path)):
                 if cmd[0] == 'ffmpeg': cmd[0] = cls._ffmpeg_path
                 elif cmd[0] == 'ffprobe': cmd[0] = cls._ffprobe_path

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                # CREATE_NO_WINDOW prevents cmd window popup on Windows
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                cwd=cwd
            )
            
            if proc.returncode == 0:
                return True, proc.stdout
            else:
                return False, (proc.stderr or proc.stdout or "").strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_duration(cls, file_path: str) -> float:
        """Get media duration in seconds."""
        cmd = [
            cls.get_ffprobe(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        ok, out = cls.run_cmd(cmd)
        if ok and out.strip():
            try:
                return float(out.strip())
            except:
                pass
        return 0.0

    @classmethod
    def has_audio(cls, video_path: str) -> bool:
        """Check if video has audio stream."""
        cmd = [
             cls.get_ffprobe(),
             "-v", "error",
             "-select_streams", "a:0",
             "-show_entries", "stream=codec_type",
             "-of", "default=nw=1:nk=1",
             str(video_path)
        ]
        ok, out = cls.run_cmd(cmd)
        return ok and out.strip() == "audio"
    
    @classmethod
    def ensure_binaries(cls) -> bool:
        """Check if FFmpeg binaries are actually available/executable."""
        ok, _ = cls.run_cmd([cls.get_ffmpeg(), "-version"])
        return ok

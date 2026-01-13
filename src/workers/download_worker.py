"""素材采集器：下载任务 Worker（QThread）

使用 yt-dlp 批量下载 TikTok / YouTube 等平台的视频。
所有耗时操作都在后台线程执行，通过信号把进度/日志同步到 UI。
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import shutil
from typing import List, Optional

from PyQt5.QtCore import pyqtSignal

from workers.base_worker import BaseWorker


class DownloadWorker(BaseWorker):
    """批量下载 Worker"""

    item_status_signal = pyqtSignal(int, str)  # row, status text
    item_progress_signal = pyqtSignal(int, int)  # row, 0-100
    item_file_signal = pyqtSignal(int, str)  # row, saved filepath
    result_signal = pyqtSignal(list)  # list of downloaded file paths

    def __init__(
        self,
        urls: List[str],
        output_dir: str,
        prefer_no_watermark: bool = False,
        archive_enabled: bool = False,
        archive_root: str | None = None,
    ):
        super().__init__()
        self.urls = [u.strip() for u in (urls or []) if u and u.strip()]
        self.output_dir = Path(output_dir)
        self.prefer_no_watermark = bool(prefer_no_watermark)
        self.archive_enabled = bool(archive_enabled)
        self.archive_root = Path(archive_root) if archive_root else None

    def _platform_from_url(self, url: str) -> str:
        try:
            host = (urlparse(url).netloc or "").lower()
            if "tiktok" in host:
                return "tiktok"
            if "youtu" in host:
                return "youtube"
            if host:
                return host.replace(":", "_")
        except Exception:
            pass
        return "unknown"

    def _archive_file(self, source_file: str, url: str) -> str | None:
        if not self.archive_enabled or not self.archive_root:
            return None

        try:
            src = Path(source_file)
            if not src.exists():
                return None

            date_dir = datetime.now().strftime("%Y%m%d")
            platform = self._platform_from_url(url)
            dest_dir = self.archive_root / date_dir / platform
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            return str(dest)
        except Exception as e:
            self.emit_log(f"✗ 归档失败：{e}")
            return None

    def _run_impl(self):
        if not self.urls:
            self.emit_error("未检测到可用链接，请粘贴至少 1 条视频链接。")
            self.emit_finished(False, "未检测到可用链接")
            return

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.emit_error(f"创建下载目录失败: {e}")
            self.emit_finished(False, "创建下载目录失败")
            return

        if self.archive_enabled and self.archive_root:
            try:
                self.archive_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.emit_log(f"[警告] 素材库目录不可用，将跳过自动归档：{e}")
                self.archive_enabled = False

        self.emit_log(f"开始下载任务：共 {len(self.urls)} 条链接")
        self.emit_log(f"下载目录：{self.output_dir}")
        if self.archive_enabled and self.archive_root:
            self.emit_log(f"素材库归档：开启（根目录：{self.archive_root}）")
        self.emit_progress(0)

        downloaded_files: List[str] = []

        # 延迟导入，避免在未安装依赖时导致 UI 启动失败
        try:
            import yt_dlp
        except Exception as e:
            self.emit_error(f"yt-dlp 未安装或不可用：{e}")
            self.emit_finished(False, "yt-dlp 不可用")
            return

        total = len(self.urls)

        for row, url in enumerate(self.urls):
            if self.should_stop():
                break

            self.item_status_signal.emit(row, "准备中")
            self.item_progress_signal.emit(row, 0)

            def _hook(d):
                if self.should_stop():
                    raise Exception("用户已停止下载")

                status = d.get("status")
                if status == "downloading":
                    percent_str = (d.get("_percent_str") or "0.0%").strip().replace("%", "")
                    try:
                        percent = int(float(percent_str))
                    except Exception:
                        percent = 0
                    self.item_status_signal.emit(row, "下载中")
                    self.item_progress_signal.emit(row, max(0, min(100, percent)))
                elif status == "finished":
                    self.item_status_signal.emit(row, "处理中")
                    self.item_progress_signal.emit(row, 100)

            ydl_opts = {
                "outtmpl": str(self.output_dir / "%(title).200B [%(id)s].%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [_hook],
                "windowsfilenames": True,
            }

            if self.prefer_no_watermark:
                # 说明：不同平台对“无水印”支持差异较大。
                # 这里使用更偏向拿到原始视频流的格式策略；若平台仅提供带水印源，则仍会下载带水印版本。
                ydl_opts.update(
                    {
                        "format": "bestvideo*+bestaudio/best",
                        "merge_output_format": "mp4",
                    }
                )

            try:
                self.emit_log(f"开始下载：{url}" + ("（去水印模式）" if self.prefer_no_watermark else ""))
                self.item_status_signal.emit(row, "下载中")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                self.item_status_signal.emit(row, "完成")
                self.item_file_signal.emit(row, filename)
                downloaded_files.append(filename)
                self.emit_log(f"✓ 下载完成：{Path(filename).name}")

                archived = self._archive_file(filename, url)
                if archived:
                    self.emit_log(f"✓ 已归档到素材库：{Path(archived).name}")

            except Exception as e:
                self.item_status_signal.emit(row, "失败")
                self.emit_log(f"✗ 下载失败：{url}；原因：{e}")

            overall = int(((row + 1) / total) * 100)
            self.emit_progress(overall)

        # 统一回传
        try:
            self.result_signal.emit(downloaded_files)
        except Exception:
            pass
        try:
            self.data_signal.emit(downloaded_files)
        except Exception:
            pass

        self.emit_log(f"任务结束：成功 {len(downloaded_files)} 个，失败 {max(0, len(self.urls) - len(downloaded_files))} 个")
        self.emit_progress(100)
        self.emit_finished(True, "下载任务结束")

import os
import sys
import logging
import requests
import subprocess
import tempfile
import time
from pathlib import Path
from packaging import version
from PyQt5.QtCore import QThread, pyqtSignal
import config

logger = logging.getLogger(__name__)

class UpdateChecker(QThread):
    """
    后台检查更新线程
    """
    update_available = pyqtSignal(str, str, str) # version, download_url, release_notes
    check_finished = pyqtSignal(bool, str)       # success, message

    def __init__(self, manual=False):
        super().__init__()
        self.manual = manual
        self.check_url = config.UPDATE_CHECK_URL

    def run(self):
        try:
            # 1. Fetch Release Info
            # GitHub Release API structure assumption
            # Or simplified JSON: {"tag_name": "v2.3.0", "html_url": "...", "assets": [{"browser_download_url": "..."}]}
            headers = {"User-Agent": "TK-Ops-Assistant-Updater"}
            
            # Simple simulation for now if typical GitHub API
            resp = requests.get(self.check_url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                self.check_finished.emit(False, f"Check failed: {resp.status_code}")
                return

            data = resp.json()
            remote_ver_str = data.get("tag_name", "0.0.0").lstrip("v")
            
            # 2. Compare Versions
            local_ver = version.parse(config.APP_VERSION)
            remote_ver = version.parse(remote_ver_str)
            
            if remote_ver > local_ver:
                download_url = ""
                # Try to find exe asset
                assets = data.get("assets", [])
                for asset in assets:
                    if asset.get("name", "").endswith(".exe") or asset.get("name", "").endswith(".zip"):
                        download_url = asset.get("browser_download_url", "")
                        break
                
                # Fallback to html_url
                if not download_url:
                    download_url = data.get("html_url", "")

                body = data.get("body", "No release notes.")
                
                self.update_available.emit(remote_ver_str, download_url, body)
                self.check_finished.emit(True, "New version found")
            else:
                if self.manual:
                    self.check_finished.emit(True, "Already latest version")
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            self.check_finished.emit(False, str(e))

class AutoUpdater:
    """
    自动更新执行器（Windows）
    """
    @staticmethod
    def install_and_restart(installer_path: str):
        """
        生成 bat 脚本，关闭当前进程，替换文件（或运行安装包），重启。
        """
        if not os.path.exists(installer_path):
            return False

        try:
            current_exe = sys.executable
            # If running from source, we can't really 'update' properly except git pull
            if not getattr(sys, 'frozen', False):
                logger.warning("Running from source, skipping binary update.")
                os.startfile(installer_path) # Just open it
                return True

            # If installer is an EXE (Setup), just run it and quit
            # If installer is the new main executable (Portable), we need to swap
            
            is_installer = "setup" in installer_path.lower() or "installer" in installer_path.lower()
            
            current_dir = os.path.dirname(current_exe)
            batch_file = os.path.join(tempfile.gettempdir(), "tk_ops_update.bat")
            
            if is_installer:
                # 简单模式：运行安装包，关闭自己
                batch_content = f"""
@echo off
timeout /t 2 /nobreak >nul
start "" "{installer_path}"
del "%~f0"
"""
            else:
                # 替换模式 (Portable)
                # 假设下载的是新版 .exe
                batch_content = f"""
@echo off
echo Waiting for application to exit...
timeout /t 3 /nobreak >nul
echo Updating...
copy /Y "{installer_path}" "{current_exe}"
start "" "{current_exe}"
del "{installer_path}"
del "%~f0"
"""

            with open(batch_file, "w") as f:
                f.write(batch_content)
            
            # Execute batch hidden
            args = [batch_file]
            subprocess.Popen(args, shell=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False

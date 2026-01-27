import os
import sys
import logging
import requests
import subprocess
import tempfile
import time
import zipfile
import tarfile
import shutil
from pathlib import Path
from packaging import version
from PyQt5.QtCore import QThread, pyqtSignal
import config

logger = logging.getLogger(__name__)


def _ensure_update_logger() -> None:
    """确保更新日志写入文件。"""
    try:
        log_dir = getattr(config, "LOG_DIR", None)
        if not log_dir:
            return
        log_path = Path(log_dir) / "update.log"
        for h in logger.handlers:
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_path):
                return
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
    except Exception:
        pass


def _parse_github_release(data: dict) -> tuple[str, str, str]:
    remote_ver_str = data.get("tag_name", "0.0.0").lstrip("v")
    download_url = ""
    assets = data.get("assets", [])
    for asset in assets:
        name = (asset.get("name", "") or "").lower()
        # 接受 exe / zip / tar.gz
        if name.endswith(".exe") or name.endswith(".zip") or name.endswith(".tar.gz") or name.endswith(".tgz"):
            download_url = asset.get("browser_download_url", "")
            break
    body = data.get("body", "No release notes.")
    return remote_ver_str, download_url, body


def _parse_gitee_release(data: dict) -> tuple[str, str, str]:
    remote_ver_str = data.get("tag_name", "0.0.0").lstrip("v")
    download_url = ""
    assets = data.get("assets", [])
    for asset in assets:
        name = (asset.get("name", "") or "").lower()
        # 接受 exe / zip / tar.gz
        if name.endswith(".exe") or name.endswith(".zip") or name.endswith(".tar.gz") or name.endswith(".tgz"):
            download_url = asset.get("browser_download_url", "") or asset.get("url", "")
            break
    body = data.get("body", "No release notes.")
    return remote_ver_str, download_url, body

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
            _ensure_update_logger()
            logger.info("启动更新检查...")
            try:
                print("[UPDATE] 检查更新...")
            except Exception:
                pass
            # 1. Fetch Release Info
            # GitHub Release API structure assumption
            headers = {
                "User-Agent": "TK-Ops-Assistant-Updater",
                "Accept": "application/vnd.github+json",
            }
            
            # Simple simulation for now if typical GitHub API
            provider = (getattr(config, "UPDATE_PROVIDER", "github") or "github").strip().lower()
            resp = None
            last_err = None
            for attempt in range(1, 4):
                try:
                    if attempt > 1:
                        logger.warning(f"更新检查重试 {attempt}/3...")
                        try:
                            print(f"[UPDATE] 更新检查重试 {attempt}/3...")
                        except Exception:
                            pass
                    resp = requests.get(self.check_url, headers=headers, timeout=10)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"更新检查请求失败：{e}")
                    time.sleep(1.5)
            if last_err is not None:
                raise last_err
            
            if resp.status_code != 200:
                # 兼容：部分仓库没有 Release，尝试 tags
                if resp.status_code == 404:
                    tags_url = ""
                    if "/releases/latest" in self.check_url:
                        tags_url = self.check_url.replace("/releases/latest", "/tags")
                    if tags_url:
                        try:
                            logger.warning(f"Release 404，尝试 tags：{tags_url}")
                            tags_resp = requests.get(tags_url, headers=headers, timeout=10)
                            if tags_resp.status_code == 200:
                                tags = tags_resp.json()
                                if isinstance(tags, list) and tags:
                                    tag_name = (tags[0].get("name", "") or "").lstrip("v").lstrip("V")
                                    remote_ver_str = tag_name or "0.0.0"
                                    download_url = ""
                                    if provider == "gitee":
                                        # https://gitee.com/api/v5/repos/{owner}/{repo}/releases/latest
                                        parts = self.check_url.split("/repos/")
                                        if len(parts) > 1:
                                            repo_path = parts[1].split("/releases/")[0]
                                            download_url = f"https://gitee.com/{repo_path}/releases"
                                    else:
                                        parts = self.check_url.split("/repos/")
                                        if len(parts) > 1:
                                            repo_path = parts[1].split("/releases/")[0]
                                            download_url = f"https://github.com/{repo_path}/releases"
                                    body = f"Tag latest: {remote_ver_str}"

                                    local_ver = version.parse(config.APP_VERSION)
                                    remote_ver = version.parse(remote_ver_str)
                                    if remote_ver > local_ver:
                                        logger.info(f"发现新版本（tag）：{remote_ver_str} -> {download_url}")
                                        try:
                                            print(f"[UPDATE] 发现新版本（tag）：{remote_ver_str}")
                                        except Exception:
                                            pass
                                        self.update_available.emit(remote_ver_str, download_url, body)
                                        self.check_finished.emit(True, "New version found")
                                        return
                                    logger.info("当前已是最新版本（tag）")
                                    try:
                                        print("[UPDATE] 当前已是最新版本（tag）")
                                    except Exception:
                                        pass
                                    if self.manual:
                                        self.check_finished.emit(True, "Already latest version")
                                    return
                        except Exception as e:
                            logger.warning(f"tags 检查失败：{e}")

                logger.warning(f"更新检查失败：HTTP {resp.status_code}")
                try:
                    print(f"[UPDATE] 检查失败 HTTP {resp.status_code}")
                except Exception:
                    pass
                self.check_finished.emit(False, f"Check failed: {resp.status_code}")
                return

            data = resp.json()
            if provider == "gitee":
                remote_ver_str, download_url, body = _parse_gitee_release(data)
            else:
                remote_ver_str, download_url, body = _parse_github_release(data)
            
            # 2. Compare Versions
            local_ver = version.parse(config.APP_VERSION)
            remote_ver = version.parse(remote_ver_str)
            
            if remote_ver > local_ver:
                if not download_url:
                    logger.warning("Release 缺少可下载资产（exe/zip/tar.gz），无法更新")
                    try:
                        print("[UPDATE] Release 缺少可下载资产（exe/zip/tar.gz），无法更新")
                    except Exception:
                        pass
                    self.check_finished.emit(False, "Release missing update asset")
                    return
                logger.info(f"发现新版本：{remote_ver_str} -> {download_url}")
                try:
                    print(f"[UPDATE] 发现新版本：{remote_ver_str}")
                except Exception:
                    pass
                self.update_available.emit(remote_ver_str, download_url, body)
                self.check_finished.emit(True, "New version found")
            else:
                if self.manual:
                    self.check_finished.emit(True, "Already latest version")
                logger.info("当前已是最新版本")
                try:
                    print("[UPDATE] 当前已是最新版本")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            try:
                print(f"[UPDATE] 检查异常：{e}")
            except Exception:
                pass
            self.check_finished.emit(False, str(e))

class UpdateDownloader(QThread):
    """
    更新包下载线程
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str) # success, file_path

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            _ensure_update_logger()
            temp_dir = tempfile.gettempdir()
            fname = self.url.split("/")[-1]
            # Handle query params if any
            if "?" in fname:
                fname = fname.split("?")[0]
            if not fname:
                fname = "update_package.tmp"
                
            local_path = os.path.join(temp_dir, fname)
            part_path = local_path + ".part"
            downloaded = 0
            if os.path.exists(part_path):
                try:
                    downloaded = os.path.getsize(part_path)
                except Exception:
                    downloaded = 0
            
            headers = {"User-Agent": "TK-Ops-Assistant-Updater"}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"
                logger.info(f"断点续传：已下载 {downloaded} bytes")

            logger.info(f"开始下载更新：{self.url}")
            with requests.get(self.url, stream=True, headers=headers, timeout=30) as r:
                if r.status_code == 416:
                    # 已完整下载
                    os.replace(part_path, local_path)
                    logger.info(f"更新包已下载：{local_path}")
                    self.finished.emit(True, local_path)
                    return

                r.raise_for_status()
                total_length = int(r.headers.get('content-length', 0))
                if "Range" in headers and total_length > 0:
                    total_length = total_length + downloaded

                with open(part_path, 'ab') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_length > 0:
                                pct = int((downloaded / total_length) * 100)
                                self.progress.emit(pct)

            os.replace(part_path, local_path)
            logger.info(f"更新包已下载：{local_path}")
            self.finished.emit(True, local_path)
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.finished.emit(False, str(e))

class AutoUpdater:
    """
    自动更新执行器（Windows）
    """
    @staticmethod
    def install_and_restart(installer_path: str, target_version: str = ""):
        """
        生成 bat 脚本，关闭当前进程，替换文件（或运行安装包），重启。
        支持 .exe 直接替换 或 .zip 解压替换
        """
        try:
            _ensure_update_logger()
            current_exe = sys.executable
            # If running from source, we can't really 'update' properly except git pull
            if not getattr(sys, 'frozen', False):
                try:
                    repo_dir = str(getattr(config, "BASE_DIR", os.getcwd()))
                    logger.info("源码模式：执行 git pull 更新代码...")
                    proc = subprocess.run(
                        ["git", "-C", repo_dir, "pull"],
                        capture_output=True,
                        text=True,
                    )
                    logger.info(f"git pull stdout: {(proc.stdout or '').strip()}")
                    if proc.stderr:
                        logger.warning(f"git pull stderr: {(proc.stderr or '').strip()}")
                    if proc.returncode != 0:
                        return False

                    # 重新启动当前脚本
                    args = [current_exe] + sys.argv
                    subprocess.Popen(args, cwd=repo_dir)
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"源码更新失败：{e}")
                    return False

            if not os.path.exists(installer_path):
                return False

            file_to_swap = installer_path
            
            # Handle ZIP: Extract and find the EXE
            if installer_path.lower().endswith(".zip"):
                try:
                    extract_dir = os.path.join(tempfile.gettempdir(), f"tk_update_{int(time.time())}")
                    with zipfile.ZipFile(installer_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    
                    # Search for main .exe in extracted files
                    found_exe = None
                    # Simple heuristic: largest exe or one matching "tk-ops"
                    exes = list(Path(extract_dir).rglob("*.exe"))
                    if not exes:
                        logger.error("No executable found in update zip")
                        return False
                        
                    # Prefer one with similar name, else largest
                    current_name = Path(current_exe).name
                    
                    # Try exact match
                    for e in exes:
                        if e.name == current_name:
                            found_exe = str(e)
                            break
                    
                    # Try largest
                    if not found_exe:
                        found_exe = str(max(exes, key=lambda p: p.stat().st_size))
                        
                    file_to_swap = found_exe
                except Exception as e:
                    logger.error(f"Failed to extract zip: {e}")
                    return False

            # Handle TAR.GZ / TGZ: Extract and find the EXE
            if installer_path.lower().endswith(".tar.gz") or installer_path.lower().endswith(".tgz"):
                try:
                    extract_dir = os.path.join(tempfile.gettempdir(), f"tk_update_{int(time.time())}")
                    with tarfile.open(installer_path, "r:gz") as tar_ref:
                        tar_ref.extractall(extract_dir)

                    exes = list(Path(extract_dir).rglob("*.exe"))
                    if not exes:
                        logger.error("No executable found in update tar.gz")
                        return False

                    current_name = Path(current_exe).name
                    found_exe = None
                    for e in exes:
                        if e.name == current_name:
                            found_exe = str(e)
                            break
                    if not found_exe:
                        found_exe = str(max(exes, key=lambda p: p.stat().st_size))

                    file_to_swap = found_exe
                except Exception as e:
                    logger.error(f"Failed to extract tar.gz: {e}")
                    return False

            # Generic Swap Logic
            current_dir = os.path.dirname(current_exe)
            current_exe_name = os.path.basename(current_exe)
            
            batch_file = os.path.join(tempfile.gettempdir(), "tk_ops_update.bat")
            
            # Robust Logic:
            # 1. Wait for PID to die
            # 2. Move current.exe -> current.exe.old (Backup/Trash)
            # 3. Move new_file -> current.exe
            # 4. Start current.exe
            # 5. Delete batch file (self)
            
            # Note: We can't delete current.exe.old immediately if it's still locked, 
            # but usually renaming is allowed.
            
            version_line = ""
            if target_version:
                version_line = f"echo {target_version} > \"{os.path.join(current_dir, 'APP_VERSION.txt')}\""

            batch_content = f"""
@echo off
timeout /t 2 /nobreak >nul

:RETRY_MOVE
move /Y "{current_exe}" "{current_exe}.old" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto RETRY_MOVE
)

copy /Y "{file_to_swap}" "{current_exe}" >nul
if errorlevel 1 (
    echo Update failed. Restoring...
    move /Y "{current_exe}.old" "{current_exe}"
    pause
    exit
)

{version_line}

start "" "{current_exe}"
del "{installer_path}"
del "%~f0"
"""

            with open(batch_file, "w") as f:
                f.write(batch_content)
            
            # Execute batch hidden
            args = [batch_file]
            logger.info("开始执行更新替换并重启")
            subprocess.Popen(args, shell=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False




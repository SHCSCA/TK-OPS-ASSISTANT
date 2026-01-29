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


def _normalize_update_url(provider: str, check_url: str) -> str:
    """规范化更新地址（避免 provider 与 URL 不匹配）。"""
    try:
        provider = (provider or "").strip().lower()
        check_url = (check_url or "").strip()
        if provider == "gitee" and "api.github.com" in check_url:
            parts = check_url.split("/repos/")
            if len(parts) > 1:
                repo_path = parts[1]
                return f"https://gitee.com/api/v5/repos/{repo_path}"
        return check_url
    except Exception:
        return check_url


def _parse_github_release(data: dict) -> tuple[str, str, str]:
    remote_ver_str = data.get("tag_name", "0.0.0").lstrip("vV")
    download_url = ""
    assets = data.get("assets", [])
    
    # 优先级：exe > zip > tar.gz
    priorities = [".exe", ".zip", ".tar.gz", ".tgz"]
    
    for suffix in priorities:
        for asset in assets:
            name = (asset.get("name", "") or "").lower()
            if name.endswith(suffix):
                download_url = asset.get("browser_download_url", "")
                if download_url:
                    break
        if download_url:
            break

    if not download_url:
        download_url = data.get("zipball_url", "") or data.get("tarball_url", "")
    body = data.get("body", "No release notes.")
    return remote_ver_str, download_url, body


def _parse_gitee_release(data: dict) -> tuple[str, str, str]:
    remote_ver_str = data.get("tag_name", "0.0.0").lstrip("vV")
    download_url = ""
    assets = data.get("assets", [])
    
    # 优先级：exe > zip > tar.gz
    priorities = [".exe", ".zip", ".tar.gz", ".tgz"]
    
    for suffix in priorities:
        for asset in assets:
            name = (asset.get("name", "") or "").lower()
            if name.endswith(suffix):
                download_url = asset.get("browser_download_url", "") or asset.get("url", "")
                if download_url:
                    break
        if download_url:
            break

    if not download_url:
        download_url = data.get("zipball_url", "") or data.get("tarball_url", "")
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
        self.check_url = _normalize_update_url(
            getattr(config, "UPDATE_PROVIDER", "github"),
            config.UPDATE_CHECK_URL,
        )

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
            # 部分 API 仅提供 assets_url，需二次拉取资产列表
            try:
                if isinstance(data, dict) and not data.get("assets") and data.get("assets_url"):
                    assets_resp = requests.get(data.get("assets_url"), headers=headers, timeout=10)
                    if assets_resp.status_code == 200:
                        data["assets"] = assets_resp.json()
            except Exception as e:
                logger.warning(f"assets_url 拉取失败：{e}")
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

    def _download_to(self, url: str, local_path: str, part_path: str) -> None:
        downloaded = 0
        if os.path.exists(part_path):
            try:
                downloaded = os.path.getsize(part_path)
            except Exception:
                downloaded = 0

        # Mismatched User-Agent can cause Gitee to return error pages
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/octet-stream,application/zip,application/gzip,application/x-zip-compressed,application/x-tar,*/*",
            "Connection": "keep-alive",
        }
        
        # Add Referer for Gitee to prevent hotlink protection issues
        if "gitee.com" in url:
            try:
                # https://gitee.com/owner/repo/...
                parts = url.split("gitee.com/")
                if len(parts) > 1:
                    repo_part = "/".join(parts[1].split("/")[:2])
                    headers["Referer"] = f"https://gitee.com/{repo_part}"
            except Exception:
                pass

        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"
            logger.info(f"断点续传：已下载 {downloaded} bytes")

        logger.info(f"开始下载更新：{url}")
        
        session = requests.Session()
        try:
            with session.get(url, stream=True, headers=headers, timeout=60, allow_redirects=True) as r:
                # Mirror 404/502 handling: fallback to original URL (recursion or simple retry logic)
                # 由于这里是 _download_to，为了简单起见，如果镜像站返回错误，
                # 我们抛出特定异常，让外层 run 方法捕获并处理回退。
                if r.status_code >= 400 and "ghproxy" in url:
                    raise RuntimeError(f"MirrorError: {r.status_code}")

                if r.status_code == 416:
                    # Range Not Satisfiable - assume finished or invalid range.
                    # If file exists and seems substantial, assume finished.
                    if os.path.exists(part_path) and os.path.getsize(part_path) > 1024: 
                        os.replace(part_path, local_path)
                        logger.info(f"更新包已下载(416 Resume)：{local_path}")
                        return
                    else:
                         # Invalid range for small file, restart
                         downloaded = 0
                         if os.path.exists(part_path):
                            os.remove(part_path)
                         if "Range" in headers:
                             del headers["Range"]
                         # Retry without range is complex here without recursion or loop, 
                         # but assume we won't hit this often if logic is correct.
                         r.raise_for_status() # Raise error to trigger retry if needed logic was here

                r.raise_for_status()
                
                # Content-Type check to avoid saving HTML as ZIP
                ctype = r.headers.get("Content-Type", "").lower()
                if "text/html" in ctype:
                    logger.error(f"下载链接返回了 HTML 页面而非文件 (Content-Type: {ctype})。可能需要登录或链接失效。")
                    # Try to read a bit to log what it is
                    try:
                        snippet = r.content[:500].decode('utf-8', errors='ignore')
                        logger.warning(f"Response snippet: {snippet}")
                    except:
                        pass
                    raise RuntimeError("Server returned HTML instead of binary file")

                total_length = int(r.headers.get('content-length', 0))
                if "Range" in headers and total_length > 0:
                    total_length = total_length + downloaded

                mode = 'ab' if downloaded > 0 else 'wb'
                with open(part_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_length > 0:
                                pct = int((downloaded / total_length) * 100)
                                self.progress.emit(pct)

            os.replace(part_path, local_path)
            logger.info(f"更新包已下载：{local_path}")
        finally:
            session.close()

    def run(self):
        try:
            _ensure_update_logger()
            
            # 针对 GitHub 的国内加速处理
            # 国内免费仓库（Gitee/GitCode）通常限制单文件 100MB，GitHub 限制 2GB。
            # 可以在此通过开源加速镜像来实现“像国内仓库一样快”的 GitHub 下载。
            # 修改：增加镜像可用性检测，如果不通则自动回退到直连。
            if "github.com" in self.url and "ghproxy" not in self.url:
                use_mirror = False
                mirror_host = "mirror.ghproxy.com"
                mirror_prefix = f"https://{mirror_host}/"
                
                # 简单检测镜像是否 DNS 可解析 (防止域名失效导致更新彻底不可用)
                try:
                    import socket
                    socket.gethostbyname(mirror_host)
                    use_mirror = True
                except Exception:
                    logger.warning(f"GitHub 加速镜像 {mirror_host} 无法解析，将回退到直连下载。")
                    use_mirror = False
                
                if use_mirror:
                     logger.info(f"应用 GitHub 加速: {mirror_host}")
                     self.url = f"{mirror_prefix}{self.url}"

            temp_dir = tempfile.gettempdir()
            fname = self.url.split("/")[-1]
            # Handle query params if any
            if "?" in fname:
                fname = fname.split("?")[0]
            if not fname:
                fname = "update_package.tmp"
                
            local_path = os.path.join(temp_dir, fname)
            part_path = local_path + ".part"

            try:
                self._download_to(self.url, local_path, part_path)
            except (RuntimeError, Exception) as e:
                err_str = str(e)
                # 场景1: Gitee 返回 HTML
                if "HTML" in err_str and "gitee.com" in self.url:
                    logger.warning("首次下载返回HTML，尝试备用下载策略...")
                
                # 场景2: 加速镜像挂了 (DNS Error, HTTP 4xx/5xx, SSL Error, Connection Error)
                elif ("ghproxy" in self.url) and (
                    "MirrorError" in err_str or 
                    "NameResolutionError" in err_str or 
                    "SSLError" in err_str or 
                    "ConnectionError" in err_str or
                    "Max retries exceeded" in err_str
                ):
                    logger.warning(f"加速镜像下载失败({type(e).__name__})，回退到 GitHub 直连...")
                    # 剥离镜像前缀: https://mirror.ghproxy.com/https://github.com/...
                    # 找到第二个 https://
                    original_url = self.url
                    if "https://github.com" in original_url:
                         original_url = "https://github.com" + original_url.split("https://github.com")[1]
                         self.url = original_url
                         self._download_to(self.url, local_path, part_path)
                         # 如果直连成功，直接跳过下面的重试逻辑
                         self.finished.emit(True, local_path)
                         return
                    else:
                        raise e
                else:
                    raise e
            
            # Gitee 专用重试逻辑：如果 zipball_url 返回 HTML，尝试 repository/archive 格式
            # 原 URL: .../archive/refs/tags/V2.2.2.zip -> 失败 HTML
            # 新 URL: .../repository/archive/V2.2.2.zip
            if "gitee.com" in self.url and "archive/refs/tags" in self.url and not zipfile.is_zipfile(local_path):
                 
                 logger.warning("Gitee archive/refs/tags 下载失败（可能是 HTML），尝试 repository/archive 格式...")
                 alt_url = self.url.replace("archive/refs/tags", "repository/archive")
                 self._download_to(alt_url, local_path, part_path)


            # Gitee 归档链接有时返回 HTML，若不是 zip 则尝试追加 download=1 重新下载
            if local_path.lower().endswith(".zip") and not zipfile.is_zipfile(local_path):
                logger.warning("下载内容不是 zip，尝试追加 download=1 重新下载")
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception:
                    pass
                try:
                    if os.path.exists(part_path):
                        os.remove(part_path)
                except Exception:
                    pass

                retry_url = self.url
                if "download=1" not in retry_url:
                    sep = "&" if "?" in retry_url else "?"
                    retry_url = f"{retry_url}{sep}download=1"
                self._download_to(retry_url, local_path, part_path)

            # 若仍不是 zip，尝试 tar.gz 兜底
            if local_path.lower().endswith(".zip") and not zipfile.is_zipfile(local_path):
                logger.warning("仍不是 zip，尝试使用 tar.gz 下载")
                tar_url = self.url.replace(".zip", ".tar.gz")
                tar_name = fname.replace(".zip", ".tar.gz")
                tar_path = os.path.join(temp_dir, tar_name)
                tar_part = tar_path + ".part"
                self._download_to(tar_url, tar_path, tar_part)
                if not tarfile.is_tarfile(tar_path):
                    raise RuntimeError("下载包不是有效的 zip/tar.gz")
                local_path = tar_path

            # 最终校验
            if local_path.lower().endswith(".zip") and not zipfile.is_zipfile(local_path):
                raise RuntimeError("下载包不是有效的 zip")
            if local_path.lower().endswith(".tar.gz") and not tarfile.is_tarfile(local_path):
                raise RuntimeError("下载包不是有效的 tar.gz")

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
            extract_dir = ""  # Initialize empty to avoid UnboundLocalError
            
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

rem Clean up extracted update files if they exist
set "EXTRACT_DIR={extract_dir}"
if not "%EXTRACT_DIR%"=="" (
    if exist "%EXTRACT_DIR%" (
       rmdir /s /q "%EXTRACT_DIR%"
    )
)

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




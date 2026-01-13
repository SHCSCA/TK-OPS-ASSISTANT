"""诊断中心 Worker（QThread）

目标：为 EXE 场景提供一键自检能力，定位常见环境问题：
- 配置缺失（API Key/Secret 等）
- 目录可写性（Output/Logs/Downloads）
- ffmpeg 是否可用（moviepy 依赖）

所有检查都通过信号回传到 UI，避免卡死主界面。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from PyQt5.QtCore import pyqtSignal

import config
from workers.base_worker import BaseWorker
from api.echotik_api import EchoTikApiClient


@dataclass
class DiagnosticItem:
    name: str
    ok: bool
    message: str
    solution: str = ""  # 新增：解决方案/引导

    def to_dict(self) -> Dict:
        return {
            "name": self.name, 
            "ok": self.ok, 
            "message": self.message,
            "solution": self.solution
        }


class DiagnosticsWorker(BaseWorker):
    """后台诊断 Worker"""

    result_signal = pyqtSignal(list)  # List[dict]

    def _check_writable_dir(self, name: str, path: Path) -> DiagnosticItem:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return DiagnosticItem(
                name, 
                False, 
                f"目录创建失败：{path}；原因：{e}",
                "请检查是否有权限，或尝试以管理员身份运行程序。"
            )

        try:
            test_file = path / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return DiagnosticItem(name, True, f"可写：{path}")
        except Exception as e:
            return DiagnosticItem(
                name, 
                False, 
                f"目录不可写：{path}；原因：{e}",
                "请检查文件夹是否只读，或尝试更改目录权限/以管理员运行。"
            )

    def _check_config_present(self, name: str, value: str, hint: str) -> DiagnosticItem:
        if (value or "").strip():
            return DiagnosticItem(name, True, "已配置")
        return DiagnosticItem(name, False, f"未配置。{hint}", hint)

    def _check_ffmpeg(self) -> DiagnosticItem:
        ffmpeg_path = shutil.which("ffmpeg")
        source = "PATH"

        # 兼容：部分环境不在 PATH 放 ffmpeg，但 moviepy/imageio-ffmpeg 仍可能提供可用路径
        if not ffmpeg_path:
            try:
                import imageio_ffmpeg  # type: ignore

                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                source = "imageio-ffmpeg"
            except Exception:
                ffmpeg_path = None

        if not ffmpeg_path:
            return DiagnosticItem(
                "ffmpeg",
                False,
                "未找到 ffmpeg。moviepy 需要 ffmpeg 才能运行。",
                "请下载 ffmpeg.exe 并将其放入程序根目录，或配置系统环境变量 PATH 指向 ffmpeg bin 目录。"
            )

        try:
            proc = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                first_line = (proc.stdout or "").splitlines()[:1]
                ver = first_line[0] if first_line else "ffmpeg 可用"
                return DiagnosticItem("ffmpeg", True, f"{ver}（来源：{source}）")
            err = (proc.stderr or proc.stdout or "").strip()
            return DiagnosticItem(
                "ffmpeg", 
                False, 
                f"ffmpeg 执行失败：{err[:200]}", 
                "ffmpeg 可执行文件可能已损坏，请重新下载并替换。"
            )
        except Exception as e:
            return DiagnosticItem(
                "ffmpeg", 
                False, 
                f"ffmpeg 检测异常：{e}",
                "请检查 ffmpeg 是否被安全软件拦截。"
            )

    def _check_dependencies_versions(self) -> DiagnosticItem:
        """检查关键依赖版本"""
        try:
            import numpy
            import pandas
            import PyQt5
            
            versions = {
                'numpy': getattr(numpy, '__version__', 'unknown'),
                'pandas': getattr(pandas, '__version__', 'unknown'),
                'PyQt5': getattr(PyQt5, '__version__', 'unknown'),
            }
            
            ver_str = " | ".join(f"{k}={v}" for k, v in versions.items())
            return DiagnosticItem("依赖版本", True, ver_str)
        except Exception as e:
            return DiagnosticItem("依赖版本", False, f"检查失败：{e}", "请检查 pip list 确认依赖是否完整安装。")
    
    def _generate_diagnostic_package(self, items: List[DiagnosticItem]):
        """生成诊断包（用于远程排障）"""
        package_dir = Path(getattr(config, "LOG_DIR", config.BASE_DIR / "Logs")) / "diagnostics"
        package_dir.mkdir(parents=True, exist_ok=True)
        
        # 诊断结果
        diag_file = package_dir / f"diag_{int(tempfile.gettempdir() or 0)}.json"
        diag_data = {
            'timestamp': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
            'items': [it.to_dict() for it in items],
            'startup_info': config.get_startup_info(),
        }
        
        with open(diag_file, 'w', encoding='utf-8') as f:
            json.dump(diag_data, f, ensure_ascii=False, indent=2)
        
        self.emit_log(f"诊断包已保存到：{diag_file}")

    def _check_moviepy(self) -> DiagnosticItem:
        try:
            import moviepy  # noqa: F401

            return DiagnosticItem("moviepy", True, "moviepy 可导入")
        except Exception as e:
            return DiagnosticItem(
                "moviepy", 
                False, 
                f"moviepy 不可用：{e}",
                "如果是源码运行请 pip install -r requirements.txt。如果是 EXE 请联系开发者检查打包。"
            )

    def _check_echotik_connectivity(self) -> DiagnosticItem:
        missing = config.validate_required_config()
        # 只关心 EchoTik 相关项
        for m in missing:
            if "EchoTik" in m:
                return DiagnosticItem(
                    "EchoTik 连通性", 
                    False, 
                    "未配置 EchoTik Key/Secret，无法测试连通性。",
                    "请先在【设置】中配置 Key 和 Secret。"
                )

        try:
            client = EchoTikApiClient()
            products = client.fetch_trending_products(count=1)
            if products is None:
                return DiagnosticItem(
                    "EchoTik 连通性", 
                    False, 
                    "请求失败或无返回（请检查 Key/Secret/网络）。",
                    "检查 API Key 是否过期，或检查网络连接（是否需要代理）。"
                )
            return DiagnosticItem("EchoTik 连通性", True, f"连通正常（返回 {len(products)} 条）")
        except Exception as e:
            return DiagnosticItem(
                "EchoTik 连通性", 
                False, 
                f"连通测试异常：{e}",
                "网络错误或 API 调用限制，请查看日志详情。"
            )

    def _run_impl(self):
        self.emit_log("开始诊断...")
        self.emit_progress(0)

        items: List[DiagnosticItem] = []

        # 0) 启动环境信息
        startup_info = config.get_startup_info()
        env_msg = (
            f"Python {startup_info['python_version']} | "
            f"{'冻结态（EXE）' if startup_info['is_frozen'] else '源码模式'} | "
            f"App {startup_info['app_version']}"
        )
        items.append(DiagnosticItem("运行环境", True, env_msg))
        self.emit_progress(10)

        # 1) 配置项
        items.append(
            self._check_config_present(
                "EchoTik API Key",
                getattr(config, "ECHOTIK_API_KEY", ""),
                "请在【系统设置】中填写 ECHOTIK_API_KEY 并保存。",
            )
        )
        items.append(
            self._check_config_present(
                "EchoTik API Secret",
                getattr(config, "ECHOTIK_API_SECRET", ""),
                "请在【系统设置】中填写 ECHOTIK_API_SECRET 并保存。",
            )
        )
        items.append(self._check_echotik_connectivity())
        self.emit_progress(25)

        # 2) 目录可写性
        items.append(self._check_writable_dir("数据目录 DATA_DIR", Path(getattr(config, "DATA_DIR", config.BASE_DIR))))
        items.append(self._check_writable_dir("输出目录 OUTPUT_DIR", Path(getattr(config, "OUTPUT_DIR", config.BASE_DIR / "Output"))))
        items.append(self._check_writable_dir("日志目录 LOG_DIR", Path(getattr(config, "LOG_DIR", config.BASE_DIR / "Logs"))))
        items.append(self._check_writable_dir("下载目录 DOWNLOAD_DIR", Path(getattr(config, "DOWNLOAD_DIR", config.BASE_DIR / "Downloads"))))
        self.emit_progress(60)

        # 3) 依赖可用性
        items.append(self._check_moviepy())
        self.emit_progress(75)

        # 4) ffmpeg
        items.append(self._check_ffmpeg())
        self.emit_progress(90)
        
        # 5) 依赖版本（用于跨机器排障）
        items.append(self._check_dependencies_versions())
        self.emit_progress(95)

        ok_count = sum(1 for it in items if it.ok)
        self.emit_log(f"诊断完成：通过 {ok_count}/{len(items)}")

        payload = [it.to_dict() for it in items]
        try:
            self.result_signal.emit(payload)
        except Exception:
            pass
        try:
            self.data_signal.emit(payload)
        except Exception:
            pass
        
        # 生成诊断包（日志 + 配置脱敏 + 诊断结果）
        try:
            self._generate_diagnostic_package(items)
        except Exception as e:
            self.emit_log(f"诊断包生成失败：{e}")
        
        self.emit_progress(100)
        self.emit_finished(True, "诊断完成")

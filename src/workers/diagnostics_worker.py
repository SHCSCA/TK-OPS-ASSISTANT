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
from utils.ffmpeg import FFmpegUtils


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
        if FFmpegUtils.ensure_binaries():
            return DiagnosticItem("ffmpeg", True, f"可用: {FFmpegUtils.get_ffmpeg()}")
        
        return DiagnosticItem(
            "ffmpeg",
            False,
            "未找到 ffmpeg。",
            "请下载 ffmpeg.exe 并将其放入 bin 目录，或配置环境变量。"
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
        from datetime import datetime

        diag_file = package_dir / f"diag_{int(time.time())}.json"
        diag_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'items': [it.to_dict() for it in items],
            'startup_info': config.get_startup_info(),
        }
        
        with open(diag_file, 'w', encoding='utf-8') as f:
            json.dump(diag_data, f, ensure_ascii=False, indent=2)
        
        self.emit_log(f"诊断包已保存到：{diag_file}")

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

    def _check_ai_connectivity(self) -> DiagnosticItem:
        """检查 AI 连通性与基础可用性（用于 AI 文案/二创）。"""
        api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
        base_url = (getattr(config, "AI_BASE_URL", "") or "").strip()
        model = (getattr(config, "AI_MODEL", "") or "").strip()

        if not api_key:
            return DiagnosticItem(
                "AI 连通性",
                False,
                "未配置 AI_API_KEY，无法测试 AI 可用性。",
                "请在【系统设置 → AI 配置】填写 AI_API_KEY/AI_BASE_URL/AI_MODEL 并保存。",
            )

        if not base_url:
            return DiagnosticItem(
                "AI 连通性",
                False,
                "未配置 AI_BASE_URL，无法测试 AI 可用性。",
                "请在【系统设置 → AI 配置】填写 AI_BASE_URL（DeepSeek/OpenAI 兼容地址）并保存。",
            )

        if not model:
            return DiagnosticItem(
                "AI 连通性",
                False,
                "未配置 AI_MODEL，无法测试 AI 可用性。",
                "请在【系统设置 → AI 配置】选择/填写 AI_MODEL（可在设置页拉取模型列表）。",
            )

        try:
            # OpenAI 兼容客户端：DeepSeek/网关同样适用
            from openai import OpenAI  # type: ignore

            client = OpenAI(base_url=base_url, api_key=api_key)
            models = client.models.list()
            count = len(getattr(models, "data", []) or [])
            return DiagnosticItem(
                "AI 连通性",
                True,
                f"连通正常（models={count}，当前模型：{model}）",
            )
        except Exception as e:
            msg = str(e)
            # Ark/部分网关不支持 /models：这里不判定为“断网”，由后续“AI 可用性”做最小请求验证
            if "models" in msg and ("not found" in msg.lower() or "404" in msg or "ResourceNotFound" in msg):
                return DiagnosticItem(
                    "AI 连通性",
                    True,
                    "服务可能不支持 /models（已跳过 models.list 检查）",
                    "可在【系统设置】点击‘测试 AI’进行最小请求验证，或直接运行下方‘AI 可用性’诊断项。",
                )
            return DiagnosticItem(
                "AI 连通性",
                False,
                f"连通测试异常：{e}",
                "请检查网络/代理、Base URL 是否正确、Key 是否有效；也可在【系统设置】先点一次‘测试 AI’。",
            )

    def _check_ai_usability(self) -> DiagnosticItem:
        """AI 可用性（最小请求）。注意：会消耗极少量 token。"""
        api_key = (getattr(config, "AI_API_KEY", "") or "").strip()
        base_url = (getattr(config, "AI_BASE_URL", "") or "").strip()
        model = (getattr(config, "AI_MODEL", "") or "").strip()

        if not (api_key and base_url and model):
            return DiagnosticItem(
                "AI 可用性",
                False,
                "AI 配置不完整，跳过可用性测试。",
                "请先配置 AI_API_KEY/AI_BASE_URL/AI_MODEL，然后再运行诊断。",
            )

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(base_url=base_url, api_key=api_key)
            # 最小可用性探测：要求输出固定字符（max_tokens 极小）
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是连通性测试助手。"},
                    {"role": "user", "content": "回复 OK"},
                ],
                max_tokens=4,
                temperature=0,
            )
            content = ""
            try:
                content = (resp.choices[0].message.content or "").strip()
            except Exception:
                content = ""
            if not content:
                return DiagnosticItem(
                    "AI 可用性",
                    True,
                    "请求成功（返回内容为空或不可解析）",
                )
            return DiagnosticItem(
                "AI 可用性",
                True,
                f"请求成功（返回：{content[:50]}）",
            )
        except Exception as e:
            return DiagnosticItem(
                "AI 可用性",
                False,
                f"可用性测试失败：{e}",
                "可能是模型名不可用/余额不足/限流/网络问题；可先在设置页刷新模型列表并重试。",
            )

    def _check_edge_tts_dependency(self) -> DiagnosticItem:
        try:
            import edge_tts  # type: ignore

            _ = edge_tts  # noqa: F841
            return DiagnosticItem("edge-tts", True, "edge-tts 可导入")
        except Exception as e:
            return DiagnosticItem(
                "edge-tts",
                False,
                f"edge-tts 不可用：{e}",
                "如果是源码运行请 pip install -r requirements.txt；如仍失败可先勾选‘配音失败自动降级’保证任务输出。",
            )

    def _check_volc_tts_config(self) -> DiagnosticItem:
        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip().lower()
        if provider not in ("volcengine", "doubao", "volc"):
            return DiagnosticItem("火山 TTS 配置", True, "未启用（当前未选择 volcengine）")

        appid = (getattr(config, "VOLC_TTS_APPID", "") or "").strip()
        token = (config.get_volc_tts_token() or "").strip()
        voice_type = (getattr(config, "VOLC_TTS_VOICE_TYPE", "") or "").strip()

        if not appid or not token or not voice_type:
            return DiagnosticItem(
                "火山 TTS 配置",
                False,
                "配置不完整：需要 VOLC_TTS_APPID / VOLC_TTS_ACCESS_TOKEN / VOLC_TTS_VOICE_TYPE",
                "请到【系统设置 → TTS 配音】填写并保存；也可以先设置备用 TTS 避免任务失败。",
            )

        return DiagnosticItem("火山 TTS 配置", True, "已配置（appid/token/voice_type）")

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
        items.append(self._check_ai_connectivity())
        items.append(self._check_ai_usability())
        self.emit_progress(25)

        # 2) 目录可写性
        items.append(self._check_writable_dir("数据目录 DATA_DIR", Path(getattr(config, "DATA_DIR", config.BASE_DIR))))
        items.append(self._check_writable_dir("输出目录 OUTPUT_DIR", Path(getattr(config, "OUTPUT_DIR", config.BASE_DIR / "Output"))))
        items.append(self._check_writable_dir("日志目录 LOG_DIR", Path(getattr(config, "LOG_DIR", config.BASE_DIR / "Logs"))))
        items.append(self._check_writable_dir("下载目录 DOWNLOAD_DIR", Path(getattr(config, "DOWNLOAD_DIR", config.BASE_DIR / "Downloads"))))
        self.emit_progress(60)

        # 3) 依赖可用性
        # items.append(self._check_moviepy())  # Removed
        items.append(self._check_edge_tts_dependency())
        items.append(self._check_volc_tts_config())
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

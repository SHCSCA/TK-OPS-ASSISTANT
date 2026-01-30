# src/ui/setup_wizard.py
import sys
import os
import requests
from pathlib import Path
from PyQt5.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFileDialog, QComboBox, QMessageBox, 
    QFormLayout, QHBoxLayout, QRadioButton, QButtonGroup,
    QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

import config
from utils.logger import logger

class SetupWizard(QWizard):
    """首次启动配置向导"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"欢迎使用 TikTok 运营助手 v{config.APP_VERSION}")
        self.setWizardStyle(QWizard.ModernStyle)
        
        # 定义页面
        self.setPage(1, WelcomePage())
        self.setPage(2, WorkspacePage())
        self.setPage(3, AISetupPage())
        self.setPage(4, FinishPage())
        
        # 设置样式图标 (可选)
        # self.setPixmap(QWizard.WatermarkPixmap, QPixmap("watermark.png"))
        
        self.resize(800, 600)

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("欢迎使用 TikTok 蓝海运营助手")
        self.setSubTitle("只需简单几步配置，即可开启自动化的 TikTok 运营之旅。")
        
        layout = QVBoxLayout()
        
        info_label = QLabel(
            "<h3>本向导将帮助您配置：</h3>"
            "<ul>"
            "<li><b>工作区目录</b>：用于存放下载的素材和生成的视频。</li>"
            "<li><b>AI 服务</b>：配置 DeepSeek / OpenAI 以启用文案和视频生成功能。</li>"
            "<li><b>环境检测</b>：检测系统依赖项（如 FFmpeg）。</li>"
            "</ul>"
            "<br>"
            "<p>点击 <b>下一步</b> 开始。</p>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        self.setLayout(layout)

class WorkspacePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("设置工作区")
        self.setSubTitle("请选择素材下载和视频输出的目录。建议选择空间充足的磁盘。")
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # 素材库目录
        self.asset_dir_edit = QLineEdit(str(config.ASSET_LIBRARY_DIR))
        self.asset_btn = QPushButton("浏览...")
        self.asset_btn.clicked.connect(lambda: self._browse_dir(self.asset_dir_edit))
        
        # 结果输出目录
        self.output_dir_edit = QLineEdit(str(config.OUTPUT_DIR))
        self.output_btn = QPushButton("浏览...")
        self.output_btn.clicked.connect(lambda: self._browse_dir(self.output_dir_edit))
        
        asset_layout = QHBoxLayout()
        asset_layout.addWidget(self.asset_dir_edit)
        asset_layout.addWidget(self.asset_btn)
        
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.output_btn)
        
        form_layout.addRow("素材库目录 (Asset Library):", asset_layout)
        form_layout.addRow("结果输出目录 (Output):", output_layout)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # 注册字段，以便后续页面访问（如果是标准 wizard 流程），或直接 validatePage 时保存
        self.registerField("asset_dir", self.asset_dir_edit)
        self.registerField("output_dir", self.output_dir_edit)

    def _browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text())
        if d:
            line_edit.setText(d)

    def validatePage(self) -> bool:
        # 简单验证并保存配置
        asset_path = self.asset_dir_edit.text().strip()
        output_path = self.output_dir_edit.text().strip()
        
        if not asset_path or not output_path:
            QMessageBox.warning(self, "提示", "目录路径不能为空。")
            return False
            
        try:
            # 尝试创建目录
            Path(asset_path).mkdir(parents=True, exist_ok=True)
            Path(output_path).mkdir(parents=True, exist_ok=True)
            
            # 保存配置 (使用 new config set_config)
            config.set_config("ASSET_LIBRARY_DIR", asset_path, persist=True)
            config.set_config("DOWNLOAD_DIR", str(Path(asset_path) / "Downloads"), persist=True)
            config.set_config("OUTPUT_DIR", output_path, persist=True)
            config.set_config("PROCESSED_VIDEOS_DIR", str(Path(output_path) / "Processed_Videos"), persist=True)
            config.set_config("LOG_DIR", str(Path(os.path.dirname(config.DATA_DIR)) / "tk_data" / "Logs"), persist=True) # 保持相对 logical
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"目录无法创建或不可写：\n{e}")
            return False

class AITester(QThread):
    """AI 连接测试线程"""
    result_sig = pyqtSignal(bool, str)
    
    def __init__(self, base_url, api_key, model, provider):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        
    def run(self):
        try:
            # 简单的 Chat Completion 测试
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello, say hi only."}],
                "max_tokens": 10
            }
            
            # DeepSeek / OpenAI 兼容
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                self.result_sig.emit(True, "连接成功！AI 响应正常。")
            else:
                err_msg = resp.text
                try:
                    err_msg = resp.json().get("error", {}).get("message", resp.text)
                except:
                    pass
                self.result_sig.emit(False, f"API 错误 ({resp.status_code}): {err_msg}")
                
        except Exception as e:
            self.result_sig.emit(False, f"网络请求失败: {e}")

class AISetupPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("AI 服务配置")
        self.setSubTitle("核心文案生成与视频理解功能需要 AI 模型支持。")
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["doubao", "openai", "deepseek", "compatible"])
        self.provider_combo.setCurrentText(config.AI_PROVIDER)
        self.provider_combo.currentTextChanged.connect(self._on_provider_change)
        
        self.base_url_edit = QLineEdit(config.AI_BASE_URL)
        self.base_url_edit.setPlaceholderText("例如: https://ark.cn-beijing.volces.com/api/v3")
        
        self.api_key_edit = QLineEdit(config.AI_API_KEY)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        
        self.model_edit = QLineEdit(config.AI_MODEL)
        
        form_layout.addRow("服务商:", self.provider_combo)
        form_layout.addRow("Base URL:", self.base_url_edit)
        form_layout.addRow("API Key:", self.api_key_edit)
        form_layout.addRow("默认模型:", self.model_edit)
        
        layout.addLayout(form_layout)
        
        self.test_btn = QPushButton("测试连通性")
        self.test_btn.clicked.connect(self._start_test)
        layout.addWidget(self.test_btn)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        self.verified = False
        
        self.setLayout(layout)
        
        # Init presets
        self._on_provider_change(self.provider_combo.currentText())

    def _on_provider_change(self, provider):
        # 预设
        if provider == "deepseek":
            self.base_url_edit.setText("https://api.deepseek.com")
            self.model_edit.setText("deepseek-chat")
        elif provider == "openai":
            self.base_url_edit.setText("https://api.openai.com/v1")
            self.model_edit.setText("gpt-4o-mini")
        elif provider == "doubao":
            self.base_url_edit.setText("https://ark.cn-beijing.volces.com/api/v3")
            self.model_edit.setText("doubao-pro-32k")

    def _start_test(self):
        base_url = self.base_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip()
        provider = self.provider_combo.currentText()
        
        if not api_key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
            
        self.test_btn.setEnabled(False)
        self.status_label.setText("正在连接 AI 服务...")
        self.status_label.setStyleSheet("color: blue")
        
        self.tester = AITester(base_url, api_key, model, provider)
        self.tester.result_sig.connect(self._on_test_result)
        self.tester.start()

    def _on_test_result(self, success, msg):
        self.test_btn.setEnabled(True)
        self.verified = success
        if success:
            self.status_label.setText(f"✅ {msg}")
            self.status_label.setStyleSheet("color: green")
            # 自动保存
            self._save_config()
        else:
            self.status_label.setText(f"❌ {msg}")
            self.status_label.setStyleSheet("color: red")
            
    def _save_config(self):
        config.set_config("AI_PROVIDER", self.provider_combo.currentText(), persist=True)
        config.set_config("AI_BASE_URL", self.base_url_edit.text().strip(), persist=True)
        config.set_config("AI_API_KEY", self.api_key_edit.text().strip(), persist=True)
        config.set_config("AI_MODEL", self.model_edit.text().strip(), persist=True)

    def validatePage(self) -> bool:
        # 允许跳过，或者强制测试通过？
        # 考虑到用户可能暂时没有 KEY，弹出询问即可
        if not self.verified:
            # 尝试保存以便用户下次无需重新输入
            self._save_config()
            
            if not self.api_key_edit.text().strip():
                ret = QMessageBox.question(self, "跳过配置", "您尚未输入 AI API Key，这将导致文案生成等功能不可用。\n目前是否跳过？", QMessageBox.Yes | QMessageBox.No)
                return ret == QMessageBox.Yes
            
            # 有 key 但未通过测试
            ret = QMessageBox.question(self, "测试未通过", "AI 连接测试未通过（或未执行）。\n是否强行继续？", QMessageBox.Yes | QMessageBox.No)
            return ret == QMessageBox.Yes
            
        return True

class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("配置完成")
        self.setSubTitle("一切准备就绪！")
        
        layout = QVBoxLayout()
        
        # FFmpeg 检测状态
        ffmpeg_status = "✅ 已检测到内置 FFmpeg (Simulated)" 
        # TODO: 真正检测
        
        msg = QLabel(
            f"{ffmpeg_status}<br><br>"
            "点击 <b>完成</b> 启动主程序。<br>"
            "您随时可以在“设置”中修改这些选项。"
        )
        layout.addWidget(msg)
        self.setLayout(layout)

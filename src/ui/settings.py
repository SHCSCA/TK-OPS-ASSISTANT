"""
Settings Panel
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QPushButton, QFrame, QCheckBox,
    QMessageBox, QComboBox, QApplication, QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from api.echotik_api import EchoTikApiClient
import config
from pathlib import Path
from utils.styles import get_global_stylesheet

class SettingsPanel(QWidget):
    """设置面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
    
    def _init_ui(self):
        """初始化设置界面"""
        outer = QVBoxLayout()
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(14)

        # 可滚动内容区：避免控件被挤压导致“全凑在一起/文字变横线”
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(22)

        # Title
        title = QLabel("系统设置")
        title.setObjectName("h1")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        content_layout.addWidget(title)

        # API Configuration
        api_frame = self._create_api_config_frame()
        api_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_layout.addWidget(api_frame)

        # AI Configuration
        ai_frame = self._create_ai_config_frame()
        ai_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_layout.addWidget(ai_frame)

        # Other settings
        other_frame = self._create_other_config_frame()
        other_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_layout.addWidget(other_frame)

        # Video settings
        video_frame = self._create_video_config_frame()
        video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_layout.addWidget(video_frame)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Save button（固定在底部，不随滚动消失）
        save_button = QPushButton("保存设置")
        save_button.setProperty("variant", "primary")
        save_button.clicked.connect(self.save_settings)
        outer.addWidget(save_button)

        self.setLayout(outer)
    
    def _create_api_config_frame(self) -> QFrame:
        """Create API configuration frame"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)  # 增加间距
        
        # Title Area
        header_layout = QHBoxLayout()
        
        title = QLabel("API 配置")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("h2")
        header_layout.addWidget(title)
        
        # Purchase Link
        link_label = QLabel('<a href="https://echotik.live/platform/api-keys">🔑 获取 EchoTik Key</a>')
        link_label.setProperty("style", "link")
        link_label.setOpenExternalLinks(True)
        link_label.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(link_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # API Key (Username)
        api_key_layout = QHBoxLayout()
        api_key_layout.setSpacing(10)
        api_key_label = QLabel("Username (Access Key):")
        api_key_label.setFixedWidth(160)
        api_key_layout.addWidget(api_key_label)
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(config.ECHOTIK_API_KEY)
        # self.api_key_input.setEchoMode(QLineEdit.Password) # Username通常可见
        api_key_layout.addWidget(self.api_key_input)
        layout.addLayout(api_key_layout)
        
        # API Secret (Password)
        api_secret_layout = QHBoxLayout()
        api_secret_layout.setSpacing(10)
        api_secret_label = QLabel("Password (Secret Key):")
        api_secret_label.setFixedWidth(160)
        api_secret_layout.addWidget(api_secret_label)
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setText(config.ECHOTIK_API_SECRET)
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        api_secret_layout.addWidget(self.api_secret_input)
        layout.addLayout(api_secret_layout)
        
        # Test button
        layout.addSpacing(6)
        test_button = QPushButton("测试 API 连接")
        test_button.clicked.connect(self.test_api_connection)
        layout.addWidget(test_button)
        
        frame.setLayout(layout)
        return frame
    
    def _create_ai_config_frame(self) -> QFrame:
        """AI 文案助手配置"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18) # 增加间距

        title = QLabel("AI 文案助手")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("h2")
        layout.addWidget(title)

        # Provider
        provider_layout = QHBoxLayout()
        provider_layout.setSpacing(10)
        provider_label = QLabel("Provider:")
        provider_label.setFixedWidth(160)
        provider_layout.addWidget(provider_label)
        self.ai_provider_input = QLineEdit(getattr(config, "AI_PROVIDER", "openai"))
        provider_layout.addWidget(self.ai_provider_input)
        layout.addLayout(provider_layout)

        # Base URL
        base_url_layout = QHBoxLayout()
        base_url_layout.setSpacing(10)
        base_url_label = QLabel("Base URL (可选):")
        base_url_label.setFixedWidth(160)
        base_url_layout.addWidget(base_url_label)
        self.ai_base_url_input = QLineEdit(getattr(config, "AI_BASE_URL", ""))
        self.ai_base_url_input.setPlaceholderText("例如：https://api.deepseek.com")
        base_url_layout.addWidget(self.ai_base_url_input)
        layout.addLayout(base_url_layout)

        # Model
        model_layout = QHBoxLayout()
        model_layout.setSpacing(10)
        model_label = QLabel("Model:")
        model_label.setFixedWidth(160)
        model_layout.addWidget(model_label)
        self.ai_model_input = QLineEdit(getattr(config, "AI_MODEL", "gpt-4o-mini"))
        model_layout.addWidget(self.ai_model_input)
        layout.addLayout(model_layout)

        # API Key
        api_key_layout = QHBoxLayout()
        api_key_layout.setSpacing(10)
        ai_key_label = QLabel("AI_API_KEY:")
        ai_key_label.setFixedWidth(160)
        api_key_layout.addWidget(ai_key_label)
        self.ai_api_key_input = QLineEdit(getattr(config, "AI_API_KEY", ""))
        self.ai_api_key_input.setEchoMode(QLineEdit.Password)
        api_key_layout.addWidget(self.ai_api_key_input)
        layout.addLayout(api_key_layout)

        frame.setLayout(layout)
        return frame
    
    def _create_other_config_frame(self) -> QFrame:
        """Create other configuration frame"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18) # 增加间距
        
        # Title
        title = QLabel("其他设置")
        title_font = QFont()
        title_font.setBold(True)
        layout.addWidget(title)
        
        # IP check
        self.ip_check_checkbox = QCheckBox("启用 IP 环境检测")
        self.ip_check_checkbox.setChecked(config.IP_CHECK_ENABLED)
        layout.addWidget(self.ip_check_checkbox)
        
        # Auto export
        self.auto_export_checkbox = QCheckBox("蓝海监测完成后自动导出 Excel")
        self.auto_export_checkbox.setChecked(True)
        layout.addWidget(self.auto_export_checkbox)

        # Download directory
        download_layout = QHBoxLayout()
        download_layout.setSpacing(10)
        download_label = QLabel("下载目录:")
        download_label.setFixedWidth(160)
        download_layout.addWidget(download_label)
        self.download_dir_input = QLineEdit(str(getattr(config, "DOWNLOAD_DIR", "")))
        download_layout.addWidget(self.download_dir_input)
        layout.addLayout(download_layout)

        # Theme
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(10)
        theme_label = QLabel("主题:")
        theme_label.setFixedWidth(160)
        theme_layout.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("暗色（默认）", "dark")
        self.theme_combo.addItem("浅色", "light")
        current_mode = (getattr(config, "THEME_MODE", "dark") or "dark").strip().lower()
        idx = self.theme_combo.findData("light" if current_mode == "light" else "dark")
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)
        
        layout.addStretch()
        frame.setLayout(layout)
        return frame

    def _create_video_config_frame(self) -> QFrame:
        """视频处理配置（性能/深度去重默认值）"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18) # 增加间距

        title = QLabel("视频处理")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("h2")
        layout.addWidget(title)

        self.deep_remix_default_checkbox = QCheckBox("默认开启深度去重")
        self.deep_remix_default_checkbox.setChecked(getattr(config, "VIDEO_DEEP_REMIX_ENABLED", False))
        layout.addWidget(self.deep_remix_default_checkbox)

        self.micro_zoom_default_checkbox = QCheckBox("默认开启微缩放")
        self.micro_zoom_default_checkbox.setChecked(getattr(config, "VIDEO_REMIX_MICRO_ZOOM", True))
        layout.addWidget(self.micro_zoom_default_checkbox)

        self.noise_default_checkbox = QCheckBox("默认开启加噪点")
        self.noise_default_checkbox.setChecked(getattr(config, "VIDEO_REMIX_ADD_NOISE", False))
        layout.addWidget(self.noise_default_checkbox)

        self.strip_metadata_default_checkbox = QCheckBox("默认清除元数据")
        self.strip_metadata_default_checkbox.setChecked(getattr(config, "VIDEO_REMIX_STRIP_METADATA", True))
        layout.addWidget(self.strip_metadata_default_checkbox)

        frame.setLayout(layout)
        return frame
    
    def save_settings(self):
        """Save settings to .env and in-memory config"""
        try:
            # 1. Get values from UI
            api_key = self.api_key_input.text().strip()
            api_secret = self.api_secret_input.text().strip()

            # 2. 统一入口写配置（写回 .env + 热更新内存）
            config.set_config("ECHOTIK_API_KEY", api_key, persist=True, hot_reload=False)
            config.set_config("ECHOTIK_API_SECRET", api_secret, persist=True, hot_reload=False)

            # AI
            ai_provider = self.ai_provider_input.text().strip() or "openai"
            ai_base_url = self.ai_base_url_input.text().strip()
            ai_model = self.ai_model_input.text().strip() or "gpt-4o-mini"
            ai_api_key = self.ai_api_key_input.text().strip()
            config.set_config("AI_PROVIDER", ai_provider, persist=True, hot_reload=False)
            config.set_config("AI_BASE_URL", ai_base_url, persist=True, hot_reload=False)
            config.set_config("AI_MODEL", ai_model, persist=True, hot_reload=False)
            config.set_config("AI_API_KEY", ai_api_key, persist=True, hot_reload=False)

            # Downloader
            download_dir = self.download_dir_input.text().strip()
            config.set_config("DOWNLOAD_DIR", download_dir, persist=True, hot_reload=False)

            # Other
            config.set_config("IP_CHECK_ENABLED", "true" if self.ip_check_checkbox.isChecked() else "false", persist=True, hot_reload=False)

            # Theme
            theme_mode = self.theme_combo.currentData() or "dark"
            config.set_config("THEME_MODE", theme_mode, persist=True, hot_reload=False)

            # Video defaults
            config.set_config("VIDEO_DEEP_REMIX_ENABLED", "1" if self.deep_remix_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_MICRO_ZOOM", "1" if self.micro_zoom_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_ADD_NOISE", "1" if self.noise_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_STRIP_METADATA", "1" if self.strip_metadata_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)

            # 3. Reload config in-memory (保证保存后立即生效)
            config.reload_config()

            # 4. Apply theme immediately
            try:
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(get_global_stylesheet(getattr(config, "THEME_MODE", "dark")))
            except Exception:
                pass
            
            QMessageBox.information(self, "成功", "设置已保存并生效。")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")
    
    def test_api_connection(self):
        """Test API connection"""
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入 API Key (Username)")
            return
        if not api_secret:
            QMessageBox.warning(self, "警告", "请输入 API Secret (Password)")
            return

        test_button = self.sender()
        if test_button:
            test_button.setEnabled(False)
            test_button.setText("正在测试...")

        # Force UI update
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            client = EchoTikApiClient(api_key=api_key, api_secret=api_secret)
            success, message = client.check_connection()
            
            if success:
                QMessageBox.information(self, "连接成功", message)
            else:
                QMessageBox.critical(self, "连接失败", message)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试过程中发生意外错误: {str(e)}")
        finally:
            if test_button:
                test_button.setEnabled(True)
                test_button.setText("测试 API 连接")


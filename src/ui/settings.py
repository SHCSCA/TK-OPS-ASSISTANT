"""
Settings Panel
"""
from tts.volc_docs import fetch_voice_types_from_docs
import base64
import requests

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QPushButton, QFrame, QCheckBox,
    QMessageBox, QComboBox, QApplication, QScrollArea, QSizePolicy, QTextEdit
)
from PyQt5.QtGui import QFont, QImage, QColor
from PyQt5.QtCore import Qt, QBuffer, QByteArray
from api.echotik_api import EchoTikApiClient
import config
from pathlib import Path
from utils.styles import apply_global_theme
from utils.ai_models_cache import (
    get_provider_models,
    get_provider_status,
    list_ok_providers,
    set_provider_models,
    set_provider_status,
)
import time


def _norm_provider(text: str) -> str:
    return (text or "").strip().lower()

class SettingsPanel(QWidget):
    """设置面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        try:
            self._auto_refresh_providers_on_startup()
        except Exception:
            pass
    
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

        # TTS Configuration
        tts_frame = self._create_tts_config_frame()
        tts_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_layout.addWidget(tts_frame)

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

        header_layout = QHBoxLayout()

        title = QLabel("AI 配置")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("h2")
        header_layout.addWidget(title)

        # Links（获取/购买）
        ai_link = QLabel('<a href="https://console.volcengine.com/ark">🤖 获取/管理 AI Key（火山方舟）</a>')
        ai_link.setOpenExternalLinks(True)
        ai_link.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(ai_link)

        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        hint = QLabel(
            "本配置同时用于：AI 文案助手 + AI 二创工厂。\n"
            "支持 OpenAI 标准接口（可接 DeepSeek/兼容服务）。"
        )
        hint.setProperty("variant", "muted")
        layout.addWidget(hint)

        # AI System Prompt / Persona
        role_layout = QHBoxLayout()
        role_layout.setSpacing(10)
        role_label = QLabel("AI 角色（可选）:")
        role_label.setFixedWidth(160)
        role_layout.addWidget(role_label)
        self.ai_role_input = QTextEdit()
        self.ai_role_input.setPlaceholderText(
            "示例：你是一名强转化的 TikTok 带货主播，输出更直接、更有号召力。\n"
            "留空则使用默认角色。"
        )
        self.ai_role_input.setMaximumHeight(90)
        self.ai_role_input.setText(getattr(config, "AI_SYSTEM_PROMPT", "") or "")
        role_layout.addWidget(self.ai_role_input)
        layout.addLayout(role_layout)

        # Provider
        provider_layout = QHBoxLayout()
        provider_layout.setSpacing(10)
        provider_label = QLabel("Provider:")
        provider_label.setFixedWidth(160)
        provider_layout.addWidget(provider_label)
        self.ai_provider_input = QLineEdit(getattr(config, "AI_PROVIDER", "openai"))
        provider_layout.addWidget(self.ai_provider_input)
        layout.addLayout(provider_layout)

        # 多供应商配置
        providers_title = QLabel("多供应商配置（豆包 / 千问 / DeepSeek）")
        providers_title.setObjectName("h3")
        layout.addWidget(providers_title)

        providers_hint = QLabel("填写后可在各功能选择供应商；测试/获取模型将使用所选供应商配置。")
        providers_hint.setProperty("variant", "muted")
        layout.addWidget(providers_hint)

        # 供应商卡片（独立配置）
        self._provider_status_labels = {}
        self._provider_model_combos = {}

        def _make_provider_card(provider_key: str, title_text: str, base_url_default: str) -> QFrame:
            card = QFrame()
            card.setProperty("class", "card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(10)

            title = QLabel(title_text)
            title.setObjectName("h3")
            card_layout.addWidget(title)

            status_label = QLabel("状态：未检测")
            status_label.setProperty("variant", "muted")
            card_layout.addWidget(status_label)
            self._provider_status_labels[provider_key] = status_label

            base_row = QHBoxLayout()
            base_row.setSpacing(8)
            base_row.addWidget(QLabel("Base URL:"))
            base_input = QLineEdit(base_url_default)
            base_row.addWidget(base_input)
            card_layout.addLayout(base_row)

            key_row = QHBoxLayout()
            key_row.setSpacing(8)
            key_row.addWidget(QLabel("API Key:"))
            key_input = QLineEdit("")
            key_input.setEchoMode(QLineEdit.Password)
            key_row.addWidget(key_input)
            card_layout.addLayout(key_row)

            model_row = QHBoxLayout()
            model_row.setSpacing(8)
            model_row.addWidget(QLabel("可用模型:"))
            model_combo = QComboBox()
            model_row.addWidget(model_combo)
            card_layout.addLayout(model_row)
            self._provider_model_combos[provider_key] = model_combo

            btn_row = QHBoxLayout()
            test_btn = QPushButton("测试连通")
            fetch_btn = QPushButton("获取模型")
            btn_row.addWidget(test_btn)
            btn_row.addWidget(fetch_btn)
            btn_row.addStretch(1)
            card_layout.addLayout(btn_row)

            # 绑定回调
            test_btn.clicked.connect(lambda: self._test_provider(provider_key))
            fetch_btn.clicked.connect(lambda: self._fetch_provider_models(provider_key))

            # 保存输入框引用
            setattr(self, f"_{provider_key}_base_input", base_input)
            setattr(self, f"_{provider_key}_key_input", key_input)

            return card

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        doubao_default = getattr(config, "AI_DOUBAO_BASE_URL", "") or "https://ark.cn-beijing.volces.com/api/v3"
        qwen_default = getattr(config, "AI_QWEN_BASE_URL", "") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ds_default = getattr(config, "AI_DEEPSEEK_BASE_URL", "") or "https://api.deepseek.com"

        doubao_card = _make_provider_card("doubao", "豆包/火山", doubao_default)
        qwen_card = _make_provider_card("qwen", "千问/通义", qwen_default)
        ds_card = _make_provider_card("deepseek", "DeepSeek", ds_default)

        cards_row.addWidget(doubao_card, 1)
        cards_row.addWidget(qwen_card, 1)
        cards_row.addWidget(ds_card, 1)
        layout.addLayout(cards_row)

        # 还原配置到输入框
        self._set_text_safely(getattr(self, "_doubao_base_input", None), getattr(config, "AI_DOUBAO_BASE_URL", ""))
        self._set_text_safely(getattr(self, "_qwen_base_input", None), getattr(config, "AI_QWEN_BASE_URL", ""))
        self._set_text_safely(getattr(self, "_deepseek_base_input", None), getattr(config, "AI_DEEPSEEK_BASE_URL", ""))
        self._set_text_safely(getattr(self, "_doubao_key_input", None), getattr(config, "AI_DOUBAO_API_KEY", ""))
        self._set_text_safely(getattr(self, "_qwen_key_input", None), getattr(config, "AI_QWEN_API_KEY", ""))
        self._set_text_safely(getattr(self, "_deepseek_key_input", None), getattr(config, "AI_DEEPSEEK_API_KEY", ""))

        self.ai_doubao_base_url_input = getattr(self, "_doubao_base_input")
        self.ai_qwen_base_url_input = getattr(self, "_qwen_base_input")
        self.ai_deepseek_base_url_input = getattr(self, "_deepseek_base_input")
        self.ai_doubao_api_key_input = getattr(self, "_doubao_key_input")
        self.ai_qwen_api_key_input = getattr(self, "_qwen_key_input")
        self.ai_deepseek_api_key_input = getattr(self, "_deepseek_key_input")

        self._refresh_provider_card("doubao")
        self._refresh_provider_card("qwen")
        self._refresh_provider_card("deepseek")

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

        # 模型下拉（可选）
        model_pick_layout = QHBoxLayout()
        model_pick_layout.setSpacing(10)
        model_pick_label = QLabel("可用模型列表:")
        model_pick_label.setFixedWidth(160)
        model_pick_layout.addWidget(model_pick_label)
        self.ai_model_combo = QComboBox()
        current_model = (getattr(config, "AI_MODEL", "") or "").strip()
        if current_model:
            self.ai_model_combo.addItem(current_model)
        self.ai_model_combo.currentTextChanged.connect(self._on_ai_model_selected)
        model_pick_layout.addWidget(self.ai_model_combo)
        layout.addLayout(model_pick_layout)

        # API Key（全局/文案/二创）
        api_key_layout = QHBoxLayout()
        api_key_layout.setSpacing(10)
        ai_key_label = QLabel("全局 API Key:")
        ai_key_label.setFixedWidth(160)
        api_key_layout.addWidget(ai_key_label)
        self.ai_api_key_input = QLineEdit(getattr(config, "AI_API_KEY", ""))
        self.ai_api_key_input.setEchoMode(QLineEdit.Password)
        api_key_layout.addWidget(self.ai_api_key_input)
        layout.addLayout(api_key_layout)

        # 任务级覆盖（可选）
        task_title = QLabel("任务级覆盖（可选）")
        task_title.setObjectName("h3")
        layout.addWidget(task_title)

        task_hint = QLabel("可为不同功能单独指定模型/接口/密钥，留空则使用全局配置。")
        task_hint.setProperty("variant", "muted")
        layout.addWidget(task_hint)

        # 高级配置（任务级 Base URL / API Key）
        advanced_toggle_row = QHBoxLayout()
        self.ai_advanced_toggle_btn = QPushButton("显示高级配置")
        self.ai_advanced_toggle_btn.setCheckable(True)
        self.ai_advanced_toggle_btn.setChecked(False)
        advanced_toggle_row.addWidget(self.ai_advanced_toggle_btn)
        advanced_toggle_row.addStretch(1)
        layout.addLayout(advanced_toggle_row)

        self.ai_advanced_frame = QFrame()
        self.ai_advanced_frame.setProperty("class", "config-frame")
        self.ai_advanced_frame.setVisible(False)
        advanced_layout = QVBoxLayout(self.ai_advanced_frame)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_layout.setSpacing(10)

        def _toggle_advanced(checked: bool) -> None:
            self.ai_advanced_frame.setVisible(bool(checked))
            self.ai_advanced_toggle_btn.setText("隐藏高级配置" if checked else "显示高级配置")
        self.ai_advanced_toggle_btn.toggled.connect(_toggle_advanced)

        # 文案助手
        copy_model_row = QHBoxLayout()
        copy_model_row.setSpacing(10)
        copy_model_label = QLabel("文案模型:")
        copy_model_label.setFixedWidth(160)
        copy_model_row.addWidget(copy_model_label)
        self.ai_copywriter_model_combo = QComboBox()
        copy_model_row.addWidget(self.ai_copywriter_model_combo)
        layout.addLayout(copy_model_row)

        copy_provider_row = QHBoxLayout()
        copy_provider_row.setSpacing(10)
        copy_provider_label = QLabel("文案供应商:")
        copy_provider_label.setFixedWidth(160)
        copy_provider_row.addWidget(copy_provider_label)
        self.ai_copywriter_provider_combo = QComboBox()
        self.ai_copywriter_provider_combo.addItem("默认", "")
        self.ai_copywriter_provider_combo.addItem("豆包/火山", "doubao")
        self.ai_copywriter_provider_combo.addItem("千问/通义", "qwen")
        self.ai_copywriter_provider_combo.addItem("DeepSeek", "deepseek")
        cur_copy_provider = (getattr(config, "AI_COPYWRITER_PROVIDER", "") or "").strip()
        idx_copy_provider = self.ai_copywriter_provider_combo.findData(cur_copy_provider)
        self.ai_copywriter_provider_combo.setCurrentIndex(idx_copy_provider if idx_copy_provider >= 0 else 0)
        copy_provider_row.addWidget(self.ai_copywriter_provider_combo)
        layout.addLayout(copy_provider_row)

        try:
            self.ai_copywriter_provider_combo.currentIndexChanged.connect(self._refresh_task_model_combos)
        except Exception:
            pass

        copy_base_row = QHBoxLayout()
        copy_base_row.setSpacing(10)
        copy_base_label = QLabel("文案 Base URL:")
        copy_base_label.setFixedWidth(160)
        copy_base_row.addWidget(copy_base_label)
        self.ai_copywriter_base_url_input = QLineEdit(getattr(config, "AI_COPYWRITER_BASE_URL", ""))
        copy_base_row.addWidget(self.ai_copywriter_base_url_input)
        advanced_layout.addLayout(copy_base_row)

        copy_key_row = QHBoxLayout()
        copy_key_row.setSpacing(10)
        copy_key_label = QLabel("文案 API Key:")
        copy_key_label.setFixedWidth(160)
        copy_key_row.addWidget(copy_key_label)
        self.ai_copywriter_api_key_input = QLineEdit(getattr(config, "AI_COPYWRITER_API_KEY", ""))
        self.ai_copywriter_api_key_input.setEchoMode(QLineEdit.Password)
        copy_key_row.addWidget(self.ai_copywriter_api_key_input)
        advanced_layout.addLayout(copy_key_row)

        # 二创脚本
        factory_model_row = QHBoxLayout()
        factory_model_row.setSpacing(10)
        factory_model_label = QLabel("二创模型:")
        factory_model_label.setFixedWidth(160)
        factory_model_row.addWidget(factory_model_label)
        self.ai_factory_model_combo = QComboBox()
        factory_model_row.addWidget(self.ai_factory_model_combo)
        layout.addLayout(factory_model_row)

        factory_provider_row = QHBoxLayout()
        factory_provider_row.setSpacing(10)
        factory_provider_label = QLabel("二创供应商:")
        factory_provider_label.setFixedWidth(160)
        factory_provider_row.addWidget(factory_provider_label)
        self.ai_factory_provider_combo = QComboBox()
        self.ai_factory_provider_combo.addItem("默认", "")
        self.ai_factory_provider_combo.addItem("豆包/火山", "doubao")
        self.ai_factory_provider_combo.addItem("千问/通义", "qwen")
        self.ai_factory_provider_combo.addItem("DeepSeek", "deepseek")
        cur_factory_provider = (getattr(config, "AI_FACTORY_PROVIDER", "") or "").strip()
        idx_factory_provider = self.ai_factory_provider_combo.findData(cur_factory_provider)
        self.ai_factory_provider_combo.setCurrentIndex(idx_factory_provider if idx_factory_provider >= 0 else 0)
        factory_provider_row.addWidget(self.ai_factory_provider_combo)
        layout.addLayout(factory_provider_row)

        try:
            self.ai_factory_provider_combo.currentIndexChanged.connect(self._refresh_task_model_combos)
        except Exception:
            pass

        factory_base_row = QHBoxLayout()
        factory_base_row.setSpacing(10)
        factory_base_label = QLabel("二创 Base URL:")
        factory_base_label.setFixedWidth(160)
        factory_base_row.addWidget(factory_base_label)
        self.ai_factory_base_url_input = QLineEdit(getattr(config, "AI_FACTORY_BASE_URL", ""))
        factory_base_row.addWidget(self.ai_factory_base_url_input)
        advanced_layout.addLayout(factory_base_row)

        factory_key_row = QHBoxLayout()
        factory_key_row.setSpacing(10)
        factory_key_label = QLabel("二创 API Key:")
        factory_key_label.setFixedWidth(160)
        factory_key_row.addWidget(factory_key_label)
        self.ai_factory_api_key_input = QLineEdit(getattr(config, "AI_FACTORY_API_KEY", ""))
        self.ai_factory_api_key_input.setEchoMode(QLineEdit.Password)
        factory_key_row.addWidget(self.ai_factory_api_key_input)
        advanced_layout.addLayout(factory_key_row)

        # 时间轴脚本
        timeline_model_row = QHBoxLayout()
        timeline_model_row.setSpacing(10)
        timeline_model_label = QLabel("时间轴模型:")
        timeline_model_label.setFixedWidth(160)
        timeline_model_row.addWidget(timeline_model_label)
        self.ai_timeline_model_combo = QComboBox()
        timeline_model_row.addWidget(self.ai_timeline_model_combo)
        layout.addLayout(timeline_model_row)

        timeline_provider_row = QHBoxLayout()
        timeline_provider_row.setSpacing(10)
        timeline_provider_label = QLabel("时间轴供应商:")
        timeline_provider_label.setFixedWidth(160)
        timeline_provider_row.addWidget(timeline_provider_label)
        self.ai_timeline_provider_combo = QComboBox()
        self.ai_timeline_provider_combo.addItem("默认", "")
        self.ai_timeline_provider_combo.addItem("豆包/火山", "doubao")
        self.ai_timeline_provider_combo.addItem("千问/通义", "qwen")
        self.ai_timeline_provider_combo.addItem("DeepSeek", "deepseek")
        cur_timeline_provider = (getattr(config, "AI_TIMELINE_PROVIDER", "") or "").strip()
        idx_timeline_provider = self.ai_timeline_provider_combo.findData(cur_timeline_provider)
        self.ai_timeline_provider_combo.setCurrentIndex(idx_timeline_provider if idx_timeline_provider >= 0 else 0)
        timeline_provider_row.addWidget(self.ai_timeline_provider_combo)
        layout.addLayout(timeline_provider_row)

        try:
            self.ai_timeline_provider_combo.currentIndexChanged.connect(self._refresh_task_model_combos)
        except Exception:
            pass

        timeline_base_row = QHBoxLayout()
        timeline_base_row.setSpacing(10)
        timeline_base_label = QLabel("时间轴 Base URL:")
        timeline_base_label.setFixedWidth(160)
        timeline_base_row.addWidget(timeline_base_label)
        self.ai_timeline_base_url_input = QLineEdit(getattr(config, "AI_TIMELINE_BASE_URL", ""))
        timeline_base_row.addWidget(self.ai_timeline_base_url_input)
        advanced_layout.addLayout(timeline_base_row)

        timeline_key_row = QHBoxLayout()
        timeline_key_row.setSpacing(10)
        timeline_key_label = QLabel("时间轴 API Key:")
        timeline_key_label.setFixedWidth(160)
        timeline_key_row.addWidget(timeline_key_label)
        self.ai_timeline_api_key_input = QLineEdit(getattr(config, "AI_TIMELINE_API_KEY", ""))
        self.ai_timeline_api_key_input.setEchoMode(QLineEdit.Password)
        timeline_key_row.addWidget(self.ai_timeline_api_key_input)
        advanced_layout.addLayout(timeline_key_row)

        # 图转视频
        photo_model_row = QHBoxLayout()
        photo_model_row.setSpacing(10)
        photo_model_label = QLabel("图转视频模型:")
        photo_model_label.setFixedWidth(160)
        photo_model_row.addWidget(photo_model_label)
        self.ai_photo_model_combo = QComboBox()
        photo_model_row.addWidget(self.ai_photo_model_combo)
        layout.addLayout(photo_model_row)

        photo_provider_row = QHBoxLayout()
        photo_provider_row.setSpacing(10)
        photo_provider_label = QLabel("图转视频供应商:")
        photo_provider_label.setFixedWidth(160)
        photo_provider_row.addWidget(photo_provider_label)
        self.ai_photo_provider_combo = QComboBox()
        self.ai_photo_provider_combo.addItem("默认", "")
        self.ai_photo_provider_combo.addItem("豆包/火山", "doubao")
        self.ai_photo_provider_combo.addItem("千问/通义", "qwen")
        self.ai_photo_provider_combo.addItem("DeepSeek", "deepseek")
        cur_photo_provider = (getattr(config, "AI_PHOTO_PROVIDER", "") or "").strip()
        idx_photo_provider = self.ai_photo_provider_combo.findData(cur_photo_provider)
        self.ai_photo_provider_combo.setCurrentIndex(idx_photo_provider if idx_photo_provider >= 0 else 0)
        photo_provider_row.addWidget(self.ai_photo_provider_combo)
        layout.addLayout(photo_provider_row)

        try:
            self.ai_photo_provider_combo.currentIndexChanged.connect(self._refresh_task_model_combos)
        except Exception:
            pass

        photo_base_row = QHBoxLayout()
        photo_base_row.setSpacing(10)
        photo_base_label = QLabel("图转视频 Base URL:")
        photo_base_label.setFixedWidth(160)
        photo_base_row.addWidget(photo_base_label)
        self.ai_photo_base_url_input = QLineEdit(getattr(config, "AI_PHOTO_BASE_URL", ""))
        photo_base_row.addWidget(self.ai_photo_base_url_input)
        advanced_layout.addLayout(photo_base_row)

        photo_key_row = QHBoxLayout()
        photo_key_row.setSpacing(10)
        photo_key_label = QLabel("图转视频 API Key:")
        photo_key_label.setFixedWidth(160)
        photo_key_row.addWidget(photo_key_label)
        self.ai_photo_api_key_input = QLineEdit(getattr(config, "AI_PHOTO_API_KEY", ""))
        self.ai_photo_api_key_input.setEchoMode(QLineEdit.Password)
        photo_key_row.addWidget(self.ai_photo_api_key_input)
        advanced_layout.addLayout(photo_key_row)

        # 视觉实验室
        vision_model_row = QHBoxLayout()
        vision_model_row.setSpacing(10)
        vision_model_label = QLabel("视觉模型:")
        vision_model_label.setFixedWidth(160)
        vision_model_row.addWidget(vision_model_label)
        self.ai_vision_model_combo = QComboBox()
        vision_model_row.addWidget(self.ai_vision_model_combo)
        layout.addLayout(vision_model_row)

        vision_provider_row = QHBoxLayout()
        vision_provider_row.setSpacing(10)
        vision_provider_label = QLabel("视觉供应商:")
        vision_provider_label.setFixedWidth(160)
        vision_provider_row.addWidget(vision_provider_label)
        self.ai_vision_provider_combo = QComboBox()
        self.ai_vision_provider_combo.addItem("默认", "")
        self.ai_vision_provider_combo.addItem("豆包/火山", "doubao")
        self.ai_vision_provider_combo.addItem("千问/通义", "qwen")
        self.ai_vision_provider_combo.addItem("DeepSeek", "deepseek")
        cur_vision_provider = (getattr(config, "AI_VISION_PROVIDER", "") or "").strip()
        idx_vision_provider = self.ai_vision_provider_combo.findData(cur_vision_provider)
        self.ai_vision_provider_combo.setCurrentIndex(idx_vision_provider if idx_vision_provider >= 0 else 0)
        vision_provider_row.addWidget(self.ai_vision_provider_combo)
        layout.addLayout(vision_provider_row)

        try:
            self.ai_vision_provider_combo.currentIndexChanged.connect(self._refresh_task_model_combos)
        except Exception:
            pass

        vision_base_row = QHBoxLayout()
        vision_base_row.setSpacing(10)
        vision_base_label = QLabel("视觉 Base URL:")
        vision_base_label.setFixedWidth(160)
        vision_base_row.addWidget(vision_base_label)
        self.ai_vision_base_url_input = QLineEdit(getattr(config, "AI_VISION_BASE_URL", ""))
        vision_base_row.addWidget(self.ai_vision_base_url_input)
        advanced_layout.addLayout(vision_base_row)

        vision_key_row = QHBoxLayout()
        vision_key_row.setSpacing(10)
        vision_key_label = QLabel("视觉 API Key:")
        vision_key_label.setFixedWidth(160)
        vision_key_row.addWidget(vision_key_label)
        self.ai_vision_api_key_input = QLineEdit(getattr(config, "AI_VISION_API_KEY", ""))
        self.ai_vision_api_key_input.setEchoMode(QLineEdit.Password)
        vision_key_row.addWidget(self.ai_vision_api_key_input)
        advanced_layout.addLayout(vision_key_row)

        # 初始化任务级模型下拉
        self._refresh_task_model_combos()

        layout.addWidget(self.ai_advanced_frame)

        frame.setLayout(layout)
        return frame

    def _on_ai_model_selected(self, model: str) -> None:
        model = (model or "").strip()
        if not model:
            return
        # 下拉选择即同步到输入框（便于保存）
        try:
            self.ai_model_input.setText(model)
        except Exception:
            pass

    def _set_text_safely(self, widget: QLineEdit, text: str) -> None:
        try:
            widget.setText((text or "").strip())
        except Exception:
            pass

    def _provider_title(self, provider: str) -> str:
        p = (provider or "").strip().lower()
        mapping = {
            "doubao": "豆包/火山",
            "qwen": "千问/通义",
            "deepseek": "DeepSeek",
        }
        return mapping.get(p, provider or "供应商")

    def _fill_task_model_combo(self, combo: QComboBox, provider: str, fallback: str) -> None:
        models = get_provider_models(provider) if provider else []
        try:
            combo.blockSignals(True)
            combo.clear()
            clean_models = [m for m in (models or []) if m]
            if clean_models:
                combo.addItems(clean_models)
            else:
                if fallback:
                    combo.addItem(fallback)
                else:
                    combo.addItem("（未获取模型）")
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _refresh_task_model_combos(self) -> None:
        # 文案
        try:
            p = self.ai_copywriter_provider_combo.currentData() or ""
        except Exception:
            p = ""
        fallback = (getattr(config, "AI_COPYWRITER_MODEL", "") or "").strip() or (getattr(config, "AI_MODEL", "") or "").strip()
        self._fill_task_model_combo(self.ai_copywriter_model_combo, p, fallback)

        # 二创
        try:
            p = self.ai_factory_provider_combo.currentData() or ""
        except Exception:
            p = ""
        fallback = (getattr(config, "AI_FACTORY_MODEL", "") or "").strip() or (getattr(config, "AI_MODEL", "") or "").strip()
        self._fill_task_model_combo(self.ai_factory_model_combo, p, fallback)

        # 时间轴
        try:
            p = self.ai_timeline_provider_combo.currentData() or ""
        except Exception:
            p = ""
        fallback = (getattr(config, "AI_TIMELINE_MODEL", "") or "").strip() or (getattr(config, "AI_MODEL", "") or "").strip()
        self._fill_task_model_combo(self.ai_timeline_model_combo, p, fallback)

        # 图转视频
        try:
            p = self.ai_photo_provider_combo.currentData() or ""
        except Exception:
            p = ""
        fallback = (getattr(config, "AI_PHOTO_MODEL", "") or "").strip() or (getattr(config, "AI_MODEL", "") or "").strip()
        self._fill_task_model_combo(self.ai_photo_model_combo, p, fallback)

        # 视觉
        try:
            p = self.ai_vision_provider_combo.currentData() or ""
        except Exception:
            p = ""
        fallback = (getattr(config, "AI_VISION_MODEL", "") or "").strip() or (getattr(config, "AI_MODEL", "") or "").strip()
        self._fill_task_model_combo(self.ai_vision_model_combo, p, fallback)

    def _auto_refresh_providers_on_startup(self) -> None:
        """启动时自动刷新一次供应商模型（若 key/base 已配置）。"""
        for provider in ("doubao", "qwen", "deepseek"):
            try:
                api_key, base_url = self._get_provider_inputs(provider)
                if not api_key:
                    continue
                combo = (self._provider_model_combos or {}).get(provider)
                if combo is None:
                    continue
                self._fetch_models_with(self._provider_title(provider), api_key, base_url, combo)
                models = [combo.itemText(i) for i in range(combo.count()) if combo.itemText(i)]
                models = [m for m in models if "未获取" not in m]
                if models:
                    set_provider_models(provider, models, ok=True, message="启动自动刷新")
                else:
                    set_provider_status(provider, False, "启动未获取到模型")
            except Exception as e:
                set_provider_status(provider, False, str(e))
            finally:
                self._refresh_provider_card(provider)
        try:
            self._refresh_task_model_combos()
        except Exception:
            pass

    def _format_status_text(self, provider: str) -> str:
        status = get_provider_status(provider)
        ok = bool(status.get("ok"))
        msg = status.get("message", "") or ""
        ts = int(status.get("updated_at") or 0)
        time_text = ""
        if ts > 0:
            try:
                time_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            except Exception:
                time_text = ""
        if ok:
            return f"状态：已连通{(' · ' + time_text) if time_text else ''}"
        if ts > 0:
            tail = f" · {time_text}" if time_text else ""
            return f"状态：失败{(' - ' + msg) if msg else ''}{tail}"
        return "状态：未检测"

    def _refresh_provider_card(self, provider: str) -> None:
        label = (self._provider_status_labels or {}).get(provider)
        if label:
            label.setText(self._format_status_text(provider))

        combo = (self._provider_model_combos or {}).get(provider)
        if not combo:
            return
        models = get_provider_models(provider)
        try:
            combo.blockSignals(True)
            combo.clear()
            if models:
                combo.addItems(models)
            else:
                combo.addItem("（未获取模型）")
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _test_provider(self, provider: str) -> None:
        title = self._provider_title(provider)
        api_key, base_url = self._get_provider_inputs(provider)
        models = get_provider_models(provider)
        probe_model = ""
        if models:
            probe_model = models[0]
        else:
            probe_model = (self.ai_model_input.text() if hasattr(self, "ai_model_input") else "").strip()
        try:
            self._test_ai_connection_with(title, api_key, base_url, model=probe_model)
            set_provider_status(provider, True, "连通正常")
        except Exception as e:
            set_provider_status(provider, False, str(e))
            QMessageBox.critical(self, "连接失败", f"{title} 连接失败：{e}")
        finally:
            self._refresh_provider_card(provider)

    def _fetch_provider_models(self, provider: str) -> None:
        title = self._provider_title(provider)
        api_key, base_url = self._get_provider_inputs(provider)
        combo = (self._provider_model_combos or {}).get(provider)
        if combo is None:
            return
        try:
            self._fetch_models_with(title, api_key, base_url, combo)
            models = [combo.itemText(i) for i in range(combo.count()) if combo.itemText(i)]
            models = [m for m in models if "未获取" not in m]
            if models:
                set_provider_models(provider, models, ok=True, message="模型已更新")
            else:
                set_provider_status(provider, False, "未获取到模型")
        except Exception as e:
            set_provider_status(provider, False, str(e))
            QMessageBox.critical(self, "失败", f"{title} 获取模型失败：{e}")
        finally:
            self._refresh_provider_card(provider)

    def _build_ai_client(self):
        """构造 OpenAI 兼容客户端（DeepSeek/兼容服务也可用）。"""
        return self._build_ai_client_for(self.ai_api_key_input, self.ai_base_url_input, missing_key_hint="请先填写全局 API Key")

    def _build_ai_client_raw(self, api_key: str, base_url: str):
        """根据字符串构造 OpenAI 兼容客户端。"""
        try:
            import openai
        except Exception as e:
            raise RuntimeError(f"缺少 openai 依赖：{e}")
        if not api_key:
            raise ValueError("请先填写所选供应商的 API Key")
        if base_url:
            return openai.OpenAI(api_key=api_key, base_url=base_url)
        return openai.OpenAI(api_key=api_key)

    def _get_provider_inputs(self, provider: str) -> tuple[str, str]:
        """从 UI 获取供应商配置（api_key, base_url）。"""
        p = (provider or "").strip().lower()
        if p == "doubao":
            return (self.ai_doubao_api_key_input.text().strip(), self.ai_doubao_base_url_input.text().strip())
        if p == "qwen":
            return (self.ai_qwen_api_key_input.text().strip(), self.ai_qwen_base_url_input.text().strip())
        if p == "deepseek":
            return (self.ai_deepseek_api_key_input.text().strip(), self.ai_deepseek_base_url_input.text().strip())
        return ("", "")

    def _build_ai_client_for(self, api_key_widget: QLineEdit, base_url_widget: QLineEdit, missing_key_hint: str = "请先填写 AI_API_KEY"):
        """根据输入框构造 OpenAI 兼容客户端。"""
        try:
            import openai
        except Exception as e:
            raise RuntimeError(f"缺少 openai 依赖：{e}")

        api_key = api_key_widget.text().strip() if api_key_widget else ""
        if not api_key:
            raise ValueError(missing_key_hint)

        base_url = base_url_widget.text().strip() if base_url_widget else ""
        # openai SDK 允许 base_url 为空，使用默认 OpenAI
        if base_url:
            return openai.OpenAI(api_key=api_key, base_url=base_url)
        return openai.OpenAI(api_key=api_key)

    def _looks_like_models_not_supported(self, e: Exception) -> bool:
        msg = str(e) or ""
        msg_low = msg.lower()
        # 常见表现：404 + ResourceNotFound + models not found
        if "404" in msg_low and "model" in msg_low and "not found" in msg_low:
            return True
        if "resourcenotfound" in msg_low and "models" in msg_low:
            return True
        if "the specified resource 'models' is not found".lower() in msg_low:
            return True
        return False

    def _probe_ai_minimal(self, client, model: str) -> None:
        """最小推理探测：用于不支持 /models 的服务（如部分 Ark 场景）。"""
        use_model = (model or "").strip()
        if not use_model:
            raise ValueError("请先填写/选择模型（Model ID）")

        # 1) 优先用 Responses API（Ark 文档示例主推）
        try:
            if hasattr(client, "responses") and hasattr(client.responses, "create"):
                resp = client.responses.create(
                    model=use_model,
                    input="ping",
                    # OpenAI Responses 推荐字段；不同兼容实现可能忽略
                    instructions="你是连通性测试助手，只回复 OK",
                )
                text = ""
                try:
                    text = (getattr(resp, "output_text", "") or "").strip()
                except Exception:
                    text = ""
                # 即使为空，只要不抛异常也算连通
                return
        except Exception:
            # 继续尝试 chat
            pass

        # 2) 回退 chat.completions
        if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
            raise RuntimeError("当前服务不支持 responses/chat 接口，无法完成探测")
        _ = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": "你是连通性测试助手，只回复 OK"},
                {"role": "user", "content": "ping"},
            ],
            max_tokens=8,
            temperature=0,
        )

    def _test_ai_connection_with(self, title: str, api_key: str, base_url: str, model: str = ""):
        if not api_key:
            raise ValueError("API Key 为空")
        try:
            # 临时构造 client：base_url 为空时走默认 OpenAI
            dummy_key = QLineEdit()
            dummy_key.setText(api_key)
            dummy_base = QLineEdit()
            dummy_base.setText(base_url)
            client = self._build_ai_client_for(dummy_key, dummy_base)
            try:
                models = client.models.list()
                count = len(getattr(models, "data", []) or [])
                QMessageBox.information(self, "连接成功", f"{title} 可用。可用模型数量：{count}")
                return
            except Exception as e:
                # 某些服务不支持 /models：降级为最小推理探测
                if self._looks_like_models_not_supported(e):
                    self._probe_ai_minimal(client, model=model)
                    QMessageBox.information(
                        self,
                        "连接成功",
                        f"{title} 可用（提示：当前服务不支持自动获取模型列表 /models，已改用最小推理探测）。\n"
                        "如需查询 Model ID，请到火山方舟【模型列表】页查看。",
                    )
                    return
                raise
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"{title} 连接失败：{e}")

    def test_ai_connection(self):
        """测试 AI 连接（优先调用 models.list）。"""
        btn = self.sender()
        if btn:
            btn.setEnabled(False)
            btn.setText("正在测试...")
        QApplication.processEvents()

        try:
            provider = ""
            if hasattr(self, "ai_provider_pick_combo"):
                provider = self.ai_provider_pick_combo.currentData() or ""
            if provider:
                api_key, base_url = self._get_provider_inputs(provider)
                client = self._build_ai_client_raw(api_key, base_url)
            else:
                client = self._build_ai_client()
            model = (self.ai_model_input.text() or "").strip()
            try:
                models = client.models.list()
                count = len(getattr(models, "data", []) or [])
                QMessageBox.information(self, "连接成功", f"AI 可用。可用模型数量：{count}")
                return
            except Exception as e:
                # 某些服务不支持 /models：降级为最小推理探测
                if self._looks_like_models_not_supported(e):
                    self._probe_ai_minimal(client, model=model)
                    QMessageBox.information(
                        self,
                        "连接成功",
                        "AI 可用（提示：当前服务不支持自动获取模型列表 /models，已改用最小推理探测）。\n"
                        "如需查询 Model ID，请到火山方舟【模型列表】页查看。",
                    )
                    return
                raise
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"AI 连接失败：{e}")
        finally:
            if btn:
                btn.setEnabled(True)
                btn.setText("测试 AI")

    def fetch_ai_models(self):
        """拉取当前 AI 服务支持的模型列表，并填充下拉框。"""
        btn = self.sender()
        if btn:
            btn.setEnabled(False)
            btn.setText("获取中...")
        QApplication.processEvents()

        try:
            provider = ""
            if hasattr(self, "ai_provider_pick_combo"):
                provider = self.ai_provider_pick_combo.currentData() or ""
            if provider:
                api_key, base_url = self._get_provider_inputs(provider)
                client = self._build_ai_client_raw(api_key, base_url)
            else:
                client = self._build_ai_client()
            models = client.models.list()
            items = []
            for m in (getattr(models, "data", []) or []):
                mid = getattr(m, "id", "")
                if mid:
                    items.append(mid)

            items = sorted(set(items))
            if not items:
                QMessageBox.warning(self, "无结果", "当前服务未返回可用模型列表（可能不支持 /v1/models）。")
                return

            current = self.ai_model_input.text().strip()
            def _fill(combo: QComboBox, cur: str) -> None:
                try:
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(items)
                    if cur and cur in items:
                        combo.setCurrentText(cur)
                finally:
                    try:
                        combo.blockSignals(False)
                    except Exception:
                        pass

            _fill(self.ai_model_combo, current)

            QMessageBox.information(self, "成功", f"已加载 {len(items)} 个模型。")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"获取模型列表失败：{e}")
        finally:
            if btn:
                btn.setEnabled(True)
                btn.setText("获取模型")

    def _fetch_models_with(self, title: str, api_key: str, base_url: str, target_combo: QComboBox, target_input: QLineEdit | None = None) -> None:
        if not api_key:
            raise ValueError("API Key 为空")

        dummy_key = QLineEdit()
        dummy_key.setText(api_key)
        dummy_base = QLineEdit()
        dummy_base.setText(base_url)
        client = self._build_ai_client_for(dummy_key, dummy_base)
        try:
            models = client.models.list()
        except Exception as e:
            if self._looks_like_models_not_supported(e):
                raise RuntimeError(
                    "当前服务不支持自动获取模型列表（/models 返回 404）。\n"
                    "请到火山方舟控制台/文档查询 Model ID 后手动填写。\n"
                    "模型列表：https://www.volcengine.com/docs/82379/1330310"
                )
            raise

        items: list[str] = []
        for m in (getattr(models, "data", []) or []):
            mid = getattr(m, "id", "")
            if mid:
                items.append(mid)

        items = sorted(set(items))
        if not items:
            QMessageBox.warning(self, "无结果", f"{title} 未返回可用模型列表（可能不支持 /v1/models）。")
            return

        try:
            target_combo.blockSignals(True)
            target_combo.clear()
            target_combo.addItems(items)
            if target_input is not None:
                cur = (target_input.text() or "").strip()
                if cur and cur in items:
                    target_combo.setCurrentText(cur)
        finally:
            try:
                target_combo.blockSignals(False)
            except Exception:
                pass

        QMessageBox.information(self, "成功", f"{title} 已加载 {len(items)} 个模型。")

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

        # Update
        update_provider_row = QHBoxLayout()
        update_provider_row.setSpacing(10)
        update_provider_label = QLabel("更新源:")
        update_provider_label.setFixedWidth(160)
        update_provider_row.addWidget(update_provider_label)
        self.update_provider_combo = QComboBox()
        self.update_provider_combo.addItem("GitHub", "github")
        self.update_provider_combo.addItem("Gitee", "gitee")
        cur_update_provider = (getattr(config, "UPDATE_PROVIDER", "github") or "github").strip().lower()
        idx_update = self.update_provider_combo.findData(cur_update_provider)
        self.update_provider_combo.setCurrentIndex(idx_update if idx_update >= 0 else 0)
        update_provider_row.addWidget(self.update_provider_combo)
        layout.addLayout(update_provider_row)

        update_url_row = QHBoxLayout()
        update_url_row.setSpacing(10)
        update_url_label = QLabel("更新检查 URL:")
        update_url_label.setFixedWidth(160)
        update_url_row.addWidget(update_url_label)
        self.update_check_url_input = QLineEdit(getattr(config, "UPDATE_CHECK_URL", ""))
        update_url_row.addWidget(self.update_check_url_input)
        layout.addLayout(update_url_row)

        
        layout.addStretch()
        frame.setLayout(layout)
        return frame

    def _create_tts_config_frame(self) -> QFrame:
        """TTS 配音配置（AI 二创工厂使用）。"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        header_layout = QHBoxLayout()

        title = QLabel("TTS 配音")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("h2")
        header_layout.addWidget(title)

        tts_link = QLabel('<a href="https://www.volcengine.com/product/doubao">🔊 获取/购买 豆包语音</a>')
        tts_link.setOpenExternalLinks(True)
        tts_link.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(tts_link)

        doc_link = QLabel('<a href="https://www.volcengine.com/docs/6561/1329505?lang=zh">📄 接入文档</a>')
        doc_link.setOpenExternalLinks(True)
        doc_link.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(doc_link)

        voice_link = QLabel('<a href="https://www.volcengine.com/docs/6561/1257544">🎛️ 音色列表</a>')
        voice_link.setOpenExternalLinks(True)
        voice_link.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(voice_link)

        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        hint = QLabel(
            "AI 二创工厂会用 TTS 合成配音。\n"
            "建议：生产优先用【豆包/火山】；Edge-TTS 免费但可能出现 403 风控。"
        )
        hint.setProperty("variant", "muted")
        layout.addWidget(hint)

        # Provider
        provider_row = QHBoxLayout()
        provider_row.setSpacing(10)
        provider_label = QLabel("TTS_PROVIDER:")
        provider_label.setFixedWidth(160)
        provider_row.addWidget(provider_label)
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItem("Edge-TTS（免费）", "edge-tts")
        self.tts_provider_combo.addItem("豆包/火山（推荐）", "volcengine")
        cur_provider = _norm_provider(getattr(config, "TTS_PROVIDER", "edge-tts"))
        idx = self.tts_provider_combo.findData(cur_provider)
        self.tts_provider_combo.setCurrentIndex(idx if idx >= 0 else 0)
        provider_row.addWidget(self.tts_provider_combo)
        layout.addLayout(provider_row)

        # Fallback
        fallback_row = QHBoxLayout()
        fallback_row.setSpacing(10)
        fallback_label = QLabel("备用 TTS:")
        fallback_label.setFixedWidth(160)
        fallback_row.addWidget(fallback_label)
        self.tts_fallback_combo = QComboBox()
        self.tts_fallback_combo.addItem("不启用", "")
        self.tts_fallback_combo.addItem("Edge-TTS", "edge-tts")
        self.tts_fallback_combo.addItem("豆包/火山", "volcengine")
        cur_fb = _norm_provider(getattr(config, "TTS_FALLBACK_PROVIDER", ""))
        idx_fb = self.tts_fallback_combo.findData(cur_fb)
        self.tts_fallback_combo.setCurrentIndex(idx_fb if idx_fb >= 0 else 0)
        fallback_row.addWidget(self.tts_fallback_combo)
        layout.addLayout(fallback_row)

        # Edge voice
        edge_voice_row = QHBoxLayout()
        edge_voice_row.setSpacing(10)
        edge_voice_label = QLabel("Edge Voice:")
        edge_voice_label.setFixedWidth(160)
        edge_voice_row.addWidget(edge_voice_label)
        self.tts_voice_input = QLineEdit(getattr(config, "TTS_VOICE", "en-US-AvaNeural"))
        self.tts_voice_input.setPlaceholderText("例如：en-US-AvaNeural")
        edge_voice_row.addWidget(self.tts_voice_input)
        layout.addLayout(edge_voice_row)

        # Speed
        speed_row = QHBoxLayout()
        speed_row.setSpacing(10)
        speed_label = QLabel("语速倍率:")
        speed_label.setFixedWidth(160)
        speed_row.addWidget(speed_label)
        self.tts_speed_input = QLineEdit(str(getattr(config, "TTS_SPEED", "1.1")))
        self.tts_speed_input.setPlaceholderText("1.0=正常；1.1=加速10%")
        speed_row.addWidget(self.tts_speed_input)
        layout.addLayout(speed_row)

        # 情绪指令（豆包 TTS 2.0）
        emo_preset_row = QHBoxLayout()
        emo_preset_row.setSpacing(10)
        emo_preset_label = QLabel("情绪指令预设:")
        emo_preset_label.setFixedWidth(160)
        emo_preset_row.addWidget(emo_preset_label)
        self.tts_emotion_preset_combo = QComboBox()
        self.tts_emotion_preset_combo.addItem("不启用", "")
        self.tts_emotion_preset_combo.addItem("热情带货", "用热情、外放、强转化的带货口播语气说")
        self.tts_emotion_preset_combo.addItem("沉稳讲解", "用沉稳、专业、清晰讲解的语气说")
        self.tts_emotion_preset_combo.addItem("轻松种草", "用轻松、自然、亲切种草的语气说")
        self.tts_emotion_preset_combo.addItem("夸张吸睛", "用夸张、情绪饱满、吸睛的语气说")
        self.tts_emotion_preset_combo.addItem("剧情对白", "用剧情对白的语气说，像在表演短剧")
        self.tts_emotion_preset_combo.addItem("情绪爆发", "用情绪爆发、强烈起伏的语气说")
        self.tts_emotion_preset_combo.addItem("温柔ASMR", "用轻声、温柔、贴耳的ASMR语气说")
        self.tts_emotion_preset_combo.addItem("冷静测评", "用冷静、客观、测评解读的语气说")
        self.tts_emotion_preset_combo.addItem("权威讲解", "用权威、稳重、可信赖的讲解语气说")
        cur_preset = (getattr(config, "TTS_EMOTION_PRESET", "") or "").strip()
        idx_preset = self.tts_emotion_preset_combo.findData(cur_preset)
        self.tts_emotion_preset_combo.setCurrentIndex(idx_preset if idx_preset >= 0 else 0)
        emo_preset_row.addWidget(self.tts_emotion_preset_combo)
        layout.addLayout(emo_preset_row)

        # 场景模式
        scene_row = QHBoxLayout()
        scene_row.setSpacing(10)
        scene_label = QLabel("场景模式:")
        scene_label.setFixedWidth(160)
        scene_row.addWidget(scene_label)
        self.tts_scene_combo = QComboBox()
        self.tts_scene_combo.addItem("不启用", "")
        self.tts_scene_combo.addItem("带货转化", "commerce")
        self.tts_scene_combo.addItem("评测解读", "review")
        self.tts_scene_combo.addItem("开箱体验", "unboxing")
        self.tts_scene_combo.addItem("剧情对白", "story")
        self.tts_scene_combo.addItem("口播讲解", "talk")
        cur_scene = (getattr(config, "TTS_SCENE_MODE", "") or "").strip()
        idx_scene = self.tts_scene_combo.findData(cur_scene)
        self.tts_scene_combo.setCurrentIndex(idx_scene if idx_scene >= 0 else 0)
        scene_row.addWidget(self.tts_scene_combo)
        layout.addLayout(scene_row)

        emo_intensity_row = QHBoxLayout()
        emo_intensity_row.setSpacing(10)
        emo_intensity_label = QLabel("情绪强度:")
        emo_intensity_label.setFixedWidth(160)
        emo_intensity_row.addWidget(emo_intensity_label)
        self.tts_emotion_intensity_combo = QComboBox()
        self.tts_emotion_intensity_combo.addItem("轻", "轻")
        self.tts_emotion_intensity_combo.addItem("中", "中")
        self.tts_emotion_intensity_combo.addItem("强", "强")
        cur_intensity = (getattr(config, "TTS_EMOTION_INTENSITY", "中") or "中").strip()
        idx_intensity = self.tts_emotion_intensity_combo.findData(cur_intensity)
        self.tts_emotion_intensity_combo.setCurrentIndex(idx_intensity if idx_intensity >= 0 else 1)
        emo_intensity_row.addWidget(self.tts_emotion_intensity_combo)
        layout.addLayout(emo_intensity_row)

        emo_custom_row = QHBoxLayout()
        emo_custom_row.setSpacing(10)
        emo_custom_label = QLabel("自定义指令:")
        emo_custom_label.setFixedWidth(160)
        emo_custom_row.addWidget(emo_custom_label)
        self.tts_emotion_custom_input = QLineEdit(getattr(config, "TTS_EMOTION_CUSTOM", ""))
        self.tts_emotion_custom_input.setPlaceholderText("例如：用撒娇、轻声、带点期待的语气说")
        emo_custom_row.addWidget(self.tts_emotion_custom_input)
        layout.addLayout(emo_custom_row)

        # 火山（按官方文档：APP ID + Access Token + Secret Key）
        volc_endpoint_row = QHBoxLayout()
        volc_endpoint_row.setSpacing(10)
        volc_endpoint_label = QLabel("VOLC_TTS_ENDPOINT:")
        volc_endpoint_label.setFixedWidth(160)
        volc_endpoint_row.addWidget(volc_endpoint_label)
        self.volc_endpoint_input = QLineEdit(getattr(config, "VOLC_TTS_ENDPOINT", "https://openspeech.bytedance.com/api/v1/tts"))
        volc_endpoint_row.addWidget(self.volc_endpoint_input)
        layout.addLayout(volc_endpoint_row)

        volc_appid_row = QHBoxLayout()
        volc_appid_row.setSpacing(10)
        volc_appid_label = QLabel("VOLC_TTS_APPID:")
        volc_appid_label.setFixedWidth(160)
        volc_appid_row.addWidget(volc_appid_label)
        self.volc_appid_input = QLineEdit(getattr(config, "VOLC_TTS_APPID", ""))
        volc_appid_row.addWidget(self.volc_appid_input)
        layout.addLayout(volc_appid_row)

        volc_token_row = QHBoxLayout()
        volc_token_row.setSpacing(10)
        volc_token_label = QLabel("VOLC_TTS_ACCESS_TOKEN:")
        volc_token_label.setFixedWidth(160)
        volc_token_row.addWidget(volc_token_label)
        self.volc_access_token_input = QLineEdit(getattr(config, "VOLC_TTS_ACCESS_TOKEN", "") or getattr(config, "VOLC_TTS_TOKEN", ""))
        self.volc_access_token_input.setEchoMode(QLineEdit.Password)
        volc_token_row.addWidget(self.volc_access_token_input)
        layout.addLayout(volc_token_row)

        volc_sk_row = QHBoxLayout()
        volc_sk_row.setSpacing(10)
        volc_sk_label = QLabel("VOLC_TTS_SECRET_KEY:")
        volc_sk_label.setFixedWidth(160)
        volc_sk_row.addWidget(volc_sk_label)
        self.volc_secret_key_input = QLineEdit(getattr(config, "VOLC_TTS_SECRET_KEY", ""))
        self.volc_secret_key_input.setEchoMode(QLineEdit.Password)
        volc_sk_row.addWidget(self.volc_secret_key_input)
        layout.addLayout(volc_sk_row)

        volc_cluster_row = QHBoxLayout()
        volc_cluster_row.setSpacing(10)
        volc_cluster_label = QLabel("VOLC_TTS_CLUSTER:")
        volc_cluster_label.setFixedWidth(160)
        volc_cluster_row.addWidget(volc_cluster_label)
        self.volc_cluster_input = QLineEdit(getattr(config, "VOLC_TTS_CLUSTER", "volcano_tts"))
        self.volc_cluster_input.setPlaceholderText("默认 volcano_tts")
        volc_cluster_row.addWidget(self.volc_cluster_input)
        layout.addLayout(volc_cluster_row)

        volc_voice_row = QHBoxLayout()
        volc_voice_row.setSpacing(10)
        volc_voice_label = QLabel("VOLC_TTS_VOICE_TYPE:")
        volc_voice_label.setFixedWidth(160)
        volc_voice_row.addWidget(volc_voice_label)
        self.volc_voice_input = QComboBox()
        self.volc_voice_input.setEditable(True)
        cur_voice = (getattr(config, "VOLC_TTS_VOICE_TYPE", "") or "").strip()
        if cur_voice:
            self.volc_voice_input.addItem(cur_voice)
            self.volc_voice_input.setCurrentText(cur_voice)
        self.volc_voice_input.setMinimumWidth(320)
        volc_voice_row.addWidget(self.volc_voice_input)
        layout.addLayout(volc_voice_row)

        voices_btn_row = QHBoxLayout()
        voices_btn_row.setSpacing(10)
        voices_btn_row.addWidget(QLabel("音色列表:"))
        self.volc_voices_btn = QPushButton("获取音色列表（文档）")
        self.volc_voices_btn.clicked.connect(self.fetch_volc_voice_list)
        voices_btn_row.addWidget(self.volc_voices_btn)
        voices_btn_row.addStretch(1)
        layout.addLayout(voices_btn_row)

        volc_encoding_row = QHBoxLayout()
        volc_encoding_row.setSpacing(10)
        volc_encoding_label = QLabel("VOLC_TTS_ENCODING:")
        volc_encoding_label.setFixedWidth(160)
        volc_encoding_row.addWidget(volc_encoding_label)
        self.volc_encoding_input = QLineEdit(getattr(config, "VOLC_TTS_ENCODING", "mp3"))
        self.volc_encoding_input.setPlaceholderText("mp3 / wav")
        volc_encoding_row.addWidget(self.volc_encoding_input)
        layout.addLayout(volc_encoding_row)

        # Quick test
        test_row = QHBoxLayout()
        self.tts_test_btn = QPushButton("测试 TTS")
        self.tts_test_btn.clicked.connect(self.test_tts_connection)
        test_row.addWidget(self.tts_test_btn)
        test_row.addStretch(1)
        layout.addLayout(test_row)

        frame.setLayout(layout)
        return frame

    def test_tts_connection(self):
        """测试 TTS（轻量）。

        - Edge：仅做依赖导入检查
        - 火山：校验必要配置；可选发起极短文本合成（默认开启）
        """
        btn = self.sender()
        if btn:
            btn.setEnabled(False)
            btn.setText("正在测试...")
        QApplication.processEvents()

        try:
            provider = self.tts_provider_combo.currentData() or "edge-tts"
            provider = _norm_provider(provider)

            if provider in ("edge", "edge-tts", "edgetts"):
                try:
                    import edge_tts  # type: ignore

                    _ = edge_tts
                    QMessageBox.information(self, "成功", "edge-tts 可用（依赖导入正常）。")
                except Exception as e:
                    QMessageBox.critical(self, "失败", f"edge-tts 不可用：{e}")
                return

            if provider in ("volcengine", "doubao", "volc"):
                appid = self.volc_appid_input.text().strip()
                token = self.volc_access_token_input.text().strip()
                voice_type = (self.volc_voice_input.currentText() or "").strip()
                endpoint = self.volc_endpoint_input.text().strip()
                if not appid or not token or not voice_type:
                    QMessageBox.warning(self, "配置不完整", "请先填写 VOLC_TTS_APPID / VOLC_TTS_ACCESS_TOKEN / VOLC_TTS_VOICE_TYPE")
                    return

                # 做一次极短合成，验证真可用（写入临时文件后删除）
                try:
                    from tts.volcengine_provider import synthesize_volcengine_token
                    from pathlib import Path
                    import tempfile

                    tmp = Path(tempfile.gettempdir()) / "tk_ops_tts_test.mp3"
                    synthesize_volcengine_token(
                        text="OK",
                        out_path=tmp,
                        appid=appid,
                        token=token,
                        voice_type=voice_type,
                        speed_text=(self.tts_speed_input.text().strip() or "1.0"),
                        cluster=(self.volc_cluster_input.text().strip() or "volcano_tts"),
                        encoding=(self.volc_encoding_input.text().strip() or "mp3"),
                        endpoint=(endpoint or "https://openspeech.bytedance.com/api/v1/tts"),
                    )
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                    QMessageBox.information(self, "成功", "火山 TTS 可用（已完成一次短文本合成）。")
                except Exception as e:
                    QMessageBox.critical(self, "失败", f"火山 TTS 测试失败：{e}")
                return

            QMessageBox.warning(self, "未知 Provider", f"不支持的 TTS_PROVIDER：{provider}")

        finally:
            if btn:
                btn.setEnabled(True)
                btn.setText("测试 TTS")

    def fetch_volc_voice_list(self):
        """从火山公开文档抓取音色 ID 列表并填充到下拉框。

        说明：官方音色列表页是文档静态/半静态内容，这里做“方便运营”的快速导入。
        若抓取不到，仍可在控制台复制 voice_type 直接粘贴到输入框。
        """
        btn = self.sender()
        if btn:
            btn.setEnabled(False)
            btn.setText("获取中...")
        QApplication.processEvents()

        try:
            items = fetch_voice_types_from_docs(timeout=20)
            if not items:
                QMessageBox.warning(self, "未获取到", "未能从文档中解析到音色列表。你仍可在控制台复制 voice_type 粘贴到输入框。")
                return

            current = (self.volc_voice_input.currentText() or "").strip()
            self.volc_voice_input.blockSignals(True)
            self.volc_voice_input.clear()
            self.volc_voice_input.addItems(items)
            if current and current in items:
                self.volc_voice_input.setCurrentText(current)
            self.volc_voice_input.blockSignals(False)

            QMessageBox.information(self, "成功", f"已加载 {len(items)} 个音色 ID（来源：文档页）。")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"获取音色列表失败：{e}")
        finally:
            if btn:
                btn.setEnabled(True)
                btn.setText("获取音色列表（文档）")

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

        cloud_title = QLabel("云端图转视频（真实生成）")
        cloud_title.setObjectName("h3")
        layout.addWidget(cloud_title)

        self.video_cloud_enabled_checkbox = QCheckBox("启用云端图转视频（将替代本地图片流合成）")
        self.video_cloud_enabled_checkbox.setChecked(bool(getattr(config, "VIDEO_CLOUD_ENABLED", False)))
        layout.addWidget(self.video_cloud_enabled_checkbox)

        cloud_key_row = QHBoxLayout()
        cloud_key_row.setSpacing(10)
        cloud_key_label = QLabel("VIDEO_CLOUD_API_KEY:")
        cloud_key_label.setFixedWidth(160)
        cloud_key_row.addWidget(cloud_key_label)
        self.video_cloud_api_key_input = QLineEdit(getattr(config, "VIDEO_CLOUD_API_KEY", ""))
        self.video_cloud_api_key_input.setEchoMode(QLineEdit.Password)
        cloud_key_row.addWidget(self.video_cloud_api_key_input)
        layout.addLayout(cloud_key_row)

        submit_row = QHBoxLayout()
        submit_row.setSpacing(10)
        submit_label = QLabel("提交接口 URL:")
        submit_label.setFixedWidth(160)
        submit_row.addWidget(submit_label)
        self.video_cloud_submit_input = QLineEdit(getattr(config, "VIDEO_CLOUD_SUBMIT_URL", ""))
        self.video_cloud_submit_input.setPlaceholderText("https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")
        submit_row.addWidget(self.video_cloud_submit_input)
        layout.addLayout(submit_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        status_label = QLabel("查询接口 URL:")
        status_label.setFixedWidth(160)
        status_row.addWidget(status_label)
        self.video_cloud_status_input = QLineEdit(getattr(config, "VIDEO_CLOUD_STATUS_URL", ""))
        self.video_cloud_status_input.setPlaceholderText("可用 {task_id} 占位")
        status_row.addWidget(self.video_cloud_status_input)
        layout.addLayout(status_row)

        model_row = QHBoxLayout()
        model_row.setSpacing(10)
        model_label = QLabel("模型 ID:")
        model_label.setFixedWidth(160)
        model_row.addWidget(model_label)
        self.video_cloud_model_input = QLineEdit(getattr(config, "VIDEO_CLOUD_MODEL", ""))
        model_row.addWidget(self.video_cloud_model_input)
        layout.addLayout(model_row)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(10)
        quality_label = QLabel("质量档位:")
        quality_label.setFixedWidth(160)
        quality_row.addWidget(quality_label)
        self.video_cloud_quality_combo = QComboBox()
        self.video_cloud_quality_combo.addItem("低（推荐）", "low")
        self.video_cloud_quality_combo.addItem("中", "medium")
        self.video_cloud_quality_combo.addItem("高", "high")
        cur_q = (getattr(config, "VIDEO_CLOUD_QUALITY", "low") or "low").strip()
        idx_q = self.video_cloud_quality_combo.findData(cur_q)
        self.video_cloud_quality_combo.setCurrentIndex(idx_q if idx_q >= 0 else 0)
        quality_row.addWidget(self.video_cloud_quality_combo)
        layout.addLayout(quality_row)

        cloud_action_row = QHBoxLayout()
        self.video_cloud_test_btn = QPushButton("测试云端图转视频")
        self.video_cloud_test_btn.clicked.connect(self._test_video_cloud_api)
        cloud_action_row.addWidget(self.video_cloud_test_btn)
        cloud_action_row.addStretch(1)
        layout.addLayout(cloud_action_row)

        frame.setLayout(layout)
        return frame

    def _test_video_cloud_api(self) -> None:
        """测试云端图转视频接口连通性（轻量提交）。"""
        submit_url = (self.video_cloud_submit_input.text() if hasattr(self, "video_cloud_submit_input") else "").strip()
        api_key = (self.video_cloud_api_key_input.text() if hasattr(self, "video_cloud_api_key_input") else "").strip()
        model = (self.video_cloud_model_input.text() if hasattr(self, "video_cloud_model_input") else "").strip()
        if not submit_url:
            QMessageBox.warning(self, "参数缺失", "请先填写提交接口 URL")
            return
        if not api_key:
            QMessageBox.warning(self, "参数缺失", "请先填写 VIDEO_CLOUD_API_KEY")
            return
        if not model:
            QMessageBox.warning(self, "参数缺失", "请先填写模型 ID")
            return

        # 生成 >=300px 的测试图片（避免 1x1 被拒绝）
        image_data = ""
        try:
            img = QImage(320, 320, QImage.Format_RGB32)
            img.fill(QColor(255, 255, 255))
            buf = QBuffer()
            buf.open(QBuffer.ReadWrite)
            img.save(buf, "PNG")
            raw = bytes(buf.data())
            b64 = base64.b64encode(raw).decode("utf-8")
            image_data = f"data:image/png;base64,{b64}"
        except Exception:
            image_data = ""
        if not image_data:
            QMessageBox.warning(self, "失败", "生成测试图片失败，无法测试连通性")
            if btn:
                btn.setEnabled(True)
                btn.setText("测试云端图转视频")
            return
        payload = {
            "model": model,
            "content": [
                {"type": "text", "text": "ping"},
                {"type": "image_url", "image_url": {"url": image_data}, "role": "first_frame"},
            ],
            "ratio": "9:16",
            "duration": 4,
            "resolution": "480p",
            "watermark": False,
            "camera_fixed": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        btn = self.sender()
        if btn:
            btn.setEnabled(False)
            btn.setText("测试中...")
        QApplication.processEvents()

        try:
            resp = requests.post(submit_url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                QMessageBox.information(self, "成功", "云端图转视频接口连通正常（已成功提交测试任务）。")
            else:
                text = (resp.text or "")[:200]
                QMessageBox.warning(self, "失败", f"提交失败 HTTP {resp.status_code}: {text}")
        except Exception as e:
            QMessageBox.critical(self, "异常", f"测试失败：{e}")
        finally:
            if btn:
                btn.setEnabled(True)
                btn.setText("测试云端图转视频")
    
    def save_settings(self):
        """保存设置到 .env，并热更新内存配置。"""
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
            ai_role = self.ai_role_input.toPlainText().strip() if hasattr(self, "ai_role_input") else ""
            config.set_config("AI_PROVIDER", ai_provider, persist=True, hot_reload=False)
            config.set_config("AI_BASE_URL", ai_base_url, persist=True, hot_reload=False)
            config.set_config("AI_MODEL", ai_model, persist=True, hot_reload=False)
            config.set_config("AI_API_KEY", ai_api_key, persist=True, hot_reload=False)
            config.set_config("AI_SYSTEM_PROMPT", ai_role, persist=True, hot_reload=False)

            if hasattr(self, "ai_doubao_api_key_input"):
                config.set_config("AI_DOUBAO_API_KEY", self.ai_doubao_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_doubao_base_url_input"):
                config.set_config("AI_DOUBAO_BASE_URL", self.ai_doubao_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_qwen_api_key_input"):
                config.set_config("AI_QWEN_API_KEY", self.ai_qwen_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_qwen_base_url_input"):
                config.set_config("AI_QWEN_BASE_URL", self.ai_qwen_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_deepseek_api_key_input"):
                config.set_config("AI_DEEPSEEK_API_KEY", self.ai_deepseek_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_deepseek_base_url_input"):
                config.set_config("AI_DEEPSEEK_BASE_URL", self.ai_deepseek_base_url_input.text().strip(), persist=True, hot_reload=False)

            # 任务级覆盖（可选）
            if hasattr(self, "ai_copywriter_model_combo"):
                config.set_config("AI_COPYWRITER_MODEL", self.ai_copywriter_model_combo.currentText().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_copywriter_base_url_input"):
                config.set_config("AI_COPYWRITER_BASE_URL", self.ai_copywriter_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_copywriter_api_key_input"):
                config.set_config("AI_COPYWRITER_API_KEY", self.ai_copywriter_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_copywriter_provider_combo"):
                config.set_config("AI_COPYWRITER_PROVIDER", self.ai_copywriter_provider_combo.currentData() or "", persist=True, hot_reload=False)

            if hasattr(self, "ai_factory_model_combo"):
                config.set_config("AI_FACTORY_MODEL", self.ai_factory_model_combo.currentText().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_factory_base_url_input"):
                config.set_config("AI_FACTORY_BASE_URL", self.ai_factory_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_factory_api_key_input"):
                config.set_config("AI_FACTORY_API_KEY", self.ai_factory_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_factory_provider_combo"):
                config.set_config("AI_FACTORY_PROVIDER", self.ai_factory_provider_combo.currentData() or "", persist=True, hot_reload=False)

            if hasattr(self, "ai_timeline_model_combo"):
                config.set_config("AI_TIMELINE_MODEL", self.ai_timeline_model_combo.currentText().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_timeline_base_url_input"):
                config.set_config("AI_TIMELINE_BASE_URL", self.ai_timeline_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_timeline_api_key_input"):
                config.set_config("AI_TIMELINE_API_KEY", self.ai_timeline_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_timeline_provider_combo"):
                config.set_config("AI_TIMELINE_PROVIDER", self.ai_timeline_provider_combo.currentData() or "", persist=True, hot_reload=False)

            if hasattr(self, "ai_photo_model_combo"):
                config.set_config("AI_PHOTO_MODEL", self.ai_photo_model_combo.currentText().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_photo_base_url_input"):
                config.set_config("AI_PHOTO_BASE_URL", self.ai_photo_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_photo_api_key_input"):
                config.set_config("AI_PHOTO_API_KEY", self.ai_photo_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_photo_provider_combo"):
                config.set_config("AI_PHOTO_PROVIDER", self.ai_photo_provider_combo.currentData() or "", persist=True, hot_reload=False)

            if hasattr(self, "ai_vision_model_combo"):
                config.set_config("AI_VISION_MODEL", self.ai_vision_model_combo.currentText().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_vision_base_url_input"):
                config.set_config("AI_VISION_BASE_URL", self.ai_vision_base_url_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_vision_api_key_input"):
                config.set_config("AI_VISION_API_KEY", self.ai_vision_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "ai_vision_provider_combo"):
                config.set_config("AI_VISION_PROVIDER", self.ai_vision_provider_combo.currentData() or "", persist=True, hot_reload=False)

            # Downloader
            download_dir = self.download_dir_input.text().strip()
            config.set_config("DOWNLOAD_DIR", download_dir, persist=True, hot_reload=False)

            # Other
            config.set_config("IP_CHECK_ENABLED", "true" if self.ip_check_checkbox.isChecked() else "false", persist=True, hot_reload=False)

            # Theme
            theme_mode = self.theme_combo.currentData() or "dark"
            config.set_config("THEME_MODE", theme_mode, persist=True, hot_reload=False)

            if hasattr(self, "update_provider_combo"):
                config.set_config("UPDATE_PROVIDER", self.update_provider_combo.currentData() or "github", persist=True, hot_reload=False)
            if hasattr(self, "update_check_url_input"):
                config.set_config("UPDATE_CHECK_URL", self.update_check_url_input.text().strip(), persist=True, hot_reload=False)

            # Video defaults
            config.set_config("VIDEO_DEEP_REMIX_ENABLED", "1" if self.deep_remix_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_MICRO_ZOOM", "1" if self.micro_zoom_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_ADD_NOISE", "1" if self.noise_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)
            config.set_config("VIDEO_REMIX_STRIP_METADATA", "1" if self.strip_metadata_default_checkbox.isChecked() else "0", persist=True, hot_reload=False)

            if hasattr(self, "video_cloud_enabled_checkbox"):
                config.set_config("VIDEO_CLOUD_ENABLED", "true" if self.video_cloud_enabled_checkbox.isChecked() else "false", persist=True, hot_reload=False)
            if hasattr(self, "video_cloud_api_key_input"):
                config.set_config("VIDEO_CLOUD_API_KEY", self.video_cloud_api_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "video_cloud_submit_input"):
                config.set_config("VIDEO_CLOUD_SUBMIT_URL", self.video_cloud_submit_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "video_cloud_status_input"):
                config.set_config("VIDEO_CLOUD_STATUS_URL", self.video_cloud_status_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "video_cloud_model_input"):
                config.set_config("VIDEO_CLOUD_MODEL", self.video_cloud_model_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "video_cloud_quality_combo"):
                config.set_config("VIDEO_CLOUD_QUALITY", self.video_cloud_quality_combo.currentData() or "low", persist=True, hot_reload=False)

            # TTS
            if hasattr(self, "tts_provider_combo"):
                config.set_config("TTS_PROVIDER", self.tts_provider_combo.currentData() or "edge-tts", persist=True, hot_reload=False)
            if hasattr(self, "tts_fallback_combo"):
                config.set_config("TTS_FALLBACK_PROVIDER", self.tts_fallback_combo.currentData() or "", persist=True, hot_reload=False)
            if hasattr(self, "tts_voice_input"):
                config.set_config("TTS_VOICE", self.tts_voice_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "tts_speed_input"):
                config.set_config("TTS_SPEED", self.tts_speed_input.text().strip() or "1.0", persist=True, hot_reload=False)
            if hasattr(self, "tts_emotion_preset_combo"):
                config.set_config("TTS_EMOTION_PRESET", self.tts_emotion_preset_combo.currentData() or "", persist=True, hot_reload=False)
            if hasattr(self, "tts_emotion_intensity_combo"):
                config.set_config("TTS_EMOTION_INTENSITY", self.tts_emotion_intensity_combo.currentData() or "中", persist=True, hot_reload=False)
            if hasattr(self, "tts_emotion_custom_input"):
                config.set_config("TTS_EMOTION_CUSTOM", self.tts_emotion_custom_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "tts_scene_combo"):
                config.set_config("TTS_SCENE_MODE", self.tts_scene_combo.currentData() or "", persist=True, hot_reload=False)

            if hasattr(self, "volc_endpoint_input"):
                config.set_config("VOLC_TTS_ENDPOINT", self.volc_endpoint_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "volc_appid_input"):
                config.set_config("VOLC_TTS_APPID", self.volc_appid_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "volc_access_token_input"):
                access_token = self.volc_access_token_input.text().strip()
                config.set_config("VOLC_TTS_ACCESS_TOKEN", access_token, persist=True, hot_reload=False)
            if hasattr(self, "volc_secret_key_input"):
                config.set_config("VOLC_TTS_SECRET_KEY", self.volc_secret_key_input.text().strip(), persist=True, hot_reload=False)
            if hasattr(self, "volc_cluster_input"):
                config.set_config("VOLC_TTS_CLUSTER", self.volc_cluster_input.text().strip() or "volcano_tts", persist=True, hot_reload=False)
            if hasattr(self, "volc_voice_input"):
                try:
                    voice_type = (self.volc_voice_input.currentText() or "").strip()
                except Exception:
                    voice_type = ""
                config.set_config("VOLC_TTS_VOICE_TYPE", voice_type, persist=True, hot_reload=False)
            if hasattr(self, "volc_encoding_input"):
                config.set_config("VOLC_TTS_ENCODING", self.volc_encoding_input.text().strip() or "mp3", persist=True, hot_reload=False)

            # 3. Reload config in-memory (保证保存后立即生效)
            config.reload_config()

            # 4. Apply theme immediately
            try:
                app = QApplication.instance()
                if app:
                    apply_global_theme(app, getattr(config, "THEME_MODE", "dark"))
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


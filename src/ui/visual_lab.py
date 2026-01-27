"""视觉实验室（视频拆解与脚本反推）"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
    QComboBox,
)

import config
from workers.visual_analysis_worker import VisualAnalysisWorker
from utils.ui_log import append_log, install_log_context_menu
from utils.ai_models_cache import get_provider_models, list_ok_providers
from ui.role_prompt_dialog import open_role_prompt_dialog

_PROVIDER_LABELS = {
    "doubao": "豆包/火山",
    "qwen": "千问/通义",
    "deepseek": "DeepSeek",
}


class VisualLabPanel(QWidget):
    """视觉实验室 UI 面板"""

    def __init__(self) -> None:
        super().__init__()
        self.worker: VisualAnalysisWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("视觉实验室")
        title.setObjectName("h1")
        layout.addWidget(title)

        desc = QLabel("用途：上传竞品视频，自动抽帧并反推拍摄脚本，识别前三秒视觉钩子。")
        desc.setProperty("variant", "muted")
        layout.addWidget(desc)

        config_frame = QFrame()
        config_frame.setProperty("class", "config-frame")
        form = QVBoxLayout(config_frame)

        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("视频文件："))
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("请选择 .mp4/.mov/... 文件")
        row_video.addWidget(self.video_path_input, 1)
        pick_btn = QPushButton("选择视频")
        pick_btn.clicked.connect(self._pick_video)
        row_video.addWidget(pick_btn)
        form.addLayout(row_video)

        row_interval = QHBoxLayout()
        row_interval.addWidget(QLabel("抽帧间隔(秒)："))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 10.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(2.0)
        row_interval.addWidget(self.interval_spin)
        row_interval.addStretch(1)
        form.addLayout(row_interval)

        row_ai = QHBoxLayout()
        row_ai.addWidget(QLabel("AI 供应商："))
        self.vision_provider_combo = QComboBox()
        cur_provider = (getattr(config, "AI_VISION_PROVIDER", "") or "").strip()
        self._setup_provider_combo(self.vision_provider_combo, cur_provider)
        row_ai.addWidget(self.vision_provider_combo)

        row_ai.addWidget(QLabel("视觉模型："))
        self.vision_model_combo = QComboBox()
        row_ai.addWidget(self.vision_model_combo)
        
        try:
            self.vision_provider_combo.currentIndexChanged.connect(self._refresh_vision_models)
        except Exception:
            pass
        self._refresh_vision_models()
        
        row_ai.addStretch(1)
        form.addLayout(row_ai)

        row_btn = QHBoxLayout()
        self.start_btn = QPushButton("开始拆解")
        self.start_btn.setProperty("variant", "primary")
        self.start_btn.clicked.connect(self._start_analysis)
        row_btn.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop_analysis)
        self.stop_btn.setEnabled(False)
        row_btn.addWidget(self.stop_btn)
        row_btn.addStretch(1)
        form.addLayout(row_btn)

        layout.addWidget(config_frame)

        # AI 角色配置
        role_frame = QFrame()
        role_frame.setProperty("class", "config-frame")
        role_layout = QVBoxLayout(role_frame)
        
        role_header = QHBoxLayout()
        role_header.addWidget(QLabel("当前生效角色提示词："))
        role_header.addStretch(1)
        
        btn_role = QPushButton("🎭 配置AI角色")
        btn_role.setFixedSize(120, 35) 
        btn_role.clicked.connect(self._open_role_prompt_dialog)
        role_header.addWidget(btn_role)
        
        role_layout.addLayout(role_header)
        
        self.role_preview = QTextEdit()
        self.role_preview.setReadOnly(True)
        self.role_preview.setMinimumHeight(90)
        self.role_preview.setPlaceholderText("将显示当前视觉分析实际使用的角色提示词。")
        role_layout.addWidget(self.role_preview)
        layout.addWidget(role_frame)

        result_frame = QFrame()
        result_frame.setProperty("class", "config-frame")

        log_frame = QFrame()
        log_frame.setProperty("class", "config-frame")
        log_layout = QVBoxLayout(log_frame)
        log_layout.addWidget(QLabel("运行日志："))
        log_toolbar = QHBoxLayout()
        btn_copy_log = QPushButton("复制日志")
        btn_copy_log.setProperty("class", "toolbar-btn")
        btn_copy_log.clicked.connect(self._copy_log)
        log_toolbar.addWidget(btn_copy_log)
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.setProperty("class", "toolbar-btn")
        btn_clear_log.clicked.connect(self._clear_log)
        log_toolbar.addWidget(btn_clear_log)
        btn_open_out = QPushButton("打开输出目录")
        btn_open_out.setProperty("class", "toolbar-btn")
        btn_open_out.clicked.connect(self._open_output_dir)
        log_toolbar.addWidget(btn_open_out)
        log_toolbar.addStretch(1)
        log_layout.addLayout(log_toolbar)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        self.log_view.setMinimumHeight(180)
        install_log_context_menu(self.log_view)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_frame)

        layout.addStretch(1)
        self.setLayout(layout)
        try:
            self._update_role_preview()
        except Exception:
            pass

    def refresh(self):
        try:
            self._setup_provider_combo(self.vision_provider_combo, getattr(config, "AI_VISION_PROVIDER", ""))
            self._refresh_vision_models()
        except Exception:
            pass

    def _setup_provider_combo(self, combo: QComboBox, current_provider: str = "") -> None:
        ok_providers = set(list_ok_providers())
        try:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("默认（系统设置）", "")
            for key in ("doubao", "qwen", "deepseek"):
                if key in ok_providers:
                    combo.addItem(_PROVIDER_LABELS.get(key, key), key)
            idx = combo.findData((current_provider or "").strip())
            if idx >= 0:
                combo.setCurrentIndex(idx)
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _fill_model_combo(self, combo: QComboBox, models: list[str], fallback_model: str = "") -> None:
        try:
            combo.blockSignals(True)
            combo.clear()
            clean_models = [m for m in (models or []) if m]
            if clean_models:
                combo.addItems(clean_models)
            else:
                if fallback_model:
                    combo.addItem(fallback_model)
                else:
                    combo.addItem("（未获取模型）")
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _refresh_vision_models(self) -> None:
        provider = ""
        try:
            provider = self.vision_provider_combo.currentData() or ""
        except Exception:
            provider = ""
        models = get_provider_models(provider) if provider else []
        fallback = (
            (getattr(config, "AI_VISION_MODEL", "") or "").strip()
            or (getattr(config, "AI_MODEL", "") or "").strip()
        )
        self._fill_model_combo(self.vision_model_combo, models, fallback)

    def _pick_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)",
        )
        if file_path:
            self.video_path_input.setText(file_path)

    def _start_analysis(self) -> None:
        video_path = (self.video_path_input.text() or "").strip()
        if not video_path:
            append_log(self.log_view, "请先选择视频文件", level="WARNING")
            return
        if not Path(video_path).exists():
            append_log(self.log_view, "视频文件不存在", level="ERROR")
            return

        self.result_view.clear()
        self.log_view.clear()
        append_log(self.log_view, "开始视觉分析...")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.worker = VisualAnalysisWorker(
            video_path=video_path,
            interval_sec=float(self.interval_spin.value()),
            model=(self.vision_model_combo.currentText() or "").strip(),
            provider=(self.vision_provider_combo.currentData() or ""),
            role_prompt=(getattr(config, "AI_VISION_ROLE_PROMPT", "") or "").strip(),
        )
        self.worker.log_signal.connect(lambda m: append_log(self.log_view, m))
        self.worker.data_signal.connect(self._on_result)
        self.worker.done_signal.connect(self._on_done)
        self.worker.start()

    def _stop_analysis(self) -> None:
        if self.worker:
            try:
                self.worker.stop()
            except Exception:
                pass
        append_log(self.log_view, "已发送停止信号", level="WARNING")

    def _on_result(self, text: object) -> None:
        try:
            self.result_view.setPlainText(str(text or ""))
        except Exception:
            pass

    def _on_done(self, ok: bool, message: str) -> None:
        if message:
            append_log(self.log_view, message, level="INFO" if ok else "ERROR")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None

    def _copy_log(self) -> None:
        try:
            text = (self.log_view.toPlainText() or "").strip()
            if not text:
                return
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
        except Exception:
            pass

    def _clear_log(self) -> None:
        try:
            self.log_view.clear()
        except Exception:
            pass

    def _open_output_dir(self) -> None:
        try:
            import os
            base_dir = Path(getattr(config, "OUTPUT_DIR", Path("Output"))) / "Visual_Lab"
            os.startfile(str(base_dir))
        except Exception:
            pass

    def _open_role_prompt_dialog(self) -> None:
        """配置视觉实验室的角色提示词（持久化到 .env）。"""
        current = (getattr(config, "AI_VISION_ROLE_PROMPT", "") or "").strip()
        text = open_role_prompt_dialog(
            self,
            title="视觉实验室角色提示词",
            initial_text=current,
            help_text="将作为系统提示词注入视觉模型（分析风格/角度/输出结构）。",
        )
        if text is None:
            return
        try:
            config.set_config("AI_VISION_ROLE_PROMPT", text, persist=True, hot_reload=False)
        except Exception:
            pass
        self._update_role_preview()

    def _update_role_preview(self) -> None:
        """刷新视觉实验室当前生效角色提示词预览。"""
        text = (getattr(config, "AI_VISION_ROLE_PROMPT", "") or "").strip()
        if not text:
            system_saved = (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
            if system_saved:
                text = system_saved
            else:
                text = "默认内置角色：无额外角色提示词（仅使用问题描述进行分析）。"
        try:
            self.role_preview.setPlainText(text)
        except Exception:
            pass

"""AI 二创工厂 UI 面板 (V2.0)

功能：
- 选择本地视频
- 输入商品/视频描述
- 调用 AIContentWorker 生成脚本 + TTS + 混音输出

说明：本面板只做 UI 编排与线程调度，不做耗时任务。
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QFileDialog,
    QFrame,
    QMessageBox,
    QComboBox,
    QCheckBox,
    QTabWidget,
    QDoubleSpinBox,
    QSpinBox,
)

import config
from workers.ai_content_worker import AIContentWorker
from workers.ai_script_worker import AIScriptWorker
from utils.ui_log import append_log, install_log_context_menu


class AIContentFactoryPanel(QWidget):
    """AI 二创工厂（视频自动二创）"""

    def __init__(self):
        super().__init__()
        self.worker: AIContentWorker | None = None
        self.script_worker: AIScriptWorker | None = None
        self._approved_script_text: str = ""
        self._approved_script_json: dict | None = None

        # 自定义角色提示词：轻量防抖，避免频繁写 .env
        self._role_save_timer = QTimer(self)
        self._role_save_timer.setSingleShot(True)
        self._role_save_timer.setInterval(800)
        self._role_save_timer.timeout.connect(self._persist_custom_role_prompt)

        # 字幕样式：轻量防抖写入 .env（拖动 SpinBox 时避免频繁落盘）
        self._subtitle_save_timer = QTimer(self)
        self._subtitle_save_timer.setSingleShot(True)
        self._subtitle_save_timer.setInterval(600)
        self._subtitle_save_timer.timeout.connect(self._persist_subtitle_style)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("AI 二创工厂")
        title.setObjectName("h1")
        layout.addWidget(title)

        desc = QLabel(
            "用途：给一段商品/视频描述 + 原始视频，自动生成解说脚本并合成配音，输出‘伪原创’解说视频。\n"
            "提示：请先在【系统设置】配置 AI_MODEL 与 TTS；首次运行可能较慢（需要合成语音/渲染视频）。"
        )
        desc.setProperty("variant", "muted")
        layout.addWidget(desc)

        # 可切换式界面：标签页（避免内容挤压）
        self.tabs = QTabWidget()
        self.tabs.setObjectName("AIContentTabs")

        # ===================== Tab 1: 基础信息 =====================
        base_tab = QWidget()
        base_layout = QVBoxLayout(base_tab)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(12)

        basic_frame = QFrame()
        basic_frame.setProperty("class", "config-frame")
        basic_form = QVBoxLayout(basic_frame)

        basic_title = QLabel("基础信息")
        basic_title.setObjectName("h2")
        basic_form.addWidget(basic_title)

        basic_form.addWidget(QLabel("商品信息描述："))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(
            "产品: 迷你风扇\n卖点: 静音、续航长、夹子可夹在床边，适合宿舍使用"
        )
        self.desc_input.setMinimumHeight(220)
        basic_form.addWidget(self.desc_input)

        video_row = QHBoxLayout()
        video_row.addWidget(QLabel("视频文件："))
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("请选择 .mp4/.mov/... 文件")
        video_row.addWidget(self.video_path_input, 1)
        pick_btn = QPushButton("选择视频")
        pick_btn.clicked.connect(self._pick_video)
        video_row.addWidget(pick_btn)
        basic_form.addLayout(video_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出目录："))
        default_out = str((getattr(config, "OUTPUT_DIR", Path("Output")) / "AI_Videos").resolve())
        self.output_dir_input = QLineEdit(default_out)
        out_row.addWidget(self.output_dir_input, 1)
        out_pick_btn = QPushButton("选择目录")
        out_pick_btn.clicked.connect(self._pick_output_dir)
        out_row.addWidget(out_pick_btn)
        basic_form.addLayout(out_row)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("AI 角色："))
        self.role_combo = QComboBox()
        self.role_combo.addItems([
            "默认（使用系统设置）",
            "TK带货主播",
            "专业测评博主",
            "幽默搞笑旁白",
            "情绪共鸣治愈",
        ])
        opts_row.addWidget(self.role_combo)

        opts_row.addWidget(QLabel("使用模型："))
        use_model = (
            (getattr(config, "AI_MODEL", "") or "").strip()
            or "（未配置）"
        )
        self.model_label = QLabel(use_model)
        self.model_label.setProperty("variant", "muted")
        opts_row.addWidget(self.model_label)

        self.skip_tts_checkbox = QCheckBox("配音失败自动降级（仍输出脚本+复制原视频）")
        self.skip_tts_checkbox.setChecked(True)
        opts_row.addWidget(self.skip_tts_checkbox)
        opts_row.addStretch(1)
        basic_form.addLayout(opts_row)

        role_frame = QFrame()
        role_frame.setProperty("class", "config-frame")
        role_form = QVBoxLayout(role_frame)
        role_title = QLabel("角色与风格")
        role_title.setObjectName("h2")
        role_form.addWidget(role_title)

        role_form.addWidget(QLabel("自定义角色提示词（可选，留空则使用预设/系统设置）："))
        self.role_input = QTextEdit()
        self.role_input.setPlaceholderText(
            "例：你是一名强转化的 TikTok 带货主播，台词要短句、强 CTA、节奏快。"
        )
        self.role_input.setMinimumHeight(160)
        try:
            self.role_input.setText((getattr(config, "AI_FACTORY_ROLE_PROMPT", "") or ""))
        except Exception:
            pass
        try:
            self.role_input.textChanged.connect(self._schedule_persist_custom_role_prompt)
        except Exception:
            pass
        role_form.addWidget(self.role_input)

        base_layout.addWidget(basic_frame)
        base_layout.addWidget(role_frame)
        base_layout.addStretch(1)

        # ===================== Tab 2: 脚本生成 =====================
        script_tab = QWidget()
        script_layout = QVBoxLayout(script_tab)
        script_layout.setContentsMargins(0, 0, 0, 0)
        script_layout.setSpacing(12)

        step1_frame = QFrame()
        step1_frame.setProperty("class", "config-frame")
        step1_form = QVBoxLayout(step1_frame)

        step1_title = QLabel("Step 1：生成口播脚本（严格校验）")
        step1_title.setObjectName("h2")
        step1_form.addWidget(step1_title)

        self.script_status_label = QLabel("状态：未生成")
        self.script_status_label.setProperty("variant", "muted")
        step1_form.addWidget(self.script_status_label)

        self.script_preview = QTextEdit()
        self.script_preview.setPlaceholderText("脚本将显示在这里（通过校验后，点击‘通过并进入下一步’）")
        self.script_preview.setMinimumHeight(380)
        try:
            self.script_preview.textChanged.connect(self._on_script_text_changed)
        except Exception:
            pass
        step1_form.addWidget(self.script_preview)

        script_btn_row = QHBoxLayout()
        self.gen_script_btn = QPushButton("生成脚本")
        self.gen_script_btn.clicked.connect(self._generate_script)
        script_btn_row.addWidget(self.gen_script_btn)

        self.retry_script_btn = QPushButton("不通过，重新生成")
        self.retry_script_btn.clicked.connect(self._retry_script)
        self.retry_script_btn.setEnabled(False)
        script_btn_row.addWidget(self.retry_script_btn)

        self.approve_script_btn = QPushButton("通过并进入下一步")
        self.approve_script_btn.setProperty("variant", "primary")
        self.approve_script_btn.clicked.connect(self._approve_script)
        self.approve_script_btn.setEnabled(False)
        script_btn_row.addWidget(self.approve_script_btn)

        view_log_btn = QPushButton("查看日志")
        view_log_btn.clicked.connect(lambda: self._switch_to_tab("log"))
        script_btn_row.addWidget(view_log_btn)

        script_btn_row.addStretch(1)
        step1_form.addLayout(script_btn_row)

        script_layout.addWidget(step1_frame)
        script_layout.addStretch(1)

        # ===================== Tab 3: 合成输出 =====================
        compose_tab = QWidget()
        compose_layout = QVBoxLayout(compose_tab)
        compose_layout.setContentsMargins(0, 0, 0, 0)
        compose_layout.setSpacing(12)

        step2_frame = QFrame()
        step2_frame.setProperty("class", "config-frame")
        step2_form = QVBoxLayout(step2_frame)

        step2_title = QLabel("Step 2：合成配音并混音输出")
        step2_title.setObjectName("h2")
        step2_form.addWidget(step2_title)

        self.compose_hint_label = QLabel("提示：请先在【脚本生成】页通过校验后再开始合成。")
        self.compose_hint_label.setProperty("variant", "muted")
        step2_form.addWidget(self.compose_hint_label)

        # 字幕样式（可配置 + 持久化到 .env）
        subtitle_frame = QFrame()
        subtitle_frame.setProperty("class", "config-frame")
        subtitle_form = QVBoxLayout(subtitle_frame)

        subtitle_title = QLabel("字幕样式（TikTok 风格）")
        subtitle_title.setObjectName("h2")
        subtitle_form.addWidget(subtitle_title)

        subtitle_tip = QLabel("说明：这些设置仅影响【烧录字幕到视频】的样式；会自动保存到 .env，后续打开无需重复设置。")
        subtitle_tip.setProperty("variant", "muted")
        subtitle_form.addWidget(subtitle_tip)

        row1 = QHBoxLayout()
        self.subtitle_burn_checkbox = QCheckBox("烧录字幕到视频（推荐）")
        self.subtitle_burn_checkbox.setChecked(bool(getattr(config, "SUBTITLE_BURN_ENABLED", True)))
        self.subtitle_burn_checkbox.stateChanged.connect(self._schedule_persist_subtitle_style)
        row1.addWidget(self.subtitle_burn_checkbox)

        row1.addWidget(QLabel("字体："))
        self.subtitle_font_combo = QComboBox()
        self.subtitle_font_combo.addItems([
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "SimHei",
            "Arial",
        ])
        try:
            current_font = (getattr(config, "SUBTITLE_FONT_NAME", "Microsoft YaHei UI") or "Microsoft YaHei UI").strip()
        except Exception:
            current_font = "Microsoft YaHei UI"
        if current_font:
            idx = self.subtitle_font_combo.findText(current_font)
            if idx >= 0:
                self.subtitle_font_combo.setCurrentIndex(idx)
        self.subtitle_font_combo.currentIndexChanged.connect(self._schedule_persist_subtitle_style)
        row1.addWidget(self.subtitle_font_combo)
        row1.addStretch(1)
        subtitle_form.addLayout(row1)

        row2 = QHBoxLayout()
        self.subtitle_font_auto_checkbox = QCheckBox("字号自动按分辨率")
        self.subtitle_font_auto_checkbox.setChecked(bool(getattr(config, "SUBTITLE_FONT_AUTO", True)))
        self.subtitle_font_auto_checkbox.stateChanged.connect(self._on_subtitle_font_auto_changed)
        row2.addWidget(self.subtitle_font_auto_checkbox)

        row2.addWidget(QLabel("字号(px)："))
        self.subtitle_font_size = QSpinBox()
        self.subtitle_font_size.setRange(10, 140)
        try:
            fs = int(getattr(config, "SUBTITLE_FONT_SIZE", 56) or 56)
        except Exception:
            fs = 56
        self.subtitle_font_size.setValue(max(10, min(140, fs)))
        self.subtitle_font_size.valueChanged.connect(self._schedule_persist_subtitle_style)
        row2.addWidget(self.subtitle_font_size)

        self.subtitle_outline_auto_checkbox = QCheckBox("描边自动按字号")
        self.subtitle_outline_auto_checkbox.setChecked(bool(getattr(config, "SUBTITLE_OUTLINE_AUTO", True)))
        self.subtitle_outline_auto_checkbox.stateChanged.connect(self._on_subtitle_outline_auto_changed)
        row2.addWidget(self.subtitle_outline_auto_checkbox)

        row2.addWidget(QLabel("描边(px)："))
        self.subtitle_outline = QSpinBox()
        # “无上限”理念：UI 给足够大的上限；worker 侧不做上限裁剪
        self.subtitle_outline.setRange(0, 9999)
        try:
            opx = int(getattr(config, "SUBTITLE_OUTLINE", 4) or 4)
        except Exception:
            opx = 4
        self.subtitle_outline.setValue(max(0, opx))
        self.subtitle_outline.valueChanged.connect(self._schedule_persist_subtitle_style)
        row2.addWidget(self.subtitle_outline)

        row2.addWidget(QLabel("阴影(px)："))
        self.subtitle_shadow = QSpinBox()
        self.subtitle_shadow.setRange(0, 8)
        try:
            s = int(getattr(config, "SUBTITLE_SHADOW", 2) or 2)
        except Exception:
            s = 2
        self.subtitle_shadow.setValue(max(0, min(8, s)))
        self.subtitle_shadow.valueChanged.connect(self._schedule_persist_subtitle_style)
        row2.addWidget(self.subtitle_shadow)

        row2.addStretch(1)
        subtitle_form.addLayout(row2)

        # 初始态：自动字号/描边时禁用 px 输入
        try:
            self._apply_subtitle_font_auto_ui()
            self._apply_subtitle_outline_auto_ui()
        except Exception:
            pass

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("底部距离（相对高度%）："))
        self.subtitle_margin_v_ratio = QDoubleSpinBox()
        self.subtitle_margin_v_ratio.setRange(4.0, 18.0)
        self.subtitle_margin_v_ratio.setDecimals(2)
        self.subtitle_margin_v_ratio.setSingleStep(0.2)
        try:
            mv = float(getattr(config, "SUBTITLE_MARGIN_V_RATIO", 0.095) or 0.095) * 100.0
        except Exception:
            mv = 9.5
        self.subtitle_margin_v_ratio.setValue(max(4.0, min(18.0, mv)))
        self.subtitle_margin_v_ratio.valueChanged.connect(self._schedule_persist_subtitle_style)
        row3.addWidget(self.subtitle_margin_v_ratio)

        row3.addWidget(QLabel("左右边距(px)："))
        self.subtitle_margin_lr = QSpinBox()
        self.subtitle_margin_lr.setRange(0, 200)
        try:
            mlr = int(getattr(config, "SUBTITLE_MARGIN_LR", 40) or 40)
        except Exception:
            mlr = 40
        self.subtitle_margin_lr.setValue(max(0, min(200, mlr)))
        self.subtitle_margin_lr.valueChanged.connect(self._schedule_persist_subtitle_style)
        row3.addWidget(self.subtitle_margin_lr)

        reset_btn = QPushButton("恢复推荐样式")
        reset_btn.clicked.connect(self._reset_subtitle_style)
        row3.addWidget(reset_btn)

        row3.addStretch(1)
        subtitle_form.addLayout(row3)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始合成（TTS + 混音）")
        self.start_btn.setProperty("variant", "primary")
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)

        self.open_out_btn = QPushButton("打开输出目录")
        self.open_out_btn.clicked.connect(self._open_output_dir)
        btn_row.addWidget(self.open_out_btn)

        back_script_btn = QPushButton("返回脚本")
        back_script_btn.clicked.connect(lambda: self._switch_to_tab("script"))
        btn_row.addWidget(back_script_btn)

        view_log_btn2 = QPushButton("查看日志")
        view_log_btn2.clicked.connect(lambda: self._switch_to_tab("log"))
        btn_row.addWidget(view_log_btn2)

        btn_row.addStretch(1)
        step2_form.addLayout(btn_row)

        compose_layout.addWidget(subtitle_frame)

        compose_layout.addWidget(step2_frame)
        compose_layout.addStretch(1)

        # ===================== Tab 4: 运行日志 =====================
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(12)

        log_frame = QFrame()
        log_frame.setProperty("class", "config-frame")
        log_form = QVBoxLayout(log_frame)

        log_title = QLabel("运行日志")
        log_title.setObjectName("h2")
        log_form.addWidget(log_title)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        self.log_view.setMinimumHeight(520)
        install_log_context_menu(self.log_view)
        log_form.addWidget(self.log_view, 1)

        log_layout.addWidget(log_frame, 1)

        # Tab 注册
        self.tabs.addTab(base_tab, "① 基础信息")
        self.tabs.addTab(script_tab, "② 脚本生成")
        self.tabs.addTab(compose_tab, "③ 合成输出")
        self.tabs.addTab(log_tab, "运行日志")

        layout.addWidget(self.tabs, 1)

        self.setLayout(layout)

    def _switch_to_tab(self, key: str) -> None:
        try:
            key = (key or "").strip().lower()
            mapping = {
                "base": 0,
                "script": 1,
                "compose": 2,
                "log": 3,
            }
            idx = mapping.get(key, None)
            if idx is None:
                return
            if hasattr(self, "tabs"):
                self.tabs.setCurrentIndex(idx)
        except Exception:
            pass

    def _on_script_text_changed(self) -> None:
        """用户手动修改脚本后，取消“已通过”状态，避免误合成。"""
        try:
            current = (self.script_preview.toPlainText() or "").strip()
            approved = (self._approved_script_text or "").strip()
            if approved and current != approved:
                self._approved_script_text = ""
                self._approved_script_json = None
                self.start_btn.setEnabled(False)
                self.approve_script_btn.setEnabled(False)
                self.script_status_label.setText("状态：已修改（需重新生成）")
                self.retry_script_btn.setEnabled(True)
        except Exception:
            pass

    def _append(self, text: str, level: str = "INFO") -> None:
        append_log(self.log_view, text, level=level)

    def _schedule_persist_custom_role_prompt(self) -> None:
        try:
            self._role_save_timer.start()
        except Exception:
            pass

    def _persist_custom_role_prompt(self) -> None:
        try:
            text = (self.role_input.toPlainText() if hasattr(self, "role_input") else "")
            text = (text or "").strip()
            config.set_config("AI_FACTORY_ROLE_PROMPT", text, persist=True, hot_reload=False)
        except Exception:
            pass

    def _schedule_persist_subtitle_style(self) -> None:
        try:
            self._subtitle_save_timer.start()
        except Exception:
            pass

    def _reset_subtitle_style(self) -> None:
        """一键恢复推荐 TikTok 样式，并自动保存。"""
        try:
            if hasattr(self, "subtitle_burn_checkbox"):
                self.subtitle_burn_checkbox.setChecked(True)
            if hasattr(self, "subtitle_font_combo"):
                idx = self.subtitle_font_combo.findText("Microsoft YaHei UI")
                if idx >= 0:
                    self.subtitle_font_combo.setCurrentIndex(idx)
            if hasattr(self, "subtitle_font_auto_checkbox"):
                self.subtitle_font_auto_checkbox.setChecked(True)
            if hasattr(self, "subtitle_font_size"):
                self.subtitle_font_size.setValue(56)
            if hasattr(self, "subtitle_outline_auto_checkbox"):
                self.subtitle_outline_auto_checkbox.setChecked(False)
            if hasattr(self, "subtitle_outline"):
                self.subtitle_outline.setValue(4)
            if hasattr(self, "subtitle_shadow"):
                self.subtitle_shadow.setValue(0)
            if hasattr(self, "subtitle_margin_v_ratio"):
                self.subtitle_margin_v_ratio.setValue(9.5)
            if hasattr(self, "subtitle_margin_lr"):
                self.subtitle_margin_lr.setValue(40)

            try:
                self._apply_subtitle_outline_auto_ui()
            except Exception:
                pass
            self._schedule_persist_subtitle_style()
        except Exception:
            pass

    def _on_subtitle_font_auto_changed(self) -> None:
        try:
            self._apply_subtitle_font_auto_ui()
        except Exception:
            pass
        self._schedule_persist_subtitle_style()

    def _on_subtitle_outline_auto_changed(self) -> None:
        try:
            self._apply_subtitle_outline_auto_ui()
        except Exception:
            pass
        self._schedule_persist_subtitle_style()

    def _apply_subtitle_font_auto_ui(self) -> None:
        try:
            auto = bool(self.subtitle_font_auto_checkbox.isChecked()) if hasattr(self, "subtitle_font_auto_checkbox") else True
            if hasattr(self, "subtitle_font_size"):
                self.subtitle_font_size.setEnabled(not auto)
        except Exception:
            pass

    def _apply_subtitle_outline_auto_ui(self) -> None:
        try:
            auto = bool(self.subtitle_outline_auto_checkbox.isChecked()) if hasattr(self, "subtitle_outline_auto_checkbox") else True
            if hasattr(self, "subtitle_outline"):
                self.subtitle_outline.setEnabled(not auto)
        except Exception:
            pass

    def _persist_subtitle_style(self) -> None:
        """写回 .env 并热更新内存 config（避免下次打开还要再设置）。"""
        try:
            burn = True
            if hasattr(self, "subtitle_burn_checkbox"):
                burn = bool(self.subtitle_burn_checkbox.isChecked())

            font_name = "Microsoft YaHei UI"
            if hasattr(self, "subtitle_font_combo"):
                font_name = (self.subtitle_font_combo.currentText() or "Microsoft YaHei UI").strip() or "Microsoft YaHei UI"

            font_auto = True
            if hasattr(self, "subtitle_font_auto_checkbox"):
                font_auto = bool(self.subtitle_font_auto_checkbox.isChecked())

            font_size_px = 56
            if hasattr(self, "subtitle_font_size"):
                font_size_px = int(self.subtitle_font_size.value())

            outline_auto = True
            if hasattr(self, "subtitle_outline_auto_checkbox"):
                outline_auto = bool(self.subtitle_outline_auto_checkbox.isChecked())

            outline_px = 4
            if hasattr(self, "subtitle_outline"):
                outline_px = int(self.subtitle_outline.value())

            shadow = 2
            if hasattr(self, "subtitle_shadow"):
                shadow = int(self.subtitle_shadow.value())

            margin_v_ratio = 0.095
            if hasattr(self, "subtitle_margin_v_ratio"):
                margin_v_ratio = float(self.subtitle_margin_v_ratio.value() or 9.5) / 100.0

            margin_lr = 40
            if hasattr(self, "subtitle_margin_lr"):
                margin_lr = int(self.subtitle_margin_lr.value())

            # 统一入口写配置（写回 .env + 热更新内存）
            config.set_config("SUBTITLE_BURN_ENABLED", "true" if burn else "false", persist=True, hot_reload=False)
            config.set_config("SUBTITLE_FONT_NAME", font_name, persist=True, hot_reload=False)
            config.set_config("SUBTITLE_FONT_AUTO", "true" if font_auto else "false", persist=True, hot_reload=False)
            config.set_config("SUBTITLE_FONT_SIZE", str(int(font_size_px)), persist=True, hot_reload=False)
            config.set_config("SUBTITLE_OUTLINE_AUTO", "true" if outline_auto else "false", persist=True, hot_reload=False)
            config.set_config("SUBTITLE_OUTLINE", str(int(outline_px)), persist=True, hot_reload=False)
            config.set_config("SUBTITLE_SHADOW", str(int(shadow)), persist=True, hot_reload=False)
            config.set_config("SUBTITLE_MARGIN_V_RATIO", f"{margin_v_ratio:.4f}", persist=True, hot_reload=False)
            config.set_config("SUBTITLE_MARGIN_LR", str(int(margin_lr)), persist=True, hot_reload=False)

            config.reload_config()
        except Exception:
            pass

    def _pick_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频",
            str(getattr(config, "OUTPUT_DIR", Path("."))),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if file_path:
            self.video_path_input.setText(file_path)

    def _pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_dir_input.text().strip() or str(getattr(config, "OUTPUT_DIR", Path("Output"))),
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _open_output_dir(self) -> None:
        out_dir = (self.output_dir_input.text().strip() or "").strip()
        if not out_dir:
            return
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(out_dir).resolve())))
        except Exception:
            # 兜底：使用 file:// 打开
            try:
                QDesktopServices.openUrl(QUrl(Path(out_dir).resolve().as_uri()))
            except Exception:
                pass

    def _start(self) -> None:
        if self.worker:
            QMessageBox.information(self, "提示", "任务正在运行中，请稍候。")
            return

        if not (self._approved_script_text or "").strip():
            QMessageBox.warning(self, "请先生成脚本", "请先完成 Step 1 脚本生成并点击‘通过并进入下一步’。")
            return

        desc = self.desc_input.toPlainText().strip()
        video_path = self.video_path_input.text().strip()
        out_dir = self.output_dir_input.text().strip()

        if not desc:
            QMessageBox.warning(self, "参数缺失", "请先填写【商品/视频描述】。")
            return
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "参数缺失", "请选择存在的视频文件。")
            return
        if not out_dir:
            QMessageBox.warning(self, "参数缺失", "请选择输出目录。")
            return

        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "目录不可用", f"输出目录创建失败：{e}")
            return

        self.log_view.clear()
        self._append("开始执行 Step 2：语音合成 + 混音...")

        # 切到日志页，方便查看进度
        self._switch_to_tab("log")

        self.start_btn.setEnabled(False)

        role_prompt = self._role_prompt_from_ui()
        skip_tts = bool(self.skip_tts_checkbox.isChecked())

        # Worker 内部会自己创建输出目录，这里仍传入绝对路径确保一致
        self.worker = AIContentWorker(
            product_desc=desc,
            video_path=video_path,
            output_dir=out_dir,
            skip_tts_failure=skip_tts,
            role_prompt=role_prompt,
            script_text=self._approved_script_text,
        )
        self.worker.progress.connect(lambda p, m: self._append(f"[{p:>3}%] {m}"))
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _generate_script(self) -> None:
        if self.script_worker:
            QMessageBox.information(self, "提示", "脚本生成中，请稍候。")
            return
        if self.worker:
            QMessageBox.information(self, "提示", "合成任务进行中，无法生成脚本。")
            return

        desc = self.desc_input.toPlainText().strip()
        if not desc:
            QMessageBox.warning(self, "参数缺失", "请先填写【商品/视频描述】。")
            return

        # 切到脚本页，方便查看输出
        self._switch_to_tab("script")

        # 清理旧状态
        self._approved_script_text = ""
        self._approved_script_json = None
        self.start_btn.setEnabled(False)
        self.approve_script_btn.setEnabled(False)
        self.retry_script_btn.setEnabled(False)
        self.script_status_label.setText("状态：生成中...")
        self.script_status_label.setProperty("variant", "muted")
        self.script_preview.clear()

        role_prompt = self._role_prompt_from_ui()

        self._append("开始执行 Step 1：脚本生成（严格校验）...")

        self.gen_script_btn.setEnabled(False)

        self.script_worker = AIScriptWorker(
            product_desc=desc,
            role_prompt=role_prompt,
            model=(getattr(config, "AI_MODEL", "") or "").strip(),
            max_attempts=3,
            strict_validation=True,
        )
        self.script_worker.log_signal.connect(lambda m: self._append(m))
        self.script_worker.progress_signal.connect(lambda p: self._append(f"[{p:>3}%] Step1 脚本生成..."))
        self.script_worker.data_signal.connect(self._on_script_data)
        self.script_worker.done_signal.connect(self._on_script_done)
        self.script_worker.start()

    def _retry_script(self) -> None:
        # 语义上等同“再生成一次”
        self._generate_script()

    def _approve_script(self) -> None:
        text = (self.script_preview.toPlainText() or "").strip()
        if not text:
            QMessageBox.warning(self, "无可用脚本", "脚本为空，无法通过。")
            return
        # 严格：只允许来自校验通过的结果
        if not (self._approved_script_text or "").strip():
            QMessageBox.warning(self, "未通过校验", "当前脚本未通过严格校验，请点击‘不通过，重新生成’。")
            return

        self.script_status_label.setText("状态：已通过（可开始合成）")
        self.script_status_label.setProperty("variant", "muted")
        self.start_btn.setEnabled(True)
        self._append("✅ Step 1 完成：脚本已通过校验，可以进入 Step 2。")

        # 自动进入合成页
        self._switch_to_tab("compose")

    def _on_script_data(self, data: object) -> None:
        # 可能是规范化脚本 JSON，也可能是失败兜底 raw
        if isinstance(data, dict) and data.get("full_script"):
            script_text = (data.get("full_script") or "").strip()
            self.script_preview.setPlainText(script_text)
            self._approved_script_text = script_text
            self._approved_script_json = data
        elif isinstance(data, dict) and data.get("raw"):
            self.script_preview.setPlainText(str(data.get("raw") or ""))

    def _on_script_done(self, ok: bool, message: str) -> None:
        self.gen_script_btn.setEnabled(True)
        self.script_worker = None
        if ok:
            self.script_status_label.setText("状态：校验通过，等待确认")
            self.approve_script_btn.setEnabled(True)
            self.retry_script_btn.setEnabled(True)
            self._append(message or "脚本生成成功")
        else:
            self.script_status_label.setText(f"状态：未通过（{message or '脚本生成失败'}）")
            self.approve_script_btn.setEnabled(False)
            self.retry_script_btn.setEnabled(True)
            self._approved_script_text = ""
            self._approved_script_json = None
            self._append(message or "脚本生成失败", level="ERROR")

        # 完成后确保停留在脚本页
        self._switch_to_tab("script")

    def _role_prompt_from_ui(self) -> str:
        # 1) 自定义优先
        custom = (self.role_input.toPlainText() if hasattr(self, "role_input") else "").strip()
        if custom:
            return custom

        # 2) 预设角色
        text = (self.role_combo.currentText() or "").strip()
        if not text or text.startswith("默认"):
            return ""
        mapping = {
            "TK带货主播": "你是一名拥有千万粉丝的 TikTok 美区带货博主，也是一位深谙消费者心理学的顶尖文案撰写专家。你的母语是美式英语，你非常熟悉 Gen Z（Z世代）的语言风格、网络梗（Slang）以及 TikTok 的流行趋势。你的任务是根据用户提供的【商品名称】和【核心卖点】，撰写一段时长在 15-30 秒的TikTok 爆款带货口播脚本。你的风格必须符合以下要求：1. **极度口语化**：像朋友打视频电话一样自然，禁止使用任何广播腔、机器人腔或过于正式的营销词汇（如 high quality, durable, convenient 这种词太无聊，换成 literally life-changing, game changer, obsessed）。2. **情绪饱满**：表现出惊讶、兴奋、难以置信或“终于得救了”的情绪。3. **快节奏**：句子要短，信息密度要适中，不拖泥带水。(必须严格遵守)1. **The Hook (0-3s)**: 必须是反直觉的、视觉冲击力强的，或者直接提出一个让人无法拒绝的问题。目的是让用户停止划动。2. **The Pain (3-10s)**: 描述用户生活中的糟糕场景，引起共鸣。3. **The Solution (10-20s)**: 展示产品如何瞬间解决问题，强调爽感。4. **The CTA (20-25s)**: 强势号召购买，制造紧迫感。要求- 输出语言：**English (US)**。- 不需要输出画面指导，只需要输出**口播文案（Spoken Text）**本身。- 严禁使用 Emoji，因为这会影响 TTS（语音合成）的发音。- 全文单词数控制在 60-120 词之间。输入要求Product: [商品名]Features: [卖点描述]输出要求直接输出一段完整的英文脚本，不要包含 Hook:, Body: 等标签，直接给我最终的念白内容。",
            "专业测评博主": "You are a rigorous product reviewer. Be factual, structured, and benefits-driven.",
            "幽默搞笑旁白": "You are a funny TikTok narrator. Be playful, fast-paced, and witty.",
            "情绪共鸣治愈": "You are an empathetic storyteller. Create emotional resonance and comforting tone.",
        }
        return mapping.get(text, "")

    def _on_done(self, output_path: str, error_msg: str) -> None:
        if error_msg:
            self._append(f"任务失败：{error_msg}", level="ERROR")
        else:
            self._append(f"任务完成：{output_path}")
            try:
                QDesktopServices.openUrl(Path(output_path).resolve().as_uri())
            except Exception:
                pass

        self.start_btn.setEnabled(True)
        self.worker = None

    def shutdown(self) -> None:
        try:
            if self.script_worker:
                self.script_worker.requestInterruption()
                self.script_worker.quit()
                if not self.script_worker.wait(800):
                    self.script_worker.terminate()
            if self.worker:
                self.worker.requestInterruption()
                self.worker.quit()
                if not self.worker.wait(800):
                    self.worker.terminate()
        except Exception:
            pass

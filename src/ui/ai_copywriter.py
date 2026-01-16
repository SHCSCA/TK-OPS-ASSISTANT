"""AI 爆款文案/标签助手 UI 面板"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QComboBox,
    QFrame,
    QFileDialog,
    QMessageBox,
    QApplication,
)

from PyQt5.QtCore import QDateTime, QTimer
from pathlib import Path

from workers.ai_worker import AICopyWorker
from utils.ui_log import append_log, install_log_context_menu
import config


class AICopywriterPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: AICopyWorker | None = None
        self._last_result: dict | None = None
        self._last_export_text: str = ""

        # 自定义角色提示词：做一个轻量防抖，避免频繁写 .env
        self._role_save_timer = QTimer(self)
        self._role_save_timer.setSingleShot(True)
        self._role_save_timer.setInterval(800)
        self._role_save_timer.timeout.connect(self._persist_custom_role_prompt)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("AI 爆款文案助手")
        title.setObjectName("h1")
        layout.addWidget(title)

        desc = QLabel(
            "用途：根据中文卖点描述，生成 TikTok 风格标题、标签与拍摄/剪辑建议。\n"
            "说明：本功能使用【系统设置】里配置的 AI 模型与 AI Key。"
        )
        desc.setProperty("variant", "muted")
        layout.addWidget(desc)

        input_frame = QFrame()
        input_frame.setProperty("class", "config-frame")
        input_layout = QVBoxLayout(input_frame)

        input_layout.addWidget(QLabel("商品信息描述："))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(
            "产品: 迷你风扇\n卖点: 静音、续航长、夹子可夹在床边，适合宿舍使用"
        )
        self.desc_input.setMaximumHeight(140)
        input_layout.addWidget(self.desc_input)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("语气："))
        self.tone_combo = QComboBox()
        self.tone_combo.addItems([
            "中性客观（无情绪倾向）",
            "幽默种草",
            "TK带货主播",
            "悬疑反转",
            "专业测评",
            "情绪共鸣",
        ])
        options_row.addWidget(self.tone_combo)

        options_row.addWidget(QLabel("AI 角色："))
        self.role_combo = QComboBox()
        self.role_combo.addItems([
            "默认（使用系统设置）",
            "TK带货主播",
            "专业测评博主",
            "幽默搞笑旁白",
            "情绪共鸣治愈",
        ])
        options_row.addWidget(self.role_combo)

        options_row.addWidget(QLabel("使用模型："))
        use_model = (
            (getattr(config, "AI_MODEL", "") or "").strip()
            or "（未配置）"
        )
        self.model_label = QLabel(use_model)
        self.model_label.setProperty("variant", "muted")
        options_row.addWidget(self.model_label)
        options_row.addStretch(1)
        input_layout.addLayout(options_row)

        input_layout.addWidget(QLabel("自定义角色提示词（可选，留空则使用预设/系统设置）："))
        self.role_input = QTextEdit()
        self.role_input.setPlaceholderText(
            "例：你是一名强转化的 TikTok 带货主播，输出要更直接、更有号召力、更偏促销。"
        )
        self.role_input.setMaximumHeight(70)
        # 回填上次保存的自定义角色提示词
        try:
            self.role_input.setText((getattr(config, "AI_COPYWRITER_ROLE_PROMPT", "") or ""))
        except Exception:
            pass
        # 自动持久化：输入变化后延迟写入 .env
        try:
            self.role_input.textChanged.connect(self._schedule_persist_custom_role_prompt)
        except Exception:
            pass
        input_layout.addWidget(self.role_input)

        actions_row = QHBoxLayout()
        self.gen_btn = QPushButton("生成文案")
        self.gen_btn.clicked.connect(self.generate)
        actions_row.addWidget(self.gen_btn)

        self.copy_btn = QPushButton("一键复制")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        actions_row.addWidget(self.copy_btn)

        self.download_btn = QPushButton("一键下载TXT")
        self.download_btn.clicked.connect(self.export_txt)
        actions_row.addWidget(self.download_btn)

        self.save_as_btn = QPushButton("另存为...")
        self.save_as_btn.clicked.connect(self.export_txt_as)
        actions_row.addWidget(self.save_as_btn)

        actions_row.addStretch(1)
        input_layout.addLayout(actions_row)

        layout.addWidget(input_frame)

        layout.addWidget(QLabel("输出："))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("LogView")
        install_log_context_menu(self.output)
        layout.addWidget(self.output)

        layout.addStretch()
        self.setLayout(layout)

    def _append(self, text: str):
        append_log(self.output, text, level="INFO")

    def _schedule_persist_custom_role_prompt(self) -> None:
        try:
            self._role_save_timer.start()
        except Exception:
            pass

    def _persist_custom_role_prompt(self) -> None:
        try:
            text = (self.role_input.toPlainText() if hasattr(self, "role_input") else "")
            text = (text or "").strip()
            config.set_config("AI_COPYWRITER_ROLE_PROMPT", text, persist=True, hot_reload=False)
        except Exception:
            # 不影响主流程
            pass

    def generate(self):
        if self.worker:
            return

        desc = self.desc_input.toPlainText().strip()
        tone = self.tone_combo.currentText().strip()
        role_prompt = self._role_prompt_from_ui()

        self.output.clear()
        self._append("正在生成，请稍候...")

        # 模型由系统设置中的 AI_MODEL 控制
        self.worker = AICopyWorker(desc_cn=desc, tone=tone, role_prompt=role_prompt)
        self.worker.log_signal.connect(self._append)
        self.worker.error_signal.connect(lambda m: self._append(f"✗ {m}"))
        # 统一结果信号：优先 data_signal，兼容旧 result_signal
        if hasattr(self.worker, "data_signal"):
            self.worker.data_signal.connect(self._on_result)
        else:
            self.worker.result_signal.connect(self._on_result)

        if hasattr(self.worker, "done_signal"):
            self.worker.done_signal.connect(self._on_done)
        self.worker.finished_signal.connect(self._on_finished)

        self.gen_btn.setEnabled(False)
        self.worker.start()

    def _on_result(self, data: dict):
        self._last_result = data
        self._last_export_text = self._build_export_text(data)
        titles = data.get("titles") or []
        hashtags = data.get("hashtags") or []
        notes = data.get("notes") or []

        self._append("\n【标题（Titles）】")
        for i, t in enumerate(titles, 1):
            self._append(f"{i}. {t}")

        self._append("\n【标签（Hashtags）】")
        if hashtags:
            self._append(" ".join(hashtags))

        self._append("\n【拍摄/剪辑建议（Notes）】")
        for i, n in enumerate(notes, 1):
            self._append(f"{i}. {n}")

        self._append("\n提示：可点击【一键复制】或【一键下载TXT】保存。")

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
            "专业测评博主": "你是一名严谨的产品测评博主，输出要更客观、对比清晰、强调参数与使用场景。",
            "幽默搞笑旁白": "你是一名幽默搞笑的旁白编剧，输出要更轻松、有梗、节奏更快。",
            "情绪共鸣治愈": "你是一名擅长情绪共鸣的文案创作者，输出更温柔、更走心、更能引发共鸣。",
        }
        return mapping.get(text, "")

    def _build_export_text(self, data: dict) -> str:
        titles = data.get("titles") or []
        hashtags = data.get("hashtags") or []
        notes = data.get("notes") or []

        lines: list[str] = []
        lines.append("【标题（Titles）】")
        for i, t in enumerate(titles, 1):
            lines.append(f"{i}. {t}")
        lines.append("")
        lines.append("【标签（Hashtags）】")
        if hashtags:
            lines.append(" ".join(hashtags))
        lines.append("")
        lines.append("【拍摄/剪辑建议（Notes）】")
        for i, n in enumerate(notes, 1):
            lines.append(f"{i}. {n}")
        lines.append("")
        return "\n".join(lines).strip() + "\n"

    def copy_to_clipboard(self):
        text = (self._last_export_text or "").strip()
        if not text:
            QMessageBox.information(self, "提示", "还没有可复制的内容，请先生成文案。")
            return
        try:
            QApplication.clipboard().setText(text)
            self._append("✓ 已复制到剪贴板")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", str(e))

    def export_txt(self):
        text = (self._last_export_text or "").strip()
        if not text:
            QMessageBox.information(self, "提示", "还没有可下载的内容，请先生成文案。")
            return

        try:
            base_dir = Path(getattr(config, "OUTPUT_DIR", Path("Output"))) / "AI_Copywriter"
            base_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            base_dir = Path("Output")

        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        file_path = str((base_dir / f"ai_copy_{ts}.txt").resolve())
        try:
            Path(file_path).write_text(text + "\n", encoding="utf-8")
            self._append(f"✓ 已保存：{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存失败：{e}")

    def export_txt_as(self):
        text = (self._last_export_text or "").strip()
        if not text:
            QMessageBox.information(self, "提示", "还没有可下载的内容，请先生成文案。")
            return

        try:
            base_dir = Path(getattr(config, "OUTPUT_DIR", Path("Output"))) / "AI_Copywriter"
            base_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            base_dir = Path("Output")

        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        default_path = str((base_dir / f"ai_copy_{ts}.txt").resolve())

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为 TXT",
            default_path,
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(text + "\n", encoding="utf-8")
            self._append(f"✓ 已保存：{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存失败：{e}")

    def _on_finished(self):
        self.gen_btn.setEnabled(True)
        self.worker = None

    def _on_done(self, ok: bool, message: str):
        if ok:
            return
        append_log(self.output, f"任务失败：{message}", level="ERROR")

    def shutdown(self):
        """窗口关闭时的资源清理。"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass

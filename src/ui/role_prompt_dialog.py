"""角色提示词配置对话框（通用组件）

用途：
- 在各 AI 功能面板中复用，提供统一的“配置角色提示词”弹窗
- 支持多行文本输入与持久化保存
"""
from __future__ import annotations

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QApplication

import config
from utils.styles import apply_global_theme


def open_role_prompt_dialog(parent, title: str, initial_text: str = "", help_text: str = "") -> str | None:
    """打开角色提示词弹窗并返回用户输入内容。

    Args:
        parent: 父级窗口
        title: 弹窗标题
        initial_text: 初始文本
        help_text: 可选提示说明

    Returns:
        str | None: 用户点击保存时返回文本；取消则返回 None。
    """
    # 确保弹窗使用全局主题
    try:
        app = QApplication.instance()
        if app:
            apply_global_theme(app, getattr(config, "THEME_MODE", "dark"))
    except Exception:
        pass

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(520)

    layout = QVBoxLayout(dialog)

    if help_text:
        hint = QLabel(help_text)
        hint.setWordWrap(True)
        hint.setProperty("variant", "muted")
        layout.addWidget(hint)

    text_edit = QTextEdit()
    text_edit.setPlaceholderText("请输入角色提示词，例如：你是一名强转化的 TikTok 带货主播...")
    text_edit.setPlainText((initial_text or "").strip())
    text_edit.setMinimumHeight(200)
    layout.addWidget(text_edit)

    btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    btns.button(QDialogButtonBox.Save).setText("保存")
    btns.button(QDialogButtonBox.Cancel).setText("取消")
    btns.accepted.connect(dialog.accept)
    btns.rejected.connect(dialog.reject)
    layout.addWidget(btns)

    if dialog.exec_() == QDialog.Accepted:
        return (text_edit.toPlainText() or "").strip()
    return None

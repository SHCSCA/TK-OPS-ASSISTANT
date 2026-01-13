"""UI 日志辅助工具

目标：
- 统一各面板 QTextEdit 的日志追加/滚动行为
- 提供右键菜单：复制全部、清空、按级别过滤（不新增页面/弹窗）

说明：
- 过滤逻辑在 UI 侧完成，不影响文件日志。
- 颜色仅用于 UI 展示，保持现有主题风格。
"""

from __future__ import annotations

import html
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QMenu, QTextEdit


_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def _normalize_level(level: Optional[str]) -> str:
    if not level:
        return "INFO"
    level = str(level).strip().upper()
    if level in _LEVEL_ORDER:
        return level
    # 兼容用户自定义/中文
    if level in {"WARN", "WARNING"}:
        return "WARNING"
    return "INFO"


def _should_show(widget: QTextEdit, level: str) -> bool:
    try:
        min_level = widget.property("log_min_level")
    except Exception:
        min_level = None
    min_level = _normalize_level(min_level)
    return _LEVEL_ORDER.get(level, 20) >= _LEVEL_ORDER.get(min_level, 20)


def append_log(widget: QTextEdit, message: str, level: Optional[str] = None) -> None:
    """向 QTextEdit 追加日志（带可选级别、颜色、自动滚动、过滤）。"""
    level = _normalize_level(level)
    if not _should_show(widget, level):
        return

    text = str(message or "")

    # 如果调用方已经传了富文本（比如 span），直接追加
    if "<span" in text or "</" in text:
        widget.append(text)
        widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())
        return

    safe = html.escape(text)

    # 简单配色：错误红、警告黄、其余默认
    if level in {"ERROR", "CRITICAL"}:
        safe = f"<span style='color:#ff5252'>[{level}] {safe}</span>"
    elif level == "WARNING":
        safe = f"<span style='color:#f1c40f'>[{level}] {safe}</span>"
    else:
        safe = f"[{level}] {safe}"

    widget.append(safe)
    widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())


def install_log_context_menu(widget: QTextEdit) -> None:
    """为日志窗口安装统一右键菜单（复制全部/清空/级别过滤）。"""

    # 默认显示 INFO 及以上
    try:
        if widget.property("log_min_level") is None:
            widget.setProperty("log_min_level", "INFO")
    except Exception:
        widget.setProperty("log_min_level", "INFO")

    widget.setContextMenuPolicy(Qt.CustomContextMenu)

    def _set_min_level(level: str) -> None:
        widget.setProperty("log_min_level", _normalize_level(level))

    def _copy_all() -> None:
        widget.selectAll()
        widget.copy()
        # 取消选择，避免影响编辑体验
        cursor = widget.textCursor()
        cursor.clearSelection()
        widget.setTextCursor(cursor)

    def _clear() -> None:
        widget.clear()

    def _show_menu(pos):
        menu = widget.createStandardContextMenu()

        menu.addSeparator()

        copy_all_action = QAction("复制全部", menu)
        copy_all_action.triggered.connect(_copy_all)
        menu.addAction(copy_all_action)

        clear_action = QAction("清空", menu)
        clear_action.triggered.connect(_clear)
        menu.addAction(clear_action)

        filter_menu = QMenu("过滤级别", menu)
        for label, lvl in [
            ("全部", "DEBUG"),
            ("INFO 及以上", "INFO"),
            ("WARNING 及以上", "WARNING"),
            ("仅 ERROR", "ERROR"),
        ]:
            act = QAction(label, filter_menu)
            act.triggered.connect(lambda _=False, l=lvl: _set_min_level(l))
            filter_menu.addAction(act)
        menu.addMenu(filter_menu)

        menu.exec_(widget.mapToGlobal(pos))

    widget.customContextMenuRequested.connect(_show_menu)

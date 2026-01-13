"""SpinBox arrows proxy style.

目的：在强 QSS 美化下，QSpinBox/QDoubleSpinBox 的上下箭头经常被样式表“吃掉”或渲染成方块。
这里使用 QProxyStyle 直接绘制三角箭头，保证在 Fusion + QSS 场景稳定显示。
"""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath
from PyQt5.QtWidgets import QProxyStyle, QStyle


class SpinBoxArrowProxyStyle(QProxyStyle):
    """为 SpinBox 的上下箭头提供稳定绘制。"""

    def _arrow_color(self, option) -> QColor:
        try:
            base = option.palette.color(option.palette.ButtonText)
        except Exception:
            base = QColor("#bdc3c7")
        color = QColor(base)
        color.setAlpha(235)
        return color

    def _draw_triangle(self, painter: QPainter, rect: QRect, up: bool, color: QColor) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)

        cx = rect.center().x()
        cy = rect.center().y()

        w = max(6, min(10, rect.width() - 6))
        h = max(5, min(8, rect.height() - 6))

        if up:
            p1 = QPoint(cx - w // 2, cy + h // 2)
            p2 = QPoint(cx + w // 2, cy + h // 2)
            p3 = QPoint(cx, cy - h // 2)
        else:
            p1 = QPoint(cx - w // 2, cy - h // 2)
            p2 = QPoint(cx + w // 2, cy - h // 2)
            p3 = QPoint(cx, cy + h // 2)

        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.closeSubpath()
        painter.drawPath(path)
        painter.restore()

    def drawComplexControl(self, control, option, painter: QPainter, widget=None):  # type: ignore[override]
        # 先让原本样式/QSS 画完整个 SpinBox（包括按钮背景）
        super().drawComplexControl(control, option, painter, widget)

        if control != QStyle.CC_SpinBox:
            return

        try:
            up_rect = self.subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxUp, widget)
            down_rect = self.subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxDown, widget)
        except Exception:
            return

        color = self._arrow_color(option)
        if up_rect.isValid() and up_rect.width() > 4 and up_rect.height() > 4:
            self._draw_triangle(painter, up_rect, up=True, color=color)
        if down_rect.isValid() and down_rect.width() > 4 and down_rect.height() > 4:
            self._draw_triangle(painter, down_rect, up=False, color=color)
        return

    def drawPrimitive(self, element, option, painter: QPainter, widget=None):  # type: ignore[override]
        # 兼容：部分样式会单独调用 primitive；这里也兜底画一下
        if element in (QStyle.PE_IndicatorSpinUp, QStyle.PE_IndicatorSpinDown):
            rect: QRect = option.rect
            color = self._arrow_color(option)
            self._draw_triangle(painter, rect, up=(element == QStyle.PE_IndicatorSpinUp), color=color)
            return

        super().drawPrimitive(element, option, painter, widget)

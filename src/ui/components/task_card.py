"""
Task Card Component (P0 Requirement)
Implements 'View Layer: Card-style list' and 'UX: Circular progress bar / Skeleton Screen'.
"""
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QProgressBar, QFrame, QPushButton, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen

# Design Constants
COLOR_BG = "#0F0F0F"
COLOR_PRIMARY = "#FE2C55"
COLOR_ACCENT = "#25F4EE"
COLOR_CARD_BG = "#1A1A1A"

class SkeletonLoader(QWidget):
    """Skeleton Screen Placeholder"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)
        self._offset = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Base
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)
        
        # Shimmer
        self._offset = (self._offset + 10) % (self.width() * 2)
        gradient_pos = self._offset - self.width()
        
        # Simple implementation: just a moving lighter bar
        painter.setBrush(QColor(50, 50, 50))
        painter.drawRoundedRect(gradient_pos, 10, 100, 60, 4, 4)

class TaskCard(QFrame):
    """
    Represent a single background task.
    """
    def __init__(self, task_id: str, title: str):
        super().__init__()
        self.task_id = task_id
        
        # Style
        self.setObjectName("taskCard")
        self.setStyleSheet(f"""
            #taskCard {{
                background-color: {COLOR_CARD_BG};
                border-radius: 8px;
                border: 1px solid #333;
            }}
            #taskCard:hover {{
                border: 1px solid {COLOR_PRIMARY};
            }}
            QLabel {{ color: white; }}
        """)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Layout
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        
        # Icon / Status
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet(f"background-color: {COLOR_ACCENT}; border-radius: 6px;")
        self._layout.addWidget(self.status_indicator)
        
        # Info
        info_layout = QVBoxLayout()
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.sub_lbl = QLabel("Waiting...")
        self.sub_lbl.setStyleSheet("color: #888; font-size: 12px;")
        
        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(self.sub_lbl)
        self._layout.addLayout(info_layout)
        
        self._layout.addStretch()
        
        # Progress (Circular or Linear - Linear is easier for MVP)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(100)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #333;
                border: none;
                border-radius: 4px;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_PRIMARY};
                border-radius: 4px;
            }}
        """)
        self._layout.addWidget(self.progress)
        
        # Micro-interaction: Hover Zoom
        # Note: In Qt Widgets, transform logic is complex. 
        # We simulate zoom by shadow or slight scale if using GraphicsView.
        # But for QFrame, we'll stick to Border change on hover (implemented in CSS).

    def update_status(self, status: str, progress: int = 0):
        self.sub_lbl.setText(f"Status: {status}")
        self.progress.setValue(progress)
        
        if status == "success":
            self.status_indicator.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
        elif status == "running":
            self.status_indicator.setStyleSheet(f"background-color: {COLOR_PRIMARY}; border-radius: 6px;")
        elif status == "failed":
            self.status_indicator.setStyleSheet("background-color: #F44336; border-radius: 6px;")

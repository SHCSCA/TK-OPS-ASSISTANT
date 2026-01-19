"""TK-Ops-Pro 全局样式（暗色/浅色）

约定：
- 只在 QApplication 上设置一次全局样式表
- 页面尽量不要再写大段 setStyleSheet（避免白底白字/割裂）
- 需要局部差异时：优先使用 objectName 或动态属性
"""


def get_global_stylesheet(theme_mode: str = "dark") -> str:
    """返回全局 QSS。

    Args:
        theme_mode: "dark" | "light"（其他值默认 dark）
    """
    mode = (theme_mode or "").strip().lower()
    if mode in ("light", "浅色", "浅色系"):
        return GLOBAL_STYLESHEET_LIGHT
    return GLOBAL_STYLESHEET_DARK


# 兼容旧代码：保留 GLOBAL_STYLESHEET（默认为暗色）
GLOBAL_STYLESHEET_DARK = """
/* =======================================================
   全局基础设置 (Dark Mode)
   ======================================================= */
QMainWindow, QWidget {
    background-color: #2b2b2b;
    font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
    font-size: 14px;
    color: #ecf0f1;
}

/* =======================================================
   页面容器/布局 (Layout Containers)
   ======================================================= */
QStackedWidget#ContentStack {
    background-color: #2b2b2b;
}

QFrame#LeftPanel {
    background-color: #1e1e1e;
}

QFrame#TitleBox {
    background-color: #232323;
    border-bottom: 1px solid #333333;
}

/* =======================================================
   侧边栏导航 (Sidebar)
   说明：仅作用于主窗口导航，避免污染页面内的 QListWidget。
   ======================================================= */
QListWidget#NavList {
    background-color: #1e1e1e;
    border: none;
    outline: none;
    min-width: 220px;
    padding-top: 20px;
}
QListWidget#NavList::item {
    height: 55px;
    color: #bdc3c7;
    padding-left: 25px;
    border-left: 5px solid transparent;
    margin-bottom: 5px;
}
QListWidget#NavList::item:selected {
    background-color: #333333;
    color: #00e676; /* Tech Green Accent */
    border-left: 5px solid #00e676;
    font-weight: bold;
}
QListWidget#NavList::item:hover {
    background-color: #2c2c2c;
    color: white;
}

/* 内容区列表（CRM/空投文件列表等） */
QListWidget#ContentList {
    background-color: #333333;
    border: 1px solid #444444;
    border-radius: 10px;
    outline: none;
}
QListWidget#ContentList::item {
    padding: 10px 12px;
    border-bottom: 1px solid #3d3d3d;
}
QListWidget#ContentList::item:selected {
    background-color: #2c2c2c;
}

/* =======================================================
   按钮样式 (Buttons)
   ======================================================= */
QPushButton {
    background-color: #34495e; /* Dark Blue-Grey */
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: bold;
    min-width: 90px;
}

/* 统一变体（推荐用 property variant=primary|danger） */
QPushButton[variant="primary"] {
    background-color: #00e676;
    color: #1e1e1e;
}
QPushButton[variant="primary"]:hover {
    background-color: #69f0ae;
}
QPushButton[variant="danger"] {
    background-color: #e74c3c;
    color: white;
}
QPushButton[variant="danger"]:hover {
    background-color: #ff5252;
}
QPushButton:hover {
    background-color: #00e676; /* Tech Green Hover */
    color: #1e1e1e; /* Black text on Green */
}
QPushButton:pressed {
    background-color: #00c853;
    padding-top: 12px; /* Press effect */
    padding-bottom: 8px;
}
QPushButton:disabled {
    background-color: #424242;
    color: #757575;
}

/* 特殊按钮：主要操作 (Primary Action) */
QPushButton#primary_btn {
    background-color: #00e676;
    color: #1e1e1e;
}
QPushButton#primary_btn:hover {
    background-color: #69f0ae;
}

/* =======================================================
   输入控件 (Inputs)
   ======================================================= */
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #383838;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px;
    color: white;
    selection-background-color: #00e676;
    selection-color: black;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #00e676;
    background-color: #424242;
}

/* 修复暗色模式微调框上下箭头不可见 */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: transparent;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QTextEdit {
    font-family: "Consolas", "Courier New", monospace;
}

/* =======================================================
   标签页 (Tabs)
   ======================================================= */
QTabWidget::pane {
    border: 1px solid #444444;
    border-radius: 10px;
    background-color: #2b2b2b;
    top: -1px;
}
QTabBar::tab {
    background-color: #1e1e1e;
    color: #bdc3c7;
    padding: 10px 14px;
    border: 1px solid #333333;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 6px;
    min-width: 110px;
}
QTabBar::tab:selected {
    background-color: #333333;
    color: #00e676;
    border-color: #00e676;
    font-weight: bold;
}
QTabBar::tab:hover {
    color: #ffffff;
    background-color: #2c2c2c;
}

/* 图文成片预览区 */
QVideoWidget#PhotoPreview {
    background-color: #2b2b2b;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
}

/* 常用日志窗口（统一给 QTextEdit 用） */
QTextEdit#LogView {
    background-color: #1e1e1e;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 10px;
}

/* 素材工厂：拖拽区域 */
QFrame#DropZone {
    border: 2px dashed #666666;
    border-radius: 8px;
    background-color: #333333;
}
QFrame#DropZone QLabel {
    color: #bdc3c7;
}

/* =======================================================
   表格 (Tables)
   ======================================================= */
QTableWidget {
    background-color: #333333;
    alternate-background-color: #2b2b2b;
    border: 1px solid #444444;
    gridline-color: #444444;
    color: #ecf0f1;
    selection-background-color: #00e676;
    selection-color: #1e1e1e;
}
QHeaderView::section {
    background-color: #1e1e1e;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #00e676;
    font-weight: bold;
    color: #00e676;
}
QTableWidget::item {
    padding: 5px;
}

QHeaderView {
    background-color: #1e1e1e;
}

/* =======================================================
   容器与框架 (Frames)
   ======================================================= */
QFrame {
    border: none;
}
/* 卡片式容器：用动态属性 class="config-frame" 标记 */
QFrame[class="config-frame"] {
    background-color: #333333;
    border: 1px solid #444444;
    border-radius: 10px;
    margin-bottom: 16px;
}
/* 标题文字强调 */
QLabel {
    color: #ecf0f1;
}
QLabel#h1 {
    font-size: 24px;
    font-weight: bold;
    color: #00e676;
    margin-bottom: 10px;
}
QLabel#h2 {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
    margin-bottom: 5px;
}

/* 次要说明文字（灰色） */
QLabel[variant="muted"] {
    color: #bdc3c7;
}

/* 状态标签：通过动态属性控制颜色 */
QLabel[status="safe"] {
    color: #00e676;
    font-weight: bold;
}
QLabel[status="unsafe"] {
    color: #e74c3c;
    font-weight: bold;
}

/* 通用状态（ok|warn|bad） */
QLabel[status="ok"] { color: #00e676; font-weight: bold; }
QLabel[status="warn"] { color: #f1c40f; font-weight: bold; }
QLabel[status="bad"] { color: #e74c3c; font-weight: bold; }

/* 状态栏 */
QStatusBar {
    background-color: #1e1e1e;
    color: #bdc3c7;
    border-top: 1px solid #333333;
}

/* =======================================================
   其他控件 (Misc)
   ======================================================= */
/* 滚动条 */
QScrollBar:vertical {
    border: none;
    background: #2b2b2b;
    width: 12px;
}

QScrollBar:horizontal {
    border: none;
    background: #2b2b2b;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #00e676;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #00e676;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* 进度条 */
QProgressBar {
    border: none;
    background-color: #424242;
    border-radius: 6px;
    text-align: center;
    color: white;
    font-weight: bold;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #00e676; /* Tech Green */
    border-radius: 6px;
}

/* 复选框 */
QCheckBox {
    spacing: 8px;
    color: #ecf0f1;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid #777;
    background-color: #383838;
}
QCheckBox::indicator:checked {
    background-color: #00e676;
    border: 1px solid #00e676;
    image: url(none); /* 可以加个对勾图标，这里暂且用颜色区分 */
}
QCheckBox::indicator:unchecked:hover {
    border: 1px solid #00e676;
}

QCheckBox[variant="bold"] {
    font-weight: bold;
}

/* 链接 */
QLabel[style="link"] {
    color: #00e676;
    text-decoration: underline;
}
"""


GLOBAL_STYLESHEET_LIGHT = """
/* =======================================================
   全局基础设置 (Light Mode)
   ======================================================= */
QMainWindow, QWidget {
    background-color: #f6f7fb;
    font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
    font-size: 14px;
    color: #1f2d3d;
}

/* =======================================================
   页面容器/布局 (Layout Containers)
   ======================================================= */
QStackedWidget#ContentStack {
    background-color: #f6f7fb;
}

QFrame#LeftPanel {
    background-color: #ffffff;
    border-right: 1px solid #d9deea;
}

QFrame#TitleBox {
    background-color: #ffffff;
    border-bottom: 1px solid #d9deea;
}

/* =======================================================
   侧边栏导航 (Sidebar)
   说明：仅作用于主窗口导航，避免污染页面内的 QListWidget。
   ======================================================= */
QListWidget#NavList {
    background-color: #ffffff;
    border: none;
    outline: none;
    min-width: 220px;
    padding-top: 20px;
}
QListWidget#NavList::item {
    height: 55px;
    color: #5f6b7a;
    padding-left: 25px;
    border-left: 5px solid transparent;
    margin-bottom: 5px;
}
QListWidget#NavList::item:selected {
    background-color: #eef2f7;
    color: #00b85c;
    border-left: 5px solid #00b85c;
    font-weight: bold;
}
QListWidget#NavList::item:hover {
    background-color: #f0f2f7;
    color: #1f2d3d;
}

/* 内容区列表（CRM/空投文件列表等） */
QListWidget#ContentList {
    background-color: #ffffff;
    border: 1px solid #d9deea;
    border-radius: 10px;
    outline: none;
}
QListWidget#ContentList::item {
    padding: 10px 12px;
    border-bottom: 1px solid #eef2f7;
}
QListWidget#ContentList::item:selected {
    background-color: #eef2f7;
}

/* =======================================================
   按钮样式 (Buttons)
   ======================================================= */
QPushButton {
    background-color: #f0f2f7;
    color: #1f2d3d;
    border: 1px solid #d9deea;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: bold;
    min-width: 90px;
}
QPushButton:hover {
    background-color: #00b85c;
    color: #ffffff;
    border-color: #00b85c;
}
QPushButton:pressed {
    background-color: #00a651;
    border-color: #00a651;
}
QPushButton:disabled {
    background-color: #f0f2f7;
    color: #9aa4b2;
    border-color: #d9deea;
}

QPushButton#primary_btn {
    background-color: #00b85c;
    color: #ffffff;
    border: none;
}
QPushButton#primary_btn:hover {
    background-color: #22c55e;
}

QPushButton[variant="primary"] {
    background-color: #00b85c;
    color: #ffffff;
    border: none;
}
QPushButton[variant="primary"]:hover {
    background-color: #22c55e;
}
QPushButton[variant="danger"] {
    background-color: #e74c3c;
    color: #ffffff;
    border: none;
}
QPushButton[variant="danger"]:hover {
    background-color: #ff5252;
}

/* =======================================================
   输入控件 (Inputs)
   ======================================================= */
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d9deea;
    border-radius: 8px;
    padding: 8px;
    color: #1f2d3d;
    selection-background-color: #00b85c;
    selection-color: #ffffff;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #00b85c;
    background-color: #ffffff;
}

/* 修复亮色模式微调框上下箭头不可见 */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: transparent;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QTextEdit {
    font-family: "Consolas", "Courier New", monospace;
}

/* 常用日志窗口（统一给 QTextEdit 用） */
QTextEdit#LogView {
    background-color: #111827;
    color: #34d399;
    border: 1px solid #d9deea;
    border-radius: 8px;
    padding: 10px;
}

/* 素材工厂：拖拽区域 */
QFrame#DropZone {
    border: 2px dashed #c3cad9;
    border-radius: 10px;
    background-color: #ffffff;
}
QFrame#DropZone QLabel {
    color: #5f6b7a;
}

/* =======================================================
   表格 (Tables)
   ======================================================= */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f6f7fb;
    border: 1px solid #d9deea;
    gridline-color: #d9deea;
    color: #1f2d3d;
    selection-background-color: #00b85c;
    selection-color: #ffffff;
}

/* =======================================================
   标签页 (Tabs)
   ======================================================= */
QTabWidget::pane {
    border: 1px solid #d9deea;
    border-radius: 10px;
    background-color: #f6f7fb;
    top: -1px;
}
QTabBar::tab {
    background-color: #ffffff;
    color: #5f6b7a;
    padding: 10px 14px;
    border: 1px solid #d9deea;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 6px;
    min-width: 110px;
}
QTabBar::tab:selected {
    background-color: #eef2f7;
    color: #00b85c;
    border-color: #00b85c;
    font-weight: bold;
}
QTabBar::tab:hover {
    background-color: #f0f2f7;
    color: #1f2d3d;
}

/* 图文成片预览区（浅色） */
QVideoWidget#PhotoPreview {
    background-color: #f6f7fb;
    border: 1px solid #d9deea;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #f0f2f7;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #00b85c;
    font-weight: bold;
    color: #00b85c;
}
QTableWidget::item {
    padding: 5px;
}

QHeaderView {
    background-color: #f0f2f7;
}

/* =======================================================
   容器与框架 (Frames)
   ======================================================= */
QFrame {
    border: none;
}
QFrame[class="config-frame"] {
    background-color: #ffffff;
    border: 1px solid #d9deea;
    border-radius: 12px;
    margin-bottom: 16px;
}
QLabel {
    color: #1f2d3d;
}
QLabel#h1 {
    font-size: 24px;
    font-weight: bold;
    color: #00b85c;
    margin-bottom: 10px;
}
QLabel#h2 {
    font-size: 18px;
    font-weight: bold;
    color: #1f2d3d;
    margin-bottom: 5px;
}
QLabel[variant="muted"] {
    color: #5f6b7a;
}
QLabel[status="safe"] {
    color: #00b85c;
    font-weight: bold;
}
QLabel[status="unsafe"] {
    color: #d92d20;
    font-weight: bold;
}
QLabel[status="ok"] {
    color: #00b85c;
    font-weight: bold;
}
QLabel[status="warn"] {
    color: #f1c40f;
    font-weight: bold;
}
QLabel[status="bad"] {
    color: #e74c3c;
    font-weight: bold;
}

QStatusBar {
    background-color: #ffffff;
    color: #5f6b7a;
    border-top: 1px solid #d9deea;
}

/* =======================================================
   其他控件 (Misc)
   ======================================================= */
QScrollBar:vertical {
    border: none;
    background: #f6f7fb;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #9aa4b2;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #00b85c;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #f6f7fb;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background: #9aa4b2;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #00b85c;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

QProgressBar {
    border: 1px solid #d9deea;
    background-color: #ffffff;
    border-radius: 8px;
    text-align: center;
    color: #1f2d3d;
    font-weight: bold;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #00b85c;
    border-radius: 8px;
}

QCheckBox {
    spacing: 8px;
    color: #1f2d3d;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #d9deea;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #00b85c;
    border: 1px solid #00b85c;
    image: url(none);
}
QCheckBox::indicator:unchecked:hover {
    border: 1px solid #00b85c;
}

QLabel[style="link"] {
    color: #00b85c;
    text-decoration: underline;
}
"""


GLOBAL_STYLESHEET = GLOBAL_STYLESHEET_DARK

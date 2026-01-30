"""
账户与指纹管理界面 (Task 2 Implementation)
负责展示、编辑、创建多账号指纹配置，并提供直接启动浏览器的入口。
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QLabel, QLineEdit, QFormLayout, QPushButton, QGroupBox, 
    QMessageBox, QComboBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal

import config
from browser.profile import BrowserProfile
from services.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)

class AccountManagerWidget(QWidget):
    """账户管理主组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profiles: List[BrowserProfile] = []
        self.current_profile: BrowserProfile = None
        self.data_file = Path(getattr(config, "ASSET_LIBRARY_DIR", "AssetLibrary")) / "profiles.json"
        
        self.init_ui()
        self.load_profiles()

    def init_ui(self):
        """初始化 UI"""
        main_layout = QHBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- 左侧：账户列表 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_profile_selected)
        left_layout.addWidget(QLabel("已保存的账户 (Accounts)"))
        left_layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("新建账户")
        self.btn_add.clicked.connect(self.create_new_profile)
        self.btn_del = QPushButton("删除账户")
        self.btn_del.clicked.connect(self.delete_current_profile)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        left_layout.addLayout(btn_layout)
        
        splitter.addWidget(left_panel)
        
        # --- 右侧：详细配置 ---
        right_panel = QWidget()
        self.right_panel = right_panel
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # 基本信息组
        info_group = QGroupBox("基本信息 (Basic Info)")
        info_layout = QFormLayout()
        
        self.input_name = QLineEdit()
        self.input_id = QLineEdit()
        self.input_id.setReadOnly(True)
        self.input_id.setPlaceholderText("系统自动生成")
        
        info_layout.addRow("账户名称:", self.input_name)
        info_layout.addRow("ID:", self.input_id)
        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)
        
        # 指纹配置组
        fp_group = QGroupBox("指纹参数 (Fingerprint)")
        fp_layout = QFormLayout()
        
        self.input_ua = QLineEdit()
        self.input_ua.setPlaceholderText("User-Agent String")
        
        # 分辨率使用 ComboBox + 自定义
        self.combo_res = QComboBox()
        self.combo_res.addItems(["1920x1080", "1366x768", "1440x900", "1280x720", "Custom"])
        self.combo_res.currentTextChanged.connect(self.on_res_changed)
        
        self.input_width = QLineEdit()
        self.input_width.setPlaceholderText("Width")
        self.input_height = QLineEdit()
        self.input_height.setPlaceholderText("Height")
        res_layout = QHBoxLayout()
        res_layout.addWidget(self.combo_res)
        res_layout.addWidget(QLabel("W:"))
        res_layout.addWidget(self.input_width)
        res_layout.addWidget(QLabel("H:"))
        res_layout.addWidget(self.input_height)
        
        fp_layout.addRow("User-Agent:", self.input_ua)
        fp_layout.addRow("分辨率:", res_layout)
        fp_layout.addRow("时区 (Timezone):", QLineEdit("Asia/Shanghai")) # 暂未绑定变量
        fp_group.setLayout(fp_layout)
        right_layout.addWidget(fp_group)
        
        # 操作栏
        action_layout = QHBoxLayout()
        self.btn_save = QPushButton("保存配置 (Save)")
        self.btn_save.clicked.connect(self.save_current_edit)
        self.btn_launch = QPushButton("🚀 启动浏览器 (Launch)")
        self.btn_launch.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_launch.clicked.connect(self.launch_browser)
        
        action_layout.addStretch()
        action_layout.addWidget(self.btn_save)
        action_layout.addWidget(self.btn_launch)
        right_layout.addLayout(action_layout)
        
        right_layout.addStretch()
        splitter.addWidget(right_panel)
        
        # 初始状态
        splitter.setSizes([200, 600])
        self.right_panel.setEnabled(False)

    def load_profiles(self):
        """从文件加载"""
        self.list_widget.clear()
        self.profiles = []
        
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        p = BrowserProfile(**item)
                        self.profiles.append(p)
            except Exception as e:
                logger.error(f"加载 Profiles 失败: {e}")
        
        # 刷新列表
        for p in self.profiles:
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p)
            self.list_widget.addItem(item)

    def save_to_disk(self):
        """写入文件"""
        try:
            data = [p.__dict__ for p in self.profiles] # BrowserProfile is dataclass
            # 过滤掉非数据字段如果 exists? dataclass to dict is clean usually.
            # Convert default factory fields if needed
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def create_new_profile(self):
        p = BrowserProfile(name=f"New Account {len(self.profiles)+1}")
        self.profiles.append(p)
        self.save_to_disk()
        self.load_profiles()
        # 选中最后一个
        self.list_widget.setCurrentRow(len(self.profiles)-1)
        self.on_profile_selected(self.list_widget.currentItem())

    def delete_current_profile(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        
        reply = QMessageBox.question(self, "确认", "确定要删除此账户配置吗？\n(Cookie 数据不会自动删除)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.profiles.pop(row)
            self.save_to_disk()
            self.load_profiles()
            self.right_panel.setEnabled(False)
            self.current_profile = None

    def on_profile_selected(self, item):
        if not item:
            return
        self.current_profile = item.data(Qt.UserRole)
        self.right_panel.setEnabled(True)
        
        # Fill UI
        self.input_name.setText(self.current_profile.name)
        self.input_id.setText(self.current_profile.id)
        self.input_ua.setText(self.current_profile.user_agent)
        self.input_width.setText(str(self.current_profile.viewport_width))
        self.input_height.setText(str(self.current_profile.viewport_height))
        
        # Match combo ref
        res_str = f"{self.current_profile.viewport_width}x{self.current_profile.viewport_height}"
        idx = self.combo_res.findText(res_str)
        if idx >= 0:
            self.combo_res.setCurrentIndex(idx)
        else:
            self.combo_res.setCurrentIndex(self.combo_res.count()-1) # Custom

    def on_res_changed(self, text):
        if text != "Custom" and "x" in text:
            w, h = text.split("x")
            self.input_width.setText(w)
            self.input_height.setText(h)

    def save_current_edit(self):
        if not self.current_profile:
            return
        
        self.current_profile.name = self.input_name.text()
        self.current_profile.user_agent = self.input_ua.text()
        try:
            self.current_profile.viewport_width = int(self.input_width.text())
            self.current_profile.viewport_height = int(self.input_height.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "分辨率必须是整数")
            return
            
        self.save_to_disk()
        
        # Update list item text
        item = self.list_widget.currentItem()
        item.setText(self.current_profile.name)
        item.setData(Qt.UserRole, self.current_profile)
        
        QMessageBox.information(self, "成功", "配置已保存")

    def launch_browser(self):
        """启动浏览器"""
        if not self.current_profile:
            return
            
        bm = get_browser_manager()
        try:
            ctx = bm.new_context_from_profile(self.current_profile)
            if ctx:
                page = ctx.new_page()
                page.goto("https://www.google.com") # 默认打开个页面
                # 可以在这里添加 Toast 提示
                QMessageBox.information(self, "启动成功", f"账户 [{self.current_profile.name}] 已启动。\n即使关闭此提示，浏览器仍将保持运行，直到手动关闭或停止服务。")
            else:
                QMessageBox.critical(self, "启动失败", "无法创建浏览器上下文，请检查日志。")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))


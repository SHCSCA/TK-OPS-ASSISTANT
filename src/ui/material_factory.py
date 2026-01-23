"""
Material Factory (Video Processing) UI Panel
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QTextEdit, QProgressBar, QFrame, QFileDialog,
    QSpinBox, QDoubleSpinBox, QLineEdit, QListWidget, QAbstractItemView,
    QListWidgetItem, QMenu, QAction, QStyle, QApplication
)
from PyQt5.QtCore import Qt, QUrl, QSettings
from PyQt5.QtGui import (
    QFont, QDragEnterEvent, QDropEvent, QDesktopServices,
    QIcon, QColor, QBrush
)
from workers.video_worker import VideoWorker
from pathlib import Path
from datetime import datetime
import config
from utils.ui_log import append_log, install_log_context_menu
from ui.toast import Toast


class MaterialFactoryPanel(QWidget):
    """Material Factory (Video Processing) Panel"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.cyborg_worker = None
        self.video_files = []
        self.output_dir = None  # User selected output directory
        self.output_dir_custom = False
        self._init_ui()
        self._load_settings() # Load user preferences
        self.setAcceptDrops(True)
    
    def _init_ui(self):
        """Initialize panel UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("素材工厂 - 批量视频处理")
        title.setObjectName("h1")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        layout.addWidget(title)
        
        # Drop zone
        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("DropZone")
        drop_layout = QVBoxLayout()
        drop_label = QLabel("📹 拖入视频文件或点击选择\n支持: MP4, AVI, MOV, MKV")
        drop_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(drop_label)
        self.drop_zone.setLayout(drop_layout)
        layout.addWidget(self.drop_zone)
        
        # File selection button
        button_layout = QHBoxLayout()
        select_button = QPushButton("选择视频文件")
        select_button.clicked.connect(self.select_video_files)
        button_layout.addWidget(select_button)
        
        remove_button = QPushButton("移除选中")
        remove_button.clicked.connect(self.remove_selected_videos)
        button_layout.addWidget(remove_button)

        clear_button = QPushButton("清空列表")
        clear_button.clicked.connect(self.clear_video_list)
        button_layout.addWidget(clear_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Video list (Using QListWidget for better UX)
        self.video_list_widget = QListWidget()
        self.video_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.video_list_widget.setMaximumHeight(120)
        self.video_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        layout.addWidget(QLabel("待处理视频列表（支持多选删除）:"))
        layout.addWidget(self.video_list_widget)
        
        # Processing options
        options_frame = self._create_options_frame()
        # Add class/object name for styling if needed
        options_frame.setProperty("class", "config-frame")
        layout.addWidget(options_frame)

        # [REMOVED] 半人马拼接 (Moved to AI Content Factory)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始处理")
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setEnabled(False)
        control_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        # 打开输出文件夹按钮（默认隐藏，任务完成后显示）
        self.open_output_btn = QPushButton("📂 打开输出文件夹")
        self.open_output_btn.clicked.connect(self._open_output_folder)
        self.open_output_btn.setVisible(False)
        control_layout.addWidget(self.open_output_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # Log window
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setObjectName("LogView")
        install_log_context_menu(self.log_text)
        layout.addWidget(QLabel("处理日志:"))
        layout.addWidget(self.log_text)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _create_options_frame(self) -> QFrame:
        """Create processing options frame"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")

        outer = QHBoxLayout()
        outer.setContentsMargins(15, 15, 15, 15)
        outer.setSpacing(20)

        # 左列：输入项
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        row_parallel = QHBoxLayout()
        row_parallel.addWidget(QLabel("并行任务数:"))
        self.parallel_spinbox = QSpinBox()
        self.parallel_spinbox.setRange(1, 4)
        self.parallel_spinbox.setValue(1)
        row_parallel.addWidget(self.parallel_spinbox)
        row_parallel.addStretch()
        left_col.addLayout(row_parallel)

        speed_hint = QLabel("变速模式：无级随机（每秒 1.10-1.35）")
        speed_hint.setProperty("variant", "muted")
        left_col.addWidget(speed_hint)

        row_trim_head = QHBoxLayout()
        row_trim_head.addWidget(QLabel("去头(秒):"))
        self.trim_head_spinbox = QDoubleSpinBox()
        self.trim_head_spinbox.setValue(0.5)
        self.trim_head_spinbox.setMinimum(0.0)
        self.trim_head_spinbox.setMaximum(10.0)
        self.trim_head_spinbox.setSingleStep(0.1)
        row_trim_head.addWidget(self.trim_head_spinbox)
        row_trim_head.addStretch()
        left_col.addLayout(row_trim_head)

        row_trim_tail = QHBoxLayout()
        row_trim_tail.addWidget(QLabel("去尾(秒):"))
        self.trim_tail_spinbox = QDoubleSpinBox()
        self.trim_tail_spinbox.setValue(0.5)
        self.trim_tail_spinbox.setMinimum(0.0)
        self.trim_tail_spinbox.setMaximum(10.0)
        self.trim_tail_spinbox.setSingleStep(0.1)
        row_trim_tail.addWidget(self.trim_tail_spinbox)
        row_trim_tail.addStretch()
        left_col.addLayout(row_trim_tail)

        # Output Directory Selector
        default_base = getattr(config, "PROCESSED_VIDEOS_DIR", config.OUTPUT_DIR)
        lbl_out = QLabel(f"输出目录 (默认: {default_base}):")
        left_col.addWidget(lbl_out)
        
        row_out = QHBoxLayout()
        self.output_dir_label = QLabel(f"默认：{default_base}")
        self._set_output_dir_label_variant("path-muted")
        self.output_dir_label.setWordWrap(True) # Allow long paths to wrap or just truncate visually
        row_out.addWidget(self.output_dir_label)
        
        btn_out = QPushButton("...")
        btn_out.setFixedWidth(30)
        btn_out.setToolTip("选择保存位置")
        btn_out.clicked.connect(self.select_output_directory)
        row_out.addWidget(btn_out)
        
        left_col.addLayout(row_out)

        left_col.addStretch()

        # 右列：可选项
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        self.flip_checkbox = QCheckBox("镜像翻转")
        self.flip_checkbox.setChecked(True)
        self.flip_checkbox.setProperty("variant", "bold")
        right_col.addWidget(self.flip_checkbox)

        self.deep_remix_checkbox = QCheckBox("深度去重（推荐）")
        self.deep_remix_checkbox.setChecked(getattr(config, "VIDEO_DEEP_REMIX_ENABLED", False))
        self.deep_remix_checkbox.setProperty("variant", "bold")
        right_col.addWidget(self.deep_remix_checkbox)

        self.micro_zoom_checkbox = QCheckBox("微缩放")
        self.micro_zoom_checkbox.setChecked(getattr(config, "VIDEO_REMIX_MICRO_ZOOM", True))
        right_col.addWidget(self.micro_zoom_checkbox)

        self.noise_checkbox = QCheckBox("加噪点")
        self.noise_checkbox.setChecked(getattr(config, "VIDEO_REMIX_ADD_NOISE", False))
        right_col.addWidget(self.noise_checkbox)

        self.strip_metadata_checkbox = QCheckBox("清除元数据")
        self.strip_metadata_checkbox.setChecked(getattr(config, "VIDEO_REMIX_STRIP_METADATA", True))
        right_col.addWidget(self.strip_metadata_checkbox)

        right_col.addStretch()

        outer.addLayout(left_col, 1)
        outer.addLayout(right_col, 1)
        frame.setLayout(outer)
        return frame
    
    def select_output_directory(self):
        """选择输出目录"""
        d = QFileDialog.getExistingDirectory(self, "选择保存处理后视频的文件夹")
        if d:
            self.output_dir = d
            self.output_dir_custom = True
            self.output_dir_label.setText(d)
            self._set_output_dir_label_variant("")
            append_log(self.log_text, f"输出目录已设置为: {d}")
        else:
            # User cancelled, keep previous or default
            pass

    def select_video_files(self):
        """Select video files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if files:
            self._add_files_to_list(files)
    
    def _add_files_to_list(self, files):
        """Add files to list widget (deduplicated)"""
        existing_paths = set()
        for i in range(self.video_list_widget.count()):
            item = self.video_list_widget.item(i)
            existing_paths.add(item.data(Qt.UserRole))

        added_count = 0
        for f in files:
            path_str = str(Path(f).resolve())
            if path_str not in existing_paths:
                item = QListWidgetItem(Path(f).name)
                item.setData(Qt.UserRole, path_str)
                item.setToolTip(path_str)
                self.video_list_widget.addItem(item)
                added_count += 1
        
        self._update_start_button_state()
        if added_count > 0:
            append_log(self.log_text, f"已添加 {added_count} 个视频")

    def remove_selected_videos(self):
        """Remove selected items from list"""
        selected_items = self.video_list_widget.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            self.video_list_widget.takeItem(self.video_list_widget.row(item))
        
        self._update_start_button_state()
        
    def clear_video_list(self):
        """Clear video list"""
        self.video_list_widget.clear()
        self._update_start_button_state()
    
    def _update_start_button_state(self):
        """Update start button state based on list count"""
        self.start_button.setEnabled(self.video_list_widget.count() > 0)
    
    def _show_list_context_menu(self, position):
        """Show context menu for video list"""
        menu = QMenu()
        remove_action = QAction("移除选中", self)
        remove_action.triggered.connect(self.remove_selected_videos)
        remove_action.setEnabled(len(self.video_list_widget.selectedItems()) > 0)
        
        clear_action = QAction("清空列表", self)
        clear_action.triggered.connect(self.clear_video_list)
        
        menu.addAction(remove_action)
        menu.addAction(clear_action)
        menu.exec_(self.video_list_widget.mapToGlobal(position))

    def _open_output_folder(self):
        """打开当前输出文件夹。"""
        if self.output_dir:
            path = str(Path(self.output_dir).resolve())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            Toast.show_info(self.window(), "未找到有效的输出目录")

    def clear_video_list(self):
        """Clear video list"""
        # Obsolete: logic moved to method above but kept wrapper for compatibility if needed
        self.video_list_widget.clear()
        self._update_start_button_state()
    
    def start_processing(self):
        """Start video processing"""
        # Collect video files from UI list (Source of Truth)
        current_video_files = []
        for i in range(self.video_list_widget.count()):
            item = self.video_list_widget.item(i)
            path = item.data(Qt.UserRole)
            if path:
                current_video_files.append(path)

        if not current_video_files:
            append_log(self.log_text, "请先选择视频文件", level="ERROR")
            return
        
        # Save settings before starting
        self._save_settings()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.open_output_btn.setVisible(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        # Get parameters from UI
        trim_head = self.trim_head_spinbox.value()
        trim_tail = self.trim_tail_spinbox.value()
        speed = None
        apply_flip = self.flip_checkbox.isChecked()

        deep_remix_enabled = self.deep_remix_checkbox.isChecked()
        micro_zoom = self.micro_zoom_checkbox.isChecked()
        add_noise = self.noise_checkbox.isChecked()
        strip_metadata = self.strip_metadata_checkbox.isChecked()
        parallel_jobs = int(self.parallel_spinbox.value())
        
        # 未选择输出目录时，使用规范化默认目录（按日期+任务分层）
        if not self.output_dir or not self.output_dir_custom:
            self.output_dir = self._build_default_output_dir()
            self.output_dir_custom = False
            self.output_dir_label.setText(self.output_dir)
            self._set_output_dir_label_variant("")
            append_log(self.log_text, f"输出目录（默认）: {self.output_dir}")

        # Create and start worker
        self.worker = VideoWorker(
            video_files=current_video_files,
            trim_head=trim_head,
            trim_tail=trim_tail,
            speed=speed,
            apply_flip=apply_flip,
            deep_remix_enabled=deep_remix_enabled,
            micro_zoom=micro_zoom,
            add_noise=add_noise,
            strip_metadata=strip_metadata,
            parallel_jobs=parallel_jobs,
            output_dir=self.output_dir, # Pass custom output dir
        )
        self.worker.log_signal.connect(self._on_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.error_signal.connect(self._on_error)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.item_finished_signal.connect(self._on_item_finished)
        self.worker.start()

    def stop_processing(self):
        """Stop processing"""
        if self.worker:
            self.worker.stop()
            self.stop_button.setText("正在停止...")
        self.stop_button.setEnabled(False)
        # Wait for worker to finish before enabling start
    
    def _on_log(self, message: str):
        """Handle log signal with improved color coding"""
        level = "INFO"
        if "❌" in message or "失败" in message or "Error" in message:
            level = "ERROR"
        elif "✅" in message or "完成" in message:
            level = "SUCCESS"
        elif "▶" in message or "开始" in message:
            level = "INFO" 
        append_log(self.log_text, message, level=level)

    def _on_item_finished(self, path: str, success: bool, msg: str):
        """Update list item status when processing finishes"""
        for i in range(self.video_list_widget.count()):
            item = self.video_list_widget.item(i)
            # Compare resolve() paths to ensure match
            try:
                item_path = str(Path(item.data(Qt.UserRole)).resolve())
                target_path = str(Path(path).resolve())
                if item_path == target_path:
                    if success:
                        icon = self.style().standardIcon(QStyle.SP_DialogApplyButton)
                        # More subtle success indication
                        item.setForeground(QBrush(QColor("#2E7D32"))) # Dark Green
                        short_msg = msg[:50] + "..." if len(msg) > 50 else msg
                        item.setToolTip(f"Success: {msg}")
                    else:
                        icon = self.style().standardIcon(QStyle.SP_DialogCancelButton)
                        item.setForeground(QBrush(QColor("#D32F2F"))) # Dark Red
                        item.setToolTip(f"Failed: {msg}")
                    item.setIcon(icon)
                    break
            except Exception:
                continue

    def _on_progress(self, progress: int):
        """Handle progress signal"""
        self.progress_bar.setValue(progress)
    
    def _on_error(self, error_message: str):
        """Handle error signal"""
        append_log(self.log_text, error_message, level="ERROR")
        Toast.show_error(self.window(), "任务执行出错")

    def _on_finished(self):
        """Handle finished signal"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.stop_button.setText("停止处理")
        Toast.show_success(self.window(), "批量处理任务已完成")
        append_log(self.log_text, "处理完成!", level="INFO")
        
        # 显示"打开输出文件夹"按钮
        if self.output_dir and Path(self.output_dir).exists():
            self.open_output_btn.setVisible(True)
            try:
                append_log(self.log_text, f"✓ 输出位置: {self.output_dir}", level="INFO")
            except Exception:
                pass
        
        self.worker = None
        if not self.output_dir_custom:
            default_base = getattr(config, "PROCESSED_VIDEOS_DIR", config.OUTPUT_DIR)
            self.output_dir = None
            self.output_dir_label.setText(f"默认：{default_base}")
            self._set_output_dir_label_variant("path-muted")

    def shutdown(self):
        """窗口关闭时的资源清理。"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass

    def _build_default_output_dir(self) -> str:
        """生成素材工厂默认输出目录（Output/Processed_Videos/日期/任务）。"""
        base_dir = Path(getattr(config, "PROCESSED_VIDEOS_DIR", config.OUTPUT_DIR))
        date_dir = datetime.now().strftime("%Y%m%d")
        task_dir = datetime.now().strftime("MaterialFactory_%Y%m%d_%H%M%S")
        target = base_dir / date_dir / task_dir
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return str(target)

    def _set_output_dir_label_variant(self, variant: str) -> None:
        """统一设置输出目录标签样式（使用全局主题变体）。"""
        try:
            self.output_dir_label.setProperty("variant", variant)
            self.output_dir_label.style().unpolish(self.output_dir_label)
            self.output_dir_label.style().polish(self.output_dir_label)
        except Exception:
            pass
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            event.accept()
            # Visual feedback
            self.drop_zone.setStyleSheet("QFrame#DropZone { border: 2px dashed #2196F3; background-color: rgba(33, 150, 243, 0.1); }")
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        """Handle drag leave"""
        self.drop_zone.setStyleSheet("")
        event.accept()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        self.drop_zone.setStyleSheet("")
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
                files.append(file_path)
        
        if files:
            self._add_files_to_list(files)

    def _load_settings(self):
        """Load UI settings from QSettings."""
        try:
            settings = QSettings(config.APP_NAME if hasattr(config, "APP_NAME") else "TK-Ops-Pro", "MaterialFactory")
            
            # Helper to safely load ints/bools/floats
            def _get(key, default, type_func):
                val = settings.value(key, default)
                try:
                    return type_func(val)
                except:
                    return default
            
            self.parallel_spinbox.setValue(_get("parallel_jobs", 1, int))
            self.trim_head_spinbox.setValue(_get("trim_head", 0.5, float))
            self.trim_tail_spinbox.setValue(_get("trim_tail", 0.5, float))
            self.flip_checkbox.setChecked(_get("apply_flip", True, bool)) # Actually QSettings stores bool as string "true"/"false" often in INI, but PyQt handles registry well
            
            # For booleans in QSettings, sometimes it returns 'true' string.
            def _get_bool(key, default):
                val = settings.value(key, default)
                if isinstance(val, bool): return val
                return str(val).lower() == 'true'

            self.flip_checkbox.setChecked(_get_bool("apply_flip", True))
            self.deep_remix_checkbox.setChecked(_get_bool("deep_remix", getattr(config, "VIDEO_DEEP_REMIX_ENABLED", False)))
            self.micro_zoom_checkbox.setChecked(_get_bool("micro_zoom", True))
            self.noise_checkbox.setChecked(_get_bool("add_noise", False))
            self.strip_metadata_checkbox.setChecked(_get_bool("strip_metadata", True))
            
        except Exception as e:
            # print(f"Error loading settings: {e}")
            pass

    def _save_settings(self):
        """Save UI settings to QSettings."""
        try:
            settings = QSettings(config.APP_NAME if hasattr(config, "APP_NAME") else "TK-Ops-Pro", "MaterialFactory")
            settings.setValue("parallel_jobs", self.parallel_spinbox.value())
            settings.setValue("trim_head", self.trim_head_spinbox.value())
            settings.setValue("trim_tail", self.trim_tail_spinbox.value())
            settings.setValue("apply_flip", self.flip_checkbox.isChecked())
            settings.setValue("deep_remix", self.deep_remix_checkbox.isChecked())
            settings.setValue("micro_zoom", self.micro_zoom_checkbox.isChecked())
            settings.setValue("add_noise", self.noise_checkbox.isChecked())
            settings.setValue("strip_metadata", self.strip_metadata_checkbox.isChecked())
        except Exception:
            pass

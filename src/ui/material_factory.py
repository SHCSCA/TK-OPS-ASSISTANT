"""
Material Factory (Video Processing) UI Panel
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QTextEdit, QProgressBar, QFrame, QFileDialog,
    QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QDragEnterEvent, QDropEvent
from workers.video_worker import VideoWorker
from pathlib import Path
from datetime import datetime
import config
from utils.ui_log import append_log, install_log_context_menu


class MaterialFactoryPanel(QWidget):
    """Material Factory (Video Processing) Panel"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.video_files = []
        self.output_dir = None  # User selected output directory
        self.output_dir_custom = False
        self._init_ui()
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
        
        clear_button = QPushButton("清空列表")
        clear_button.clicked.connect(self.clear_video_list)
        button_layout.addWidget(clear_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Video list
        self.video_list_text = QTextEdit()
        self.video_list_text.setReadOnly(True)
        self.video_list_text.setMaximumHeight(80)
        layout.addWidget(QLabel("待处理视频列表:"))
        layout.addWidget(self.video_list_text)
        
        # Processing options
        options_frame = self._create_options_frame()
        # Add class/object name for styling if needed
        options_frame.setProperty("class", "config-frame")
        layout.addWidget(options_frame)
        
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

        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("变速倍数:"))
        self.speed_spinbox = QDoubleSpinBox()
        self.speed_spinbox.setValue(1.1)
        self.speed_spinbox.setMinimum(0.5)
        self.speed_spinbox.setMaximum(2.0)
        self.speed_spinbox.setSingleStep(0.1)
        row_speed.addWidget(self.speed_spinbox)
        row_speed.addStretch()
        left_col.addLayout(row_speed)

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
        self.output_dir_label.setStyleSheet("color: #888; font-style: italic;")
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
            self.output_dir_label.setStyleSheet("color: white;")
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
            self.video_files.extend(files)
            self._update_video_list()
    
    def clear_video_list(self):
        """Clear video list"""
        self.video_files = []
        self.video_list_text.clear()
        self.start_button.setEnabled(False)
    
    def _update_video_list(self):
        """Update video list display"""
        self.video_list_text.clear()
        for i, file in enumerate(self.video_files, 1):
            self.video_list_text.append(f"{i}. {Path(file).name}")
        
        self.start_button.setEnabled(len(self.video_files) > 0)
    
    def start_processing(self):
        """Start video processing"""
        if not self.video_files:
            append_log(self.log_text, "请先选择视频文件", level="ERROR")
            return
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        # Get parameters from UI
        trim_head = self.trim_head_spinbox.value()
        trim_tail = self.trim_tail_spinbox.value()
        speed = self.speed_spinbox.value()
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
            self.output_dir_label.setStyleSheet("color: white;")
            append_log(self.log_text, f"输出目录（默认）: {self.output_dir}")

        # Create and start worker
        self.worker = VideoWorker(
            video_files=self.video_files,
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
        self.worker.start()
    
    def stop_processing(self):
        """Stop processing"""
        if self.worker:
            self.worker.stop()
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
    
    def _on_log(self, message: str):
        """Handle log signal"""
        append_log(self.log_text, message, level="INFO")
    
    def _on_progress(self, progress: int):
        """Handle progress signal"""
        self.progress_bar.setValue(progress)
    
    def _on_error(self, error_message: str):
        """Handle error signal"""
        append_log(self.log_text, error_message, level="ERROR")
    
    def _on_finished(self):
        """Handle finished signal"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        append_log(self.log_text, "处理完成!", level="INFO")
        self.worker = None
        if not self.output_dir_custom:
            default_base = getattr(config, "PROCESSED_VIDEOS_DIR", config.OUTPUT_DIR)
            self.output_dir = None
            self.output_dir_label.setText(f"默认：{default_base}")
            self.output_dir_label.setStyleSheet("color: #888; font-style: italic;")

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
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
                self.video_files.append(file_path)
        
        self._update_video_list()

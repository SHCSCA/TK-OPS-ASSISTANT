"""
Blue Ocean Detector UI Panel
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, QTextEdit,
    QProgressBar, QFrame, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from workers.blue_ocean_worker import BlueOceanWorker
from utils.excel_export import export_blue_ocean_results
from utils.ui_log import append_log, install_log_context_menu
import config


class BlueOceanPanel(QWidget):
    """Blue Ocean Detection Panel"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.results = []
        self._init_ui()
    
    def _init_ui(self):
        """Initialize panel UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("蓝海监测器")
        title.setObjectName("h1")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        layout.addWidget(title)
        
        # Configuration section
        config_frame = self._create_config_frame()
        layout.addWidget(config_frame)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始监测")
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.export_button = QPushButton("导出 Excel")
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "商品标题", "7日增长%", "评价数", "价格USD", 
            "预估毛利%", "1688搜索", "详情"
        ])
        self.results_table.resizeColumnsToContents()
        layout.addWidget(QLabel("检测结果:"), 0, Qt.AlignTop)
        layout.addWidget(self.results_table, 0, Qt.AlignTop)
        
        # Log window
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setObjectName("LogView")
        install_log_context_menu(self.log_text)
        layout.addWidget(QLabel("运行日志:"), 0, Qt.AlignTop)
        layout.addWidget(self.log_text, 0, Qt.AlignTop)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _create_config_frame(self) -> QFrame:
        """Create configuration frame"""
        frame = QFrame()
        frame.setProperty("class", "config-frame")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        
        # Growth threshold
        row1.addWidget(QLabel("近7日销量阈值:"))
        self.growth_spinbox = QSpinBox()
        self.growth_spinbox.setValue(getattr(config, "GROWTH_RATE_THRESHOLD", 500))
        self.growth_spinbox.setMinimum(0)
        self.growth_spinbox.setMaximum(1000000)
        row1.addWidget(self.growth_spinbox)
        
        # Max reviews
        row1.addWidget(QLabel("最大评价数:"))
        self.review_spinbox = QSpinBox()
        self.review_spinbox.setValue(getattr(config, "MAX_REVIEWS", 50))
        self.review_spinbox.setMinimum(0)
        self.review_spinbox.setMaximum(1000000)
        row1.addWidget(self.review_spinbox)

        # Price range
        row2.addWidget(QLabel("价格范围(USD):"))
        self.price_min_spinbox = QDoubleSpinBox()
        self.price_min_spinbox.setRange(0, 10000)
        self.price_min_spinbox.setValue(float(getattr(config, "PRICE_MIN", 20)))
        row2.addWidget(self.price_min_spinbox)
        row2.addWidget(QLabel(" - "))
        self.price_max_spinbox = QDoubleSpinBox()
        self.price_max_spinbox.setRange(0, 10000)
        self.price_max_spinbox.setValue(float(getattr(config, "PRICE_MAX", 80)))
        row2.addWidget(self.price_max_spinbox)
        
        # Export option
        self.auto_export_checkbox = QCheckBox("自动导出 Excel")
        self.auto_export_checkbox.setChecked(True)
        row2.addWidget(self.auto_export_checkbox)
        
        row1.addStretch()
        row2.addStretch()
        layout.addLayout(row1)
        layout.addLayout(row2)
        frame.setLayout(layout)
        return frame
    
    def start_detection(self):
        """Start blue ocean detection"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.export_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.results_table.setRowCount(0)
        self.results = []

        # 阈值持久化：统一入口写回 .env + 热更新内存 config（避免“改了不生效/需重启”）
        try:
            growth_threshold = int(self.growth_spinbox.value())
            max_reviews = int(self.review_spinbox.value())
            price_min = float(self.price_min_spinbox.value())
            price_max = float(self.price_max_spinbox.value())

            config.set_config("GROWTH_RATE_THRESHOLD", str(growth_threshold), persist=True, hot_reload=False)
            config.set_config("MAX_REVIEWS", str(max_reviews), persist=True, hot_reload=False)
            config.set_config("PRICE_MIN", str(price_min), persist=True, hot_reload=False)
            config.set_config("PRICE_MAX", str(price_max), persist=True, hot_reload=False)
            config.reload_config()
        except Exception as e:
            self._on_log(f"[警告] 阈值保存失败（仍会使用当前输入值执行）：{e}")
        
        # Create and start worker
        self.worker = BlueOceanWorker(
            use_trending=True,
            growth_threshold=int(self.growth_spinbox.value()),
            max_reviews=int(self.review_spinbox.value()),
            price_min=float(self.price_min_spinbox.value()),
            price_max=float(self.price_max_spinbox.value()),
        )
        self.worker.log_signal.connect(self._on_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.error_signal.connect(self._on_error)
        # 统一结果信号：优先 data_signal，兼容旧 result_signal
        if hasattr(self.worker, "data_signal"):
            self.worker.data_signal.connect(self._on_results)
        elif hasattr(self.worker, "result_signal"):
            self.worker.result_signal.connect(self._on_results)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_results(self, products: list):
        self.results = products or []
    
    def stop_detection(self):
        """Stop detection"""
        if self.worker:
            self.worker.stop()
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
    
    def export_results(self):
        """导出结果到 Excel"""
        if not self.results:
            append_log(self.log_text, "没有结果可导出", level="WARNING")
            return
        
        try:
            filepath = export_blue_ocean_results(self.results, emit_log=self._on_log)
            append_log(self.log_text, f"已导出到: {filepath}", level="INFO")
        except Exception as e:
            append_log(self.log_text, f"导出失败: {str(e)}", level="ERROR")
    
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
        
        if self.worker and self.worker.filtered_products:
            self.results = self.worker.filtered_products
            self._populate_results_table()
            self.export_button.setEnabled(True)
            
            if self.auto_export_checkbox.isChecked():
                self.export_results()

        self.worker = None

    def shutdown(self):
        """窗口关闭时的资源清理。"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass
    
    def _populate_results_table(self):
        """Populate results table with data"""
        self.results_table.setRowCount(len(self.results))
        
        for row, product in enumerate(self.results):
            self.results_table.setItem(row, 0, QTableWidgetItem(product.get('title', '')))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(product.get('growth_rate', 0))))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(product.get('review_count', 0))))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"${product.get('price', 0)}"))
            
            profit = product.get('profit_margin', 0)
            
            # Ensure profit is a number (handle string '15.5%' or safe conversion)
            try:
                if isinstance(profit, str):
                    profit = float(profit.replace('%', ''))
                else:
                    profit = float(profit)
            except (ValueError, TypeError):
                profit = 0.0

            profit_item = QTableWidgetItem(f"{profit:.1f}%")
            
            # Highlight high profit
            if profit > 20:
                profit_item.setForeground(QColor("#00e676")) # Tech Green
            
            self.results_table.setItem(row, 4, profit_item)
            
            # Add taobao link button (simplified - just show URL)
            self.results_table.setItem(
                row, 5, 
                QTableWidgetItem("🔗 搜索")
            )

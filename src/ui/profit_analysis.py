"""
选品利润清洗池 UI (V2.0 核心模块)
功能：Excel 导入、实时利润核算、红绿灯视觉反馈、AI 选品参谋入口
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QLabel, QFileDialog, QMenu, QProgressBar, QMessageBox,
                             QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QDragEnterEvent, QDropEvent
import config
from workers.profit_worker import ExcelParserWorker, ProfitCalculator
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class ProfitAnalysisWidget(QWidget):
    """
    V2.0 核心模块：选品利润清洗池
    替代 V1.0 的蓝海监测器
    """

    def __init__(self):
        super().__init__()
        self.current_data = []
        self.load_profit_params()
        self.init_ui()
        # 启动时自动加载历史数据
        self.load_history_from_db()

    def load_profit_params(self):
        """从数据库加载利润核算参数（V2.0: profit_config），失败则回退默认值。"""
        defaults = {
            "exchange_rate": 7.25,
            "shipping_cost_per_kg": 12.0,
            "platform_commission": 0.05,
            "fixed_fee": 0.3,
        }

        self.exchange_rate = float(defaults["exchange_rate"])
        self.shipping_cost = float(defaults["shipping_cost_per_kg"])
        self.commission = float(defaults["platform_commission"])
        self.fixed_fee = float(defaults["fixed_fee"])

        try:
            db_path = str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS profit_config (key TEXT PRIMARY KEY, value TEXT)")
                cur.execute(
                    "SELECT key, value FROM profit_config WHERE key IN (?, ?, ?, ?)",
                    (
                        "exchange_rate",
                        "shipping_cost_per_kg",
                        "platform_commission",
                        "fixed_fee",
                    ),
                )
                rows = cur.fetchall()

            values = {k: v for k, v in rows}
            self.exchange_rate = float(values.get("exchange_rate", self.exchange_rate))
            self.shipping_cost = float(values.get("shipping_cost_per_kg", self.shipping_cost))
            self.commission = float(values.get("platform_commission", self.commission))
            self.fixed_fee = float(values.get("fixed_fee", self.fixed_fee))
        except Exception as e:
            logger.warning(f"利润参数加载失败，已使用默认值: {e}")

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. 标题栏
        title_label = QLabel("📊 选品利润清洗池")
        title_label.setObjectName("h1")
        
        # 2. 顶部控制栏
        top_bar = QHBoxLayout()
        self.lbl_status = QLabel("拖入或点击导入 EchoTik/Kalodata 导出的 Excel 文件")
        self.lbl_status.setProperty("variant", "muted")
        
        btn_import = QPushButton("📥 导入 SaaS 表格")
        btn_import.setFixedHeight(35)
        btn_import.setProperty("variant", "primary")
        btn_import.clicked.connect(self.open_file_dialog)
        
        btn_save = QPushButton("💾 保存到数据库")
        btn_save.setFixedHeight(35)
        btn_save.clicked.connect(self.save_to_database)
        
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        top_bar.addWidget(btn_import)
        top_bar.addWidget(btn_save)
        
        # 3. 参数显示栏
        param_bar = QHBoxLayout()
        self.param_label = QLabel(
            f"💵 当前参数: 汇率 {self.exchange_rate} | 运费 ${self.shipping_cost}/kg | "
            f"佣金 {int(self.commission*100)}% + ${self.fixed_fee}"
        )
        self.param_label.setProperty("variant", "muted")
        param_bar.addWidget(self.param_label)
        
        btn_config = QPushButton("⚙️ 配置参数")
        btn_config.setFixedSize(90, 26)
        btn_config.clicked.connect(self.open_config_dialog)
        param_bar.addWidget(btn_config)
        
        param_bar.addStretch() # Ensure left alignment
        
        # 4. 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # 5. 数据表格
        self.table = QTableWidget()
        self.table.setObjectName("ProfitTable")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "商品标题", "TK售价($)", "销量", "1688进价(¥)", "重量(kg)", "净利润($)", "ROI(%)", "操作"
        ])
        
        # 列宽设置
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in [1, 2, 3, 4, 5, 6]:
            self.table.setColumnWidth(i, 100)
        
        # 增加操作列宽度，确保按钮不被遮挡
        self.table.setColumnWidth(7, 35) 
        
        self.table.verticalHeader().setDefaultSectionSize(38) # Ensure comfortable row height
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.DoubleClicked)
        
        # 信号连接
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 布局组装
        layout.addWidget(title_label)
        layout.addLayout(top_bar)
        layout.addLayout(param_bar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.table)
        
        # 启用拖拽
        self.setAcceptDrops(True)

    # --- 拖拽处理 ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            if f.endswith(('.xlsx', '.csv')):
                self.start_parsing(f)
                break

    def open_file_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, '导入选品表', '', 
            'Excel Files (*.xlsx *.csv);;All Files (*)'
        )
        if fname:
            self.start_parsing(fname)

    def start_parsing(self, file_path):
        """启动 Worker 线程解析 Excel"""
        self.lbl_status.setText(f"📂 正在解析: {file_path.split('/')[-1]}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = ExcelParserWorker(file_path)
        self.worker.progress.connect(self.on_parsing_progress)
        self.worker.finished.connect(self.on_parsing_finished)
        self.worker.start()

    def on_parsing_progress(self, percent, msg):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(f"📂 {msg}")

    def on_parsing_finished(self, data, error):
        self.progress_bar.setVisible(False)
        
        if error:
            self.lbl_status.setText(f"❌ {error}")
            QMessageBox.warning(self, "解析失败", error)
            return
        
        self.current_data = data
        self.lbl_status.setText(f"✅ 导入成功: 共 {len(data)} 条数据")
        self.populate_table()

    def populate_table(self):
        """填充表格数据"""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        for row_idx, item in enumerate(self.current_data):
            self.table.insertRow(row_idx)
            
            # 只读字段
            self.table.setItem(row_idx, 0, QTableWidgetItem(item['title']))
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{item['tk_price']:.2f}"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(item['sales'])))
            
            # 可编辑字段
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{item['cny_cost']:.2f}"))
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{item['weight']:.2f}"))
            
            # 计算字段（只读）
            profit_item = QTableWidgetItem("0.00")
            profit_item.setFlags(profit_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row_idx, 5, profit_item)
            
            roi_item = QTableWidgetItem("0")
            roi_item.setFlags(roi_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row_idx, 6, roi_item)

            # 操作按钮 (Use cell widget for real buttons)
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0) # Maximize space usage
            btn_layout.setSpacing(0)
            
            btn_del = QPushButton("➖")
            btn_del.setToolTip("删除此行")
            # 移除硬编码尺寸，改用 QSS 控制 (Global Theme)
            # btn_del.setFixedSize(24, 20) 
            btn_del.setProperty("class", "table-action-btn")
            btn_del.setProperty("variant", "danger") 
            
            # Use closure to capture current row reference logic if needed, 
            # but usually row index changes on deletion. 
            # Better to store row id or use `indexAt` in slot.
            btn_del.clicked.connect(lambda _, r=row_idx: self.delete_row(r))
            
            # Re-bind is tricky with lambdas if rows shift. 
            # A cleaner way is using `sender()` and `indexAt`.
            # We will use a standard method instead of lambda for safety.
            btn_del.clicked.disconnect()
            btn_del.clicked.connect(self.on_delete_clicked)
            
            # Align center
            btn_layout.addWidget(btn_del)
            btn_layout.setAlignment(Qt.AlignCenter) 
            self.table.setCellWidget(row_idx, 7, btn_container)

            # 初始计算
            self.calculate_row_profit(row_idx)

        self.table.blockSignals(False)

    def on_delete_clicked(self):
        """Handle delete button click"""
        btn = self.sender()
        if not btn: return
        
        # Find which row contains this button
        # btn -> layout -> container -> table
        # simpler: map position
        pos = btn.parent().mapToGlobal(btn.pos())
        pos_in_table = self.table.viewport().mapFromGlobal(pos)
        row = self.table.rowAt(pos_in_table.y())
        
        if row >= 0:
            self.delete_row(row)

    def delete_row(self, row):
        """Remove row from data and table"""
        if 0 <= row < len(self.current_data):
            # Check DB ID if exists to delete from DB? 
            # Current logic just saves good ones to DB on demand.
            # If we want to delete from DB, we need ID linkage.
            # For now, just remove from UI list.
            
            # Confirm
            # res = QMessageBox.question(self, "确认", "删除此行？", QMessageBox.Yes | QMessageBox.No)
            # if res != QMessageBox.Yes: return

            del self.current_data[row]
            self.table.removeRow(row)

    def on_cell_changed(self, row, column):
        """单元格修改时触发重算"""
        if column in [3, 4]:  # 1688进价 或 重量
            try:
                # 更新内存数据
                if column == 3:
                    self.current_data[row]['cny_cost'] = float(self.table.item(row, 3).text())
                elif column == 4:
                    self.current_data[row]['weight'] = float(self.table.item(row, 4).text())
                
                self.calculate_row_profit(row)
            except ValueError:
                pass

    def calculate_row_profit(self, row):
        """计算单行利润并更新 UI"""
        try:
            tk_price = float(self.table.item(row, 1).text())
            cny_cost = float(self.table.item(row, 3).text())
            weight = float(self.table.item(row, 4).text())
            
            net_profit, roi = ProfitCalculator.calculate(
                tk_price, cny_cost, weight,
                self.exchange_rate, self.shipping_cost, 
                self.commission, self.fixed_fee
            )
            
            # 更新数据
            self.current_data[row]['net_profit'] = net_profit
            
            # 更新 UI
            self.table.item(row, 5).setText(f"{net_profit:.2f}")
            self.table.item(row, 6).setText(f"{int(roi)}")
            
            # 视觉反馈（红绿灯）
            self.update_row_visuals(row, net_profit)
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"计算利润失败 (行{row}): {e}")

    def update_row_visuals(self, row, profit):
        """
        红绿灯视觉系统：
        🔴 < $5: 红色背景（亏本警告）
        🟢 > $15: 绿色背景（推荐选品）
        ⚪ 其他: 默认
        """
        if profit < 5:
            bg_color = QColor("#3a1c1c")  # 暗红
            text_color = QColor("#ff5252")
        elif profit > 15:
            bg_color = QColor("#1c3a24")  # 暗绿
            text_color = QColor("#00e676")
        else:
            bg_color = QColor("#2b2b2b")
            text_color = QColor("#e0e0e0")
            
        for col in range(8):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(text_color)

    def show_context_menu(self, pos):
        """右键菜单"""
        menu = QMenu()
        analyze_action = menu.addAction("🤖 AI 选品参谋 (DeepSeek)")
        search_action = menu.addAction("🔍 1688 图搜")
        
        action = menu.exec_(self.table.mapToGlobal(pos))
        
        if action == analyze_action:
            current_row = self.table.currentRow()
            if current_row >= 0:
                title = self.table.item(current_row, 0).text()
                self.analyze_product_ai(title)
        elif action == search_action:
            QMessageBox.information(self, "功能开发中", "1688 图搜功能将在后续版本提供")

    def open_config_dialog(self):
        """打开参数配置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("利润核算参数配置")
        dialog.setFixedWidth(350)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        sb_exchange = QDoubleSpinBox()
        sb_exchange.setRange(1, 20)
        sb_exchange.setDecimals(4)
        sb_exchange.setValue(self.exchange_rate)
        form.addRow("汇率 (USD->CNY):", sb_exchange)
        
        sb_shipping = QDoubleSpinBox()
        sb_shipping.setRange(0, 100)
        sb_shipping.setValue(self.shipping_cost)
        sb_shipping.setSuffix(" $/kg")
        form.addRow("物流单价:", sb_shipping)
        
        sb_commission = QDoubleSpinBox()
        sb_commission.setRange(0, 1)
        sb_commission.setSingleStep(0.01)
        sb_commission.setValue(self.commission)
        form.addRow("平台佣金率:", sb_commission)
        
        sb_fixed = QDoubleSpinBox()
        sb_fixed.setRange(0, 100)
        sb_fixed.setValue(self.fixed_fee)
        sb_fixed.setSuffix(" $")
        form.addRow("固定费用:", sb_fixed)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            # Update values
            self.exchange_rate = sb_exchange.value()
            self.shipping_cost = sb_shipping.value()
            self.commission = sb_commission.value()
            self.fixed_fee = sb_fixed.value()
            
            # Save to DB
            self.save_profit_params()
            
            # Update UI Link
            self.param_label.setText(
                f"💵 当前参数: 汇率 {self.exchange_rate} | 运费 ${self.shipping_cost}/kg | "
                f"佣金 {int(self.commission*100)}% + ${self.fixed_fee}"
            )
            
            # Recalculate all rows
            for i in range(self.table.rowCount()):
                self.calculate_row_profit(i)
                
            QMessageBox.information(self, "更新成功", "参数已更新，所有商品利润已重新计算。")

    def save_profit_params(self):
        """保存参数到数据库"""
        try:
            db_path = str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                updates = [
                    ("exchange_rate", str(self.exchange_rate)),
                    ("shipping_cost_per_kg", str(self.shipping_cost)),
                    ("platform_commission", str(self.commission)),
                    ("fixed_fee", str(self.fixed_fee)),
                ]
                cur.executemany("INSERT OR REPLACE INTO profit_config (key, value) VALUES (?, ?)", updates)
                conn.commit()
        except Exception as e:
            logger.error(f"Save params failed: {e}")

    def analyze_product_ai(self, title):
        """调用 AI 参谋 (DeepSeek)"""
        from api.deepseek_client import get_deepseek_client
        from ui.toast import Toast
        
        client = get_deepseek_client()
        if not client.is_configured():
            QMessageBox.warning(self, "未配置", "AI 参谋需要配置 DeepSeek API Key。\n请前往【系统设置】进行配置。")
            return

        # Find row data
        row_data = None
        for item in self.current_data:
            if item['title'] == title:
                row_data = item
                break
        
        if not row_data:
            return

        Toast.show_info(self, f"正在分析商品: {title[:15]}...")
        QApplication.processEvents()

        # Call AI (Synchronous for now, ideally strictly async worker)
        # For simple text analysis, sync call might freeze UI for 2-5s, OK for MVP.
        # Improvement: Move to thread.
        try:
            analysis = client.analyze_product_potential(
                title, 
                row_data.get('tk_price', 0), 
                row_data.get('sales', 0)
            )
            
            # Show Result Dialog
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"AI 参谋报告 - {title[:10]}...")
            msg_box.setText(analysis)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setStyleSheet("QLabel{min-width: 400px;}")
            msg_box.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "分析失败", str(e))

    def load_history_from_db(self):
        """从数据库加载历史选品数据"""
        try:
            db_path = str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
            if not Path(db_path).exists():
                return
                
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # 检查表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product_history'")
                if not cursor.fetchone():
                    return

                # 读取最新的 500 条数据
                cursor.execute("""
                    SELECT title, tk_price, sales_count, cny_cost, weight, net_profit, source_file, image_url
                    FROM product_history 
                    ORDER BY created_at DESC 
                    LIMIT 500
                """)
                rows = cursor.fetchall()
            
            if not rows:
                return

            new_data = []
            for r in rows:
                new_data.append({
                    "title": r[0],
                    "tk_price": r[1],
                    "sales": r[2], # Map DB sales_count to dict sales
                    "cny_cost": r[3],
                    "weight": r[4],
                    "net_profit": r[5],
                    "source_file": r[6],
                    "image_url": r[7]
                })
            
            self.current_data = new_data
            self.populate_table()
            self.lbl_status.setText(f"📂 已加载 {len(rows)} 条历史记录")
            logger.info(f"[PROFIT] Loaded {len(rows)} history records from DB")

        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
            self.lbl_status.setText(f"❌ 加载历史失败: {e}")

    def save_to_database(self):
        """保存当前数据到 SQLite"""
        if not self.current_data:
            QMessageBox.warning(self, "无数据", "请先导入 Excel 数据")
            return
        
        try:
            db_path = str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                saved_count = 0
                for item in self.current_data:
                    if item['net_profit'] > 0:  # 只保存有利润数据的行
                        cursor.execute("""
                            INSERT INTO product_history 
                            (title, tk_price, sales_count, cny_cost, weight, net_profit, source_file, image_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            item['title'], item['tk_price'], item.get('sales', 0),
                            item['cny_cost'], item['weight'], item['net_profit'],
                            'excel_import', item.get('image_url', '')
                        ))
                        saved_count += 1

                conn.commit()
            
            QMessageBox.information(self, "保存成功", f"已保存 {saved_count} 条有效数据到数据库")
            logger.info(f"[PROFIT] 保存了 {saved_count} 条选品数据")
            
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            QMessageBox.critical(self, "保存失败", str(e))

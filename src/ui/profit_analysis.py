"""
选品利润清洗池 UI (V2.0 核心模块)
功能：Excel 导入、实时利润核算、红绿灯视觉反馈、AI 选品参谋入口
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QLabel, QFileDialog, QMenu, QProgressBar, QMessageBox,
                             QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QApplication,
                             QTextEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QDragEnterEvent, QDropEvent
import config
from workers.profit_worker import ExcelParserWorker, ProfitCalculator, AIAnalysisWorker
import logging
from pathlib import Path
import webbrowser
import urllib.parse
from ui.toast import Toast
from ui.role_prompt_dialog import open_role_prompt_dialog

# ORM Imports
from db.core import SessionLocal
from db.models import ProfitConfig, ProductHistory

logger = logging.getLogger(__name__)

class ProfitAnalysisWidget(QWidget):
    """
    V2.0 核心模块：选品利润清洗池
    替代 V1.0 的蓝海监测器
    """

    def __init__(self):
        super().__init__()
        self.current_data = []
        self.ai_workers = {} # Keep references to avoid GC
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

        session = SessionLocal()
        try:
            # Load from DB
            configs = session.query(ProfitConfig).filter(
                ProfitConfig.key.in_(defaults.keys())
            ).all()
            
            config_map = {c.key: c.value for c in configs}
            
            if "exchange_rate" in config_map:
                self.exchange_rate = float(config_map["exchange_rate"])
            if "shipping_cost_per_kg" in config_map:
                self.shipping_cost = float(config_map["shipping_cost_per_kg"])
            if "platform_commission" in config_map:
                self.commission = float(config_map["platform_commission"])
            if "fixed_fee" in config_map:
                self.fixed_fee = float(config_map["fixed_fee"])

        except Exception as e:
            logger.warning(f"利润参数加载失败，已使用默认值: {e}")
        finally:
            session.close()

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
        btn_config.setFixedSize(90, 35)
        btn_config.clicked.connect(self.open_config_dialog)
        param_bar.addWidget(btn_config)

        btn_role = QPushButton("🎭 配置AI角色")
        btn_role.setFixedSize(120, 35)
        btn_role.clicked.connect(self.open_ai_role_dialog)
        param_bar.addWidget(btn_role)
        
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
        self.table.setColumnWidth(7, 120) 
        
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

        # role_frame removed
        
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

    def open_ai_role_dialog(self):
        """配置 AI 选品参谋的角色提示词（持久化到 .env）。"""
        current = (getattr(config, "AI_PROFIT_ROLE_PROMPT", "") or "").strip()
        text = open_role_prompt_dialog(
            self,
            title="AI 选品参谋角色提示词",
            initial_text=current,
            help_text="将作为系统提示词注入选品分析，影响分析角度与输出风格。",
        )
        if text is None:
            return
        try:
            config.set_config("AI_PROFIT_ROLE_PROMPT", text, persist=True, hot_reload=False)
        except Exception:
            pass
        # Preview update removed

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
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(4)
            
            # 1. AI 分析按钮
            btn_ai = QPushButton("🤖")
            btn_ai.setToolTip("AI 选品参谋")
            btn_ai.setFixedSize(28, 24)
            btn_ai.setProperty("class", "table-action-btn")
            btn_ai.clicked.connect(self.on_ai_analyze_clicked)
            btn_layout.addWidget(btn_ai)
            
            # 2. 1688 搜同款按钮
            btn_search = QPushButton("🔍")
            btn_search.setToolTip("在 1688 搜索同款")
            btn_search.setFixedSize(28, 24)
            btn_search.setProperty("class", "table-action-btn")
            btn_search.clicked.connect(self.on_search_clicked)
            btn_layout.addWidget(btn_search)
            
            # 3. 删除按钮
            btn_del = QPushButton("➖")
            btn_del.setToolTip("删除此行")
            btn_del.setFixedSize(28, 24)
            btn_del.setProperty("class", "table-action-btn")
            btn_del.setProperty("variant", "danger") 
            btn_del.clicked.connect(self.on_delete_clicked)
            btn_layout.addWidget(btn_del)
            
            btn_layout.setAlignment(Qt.AlignCenter) 
            self.table.setCellWidget(row_idx, 7, btn_container)

            # 初始计算
            self.calculate_row_profit(row_idx)

        self.table.blockSignals(False)

    def on_ai_analyze_clicked(self):
        """Handle AI Analyze button click"""
        btn = self.sender()
        if not btn: return
        pos = btn.parent().mapToGlobal(btn.pos())
        pos_in_table = self.table.viewport().mapFromGlobal(pos)
        row = self.table.rowAt(pos_in_table.y())
        if row >= 0:
            item = self.current_data[row]
            self.start_ai_worker(item['title'], item.get('tk_price', 0), item.get('sales', 0))

    def on_search_clicked(self):
        """Handle 1688 Search button click"""
        btn = self.sender()
        if not btn: return
        pos = btn.parent().mapToGlobal(btn.pos())
        pos_in_table = self.table.viewport().mapFromGlobal(pos)
        row = self.table.rowAt(pos_in_table.y())
        if row >= 0:
            title = self.current_data[row].get('title', '')
            if title:
                # 1688 Image Search (Literal Search)
                # Ideally use image search API, but here we fallback to text search which works for MVP
                # Cleaning title for better search results
                clean_title = title.replace("TikTok", "").strip()[:50] 
                url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={urllib.parse.quote(clean_title)}"
                webbrowser.open(url)
                Toast.show_info(self, "已打开浏览器搜索同款")

    def start_ai_worker(self, title, price, sales):
        """启动异步 AI 分析线程"""
        if title in self.ai_workers:
            Toast.show_warning(self, "该商品正在分析中，请稍候...")
            return

        worker = AIAnalysisWorker(title, price, sales)
        worker.finished.connect(lambda t, res: self.on_ai_finished(t, res))
        worker.error.connect(lambda t, err: self.on_ai_error(t, err))
        
        self.ai_workers[title] = worker
        worker.start()
        Toast.show_info(self, f"🤖 AI 正在分析: {title[:15]}...")

    def on_ai_finished(self, title, result):
        if title in self.ai_workers:
            del self.ai_workers[title]
        
        # Show Result
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"AI 参谋报告")
        msg_box.setText(result)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setStyleSheet("QLabel{min-width: 500px; min-height: 300px;}")
        msg_box.exec_()

    def on_ai_error(self, title, error):
        if title in self.ai_workers:
            del self.ai_workers[title]
        Toast.show_error(self, f"分析失败: {error}")

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
        """保存参数到数据库 (ORM)"""
        session = SessionLocal()
        try:
            updates = {
                "exchange_rate": str(self.exchange_rate),
                "shipping_cost_per_kg": str(self.shipping_cost),
                "platform_commission": str(self.commission),
                "fixed_fee": str(self.fixed_fee),
            }
            
            for key, val in updates.items():
                # Merge: if exists update, else insert
                # ProfitConfig has primary key 'key'
                conf = ProfitConfig(key=key, value=val)
                session.merge(conf)
            
            session.commit()
            logger.info("Profit params saved to DB")
        except Exception as e:
            session.rollback()
            logger.error(f"Save params failed: {e}")
        finally:
            session.close()

    def analyze_product_ai(self, title):
        """调用 AI 参谋 (DeepSeek)"""
        # Find row data
        row_data = None
        for item in self.current_data:
            if item['title'] == title:
                row_data = item
                break
        
        if not row_data:
            return

        self.start_ai_worker(title, row_data.get('tk_price', 0), row_data.get('sales', 0))

    def load_history_from_db(self):
        """从数据库加载历史选品数据 (ORM)"""
        session = SessionLocal()
        try:
            # 读取最新的 500 条数据
            # SQLAlchemy 的 Model 字段是自动映射的
            history_items = session.query(ProductHistory).order_by(ProductHistory.created_at.desc()).limit(500).all()
            
            if not history_items:
                return

            new_data = []
            for r in history_items:
                new_data.append({
                    "title": r.title,
                    "tk_price": r.tk_price,
                    "sales": r.sales_count,
                    "cny_cost": r.cny_cost,
                    "weight": r.weight,
                    "net_profit": r.net_profit,
                    "source_file": r.source_file,
                    "image_url": r.image_url
                })
            
            self.current_data = new_data
            self.populate_table()
            self.lbl_status.setText(f"📂 已加载 {len(history_items)} 条历史记录")
            logger.info(f"[PROFIT] Loaded {len(history_items)} history records from DB")

        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
            self.lbl_status.setText(f"❌ 加载历史失败: {e}")
        finally:
            session.close()

    def save_to_database(self):
        """保存当前数据到 SQLite (ORM)"""
        if not self.current_data:
            QMessageBox.warning(self, "无数据", "请先导入 Excel 数据")
            return
        
        session = SessionLocal()
        try:
            saved_count = 0
            for item in self.current_data:
                if item['net_profit'] > 0:  # 只保存有利润数据的行
                    history = ProductHistory(
                        title=item['title'],
                        tk_price=item['tk_price'],
                        sales_count=item.get('sales', 0),
                        cny_cost=item['cny_cost'],
                        weight=item['weight'],
                        net_profit=item['net_profit'],
                        source_file='excel_import',
                        image_url=item.get('image_url', '')
                    )
                    session.add(history)
                    saved_count += 1
            
            session.commit()
            
            QMessageBox.information(self, "保存成功", f"已保存 {saved_count} 条有效数据到数据库")
            logger.info(f"[PROFIT] 保存了 {saved_count} 条选品数据")
            
        except Exception as e:
            session.rollback()
            logger.error(f"保存数据失败: {e}")
            QMessageBox.critical(self, "保存失败", str(e))
        finally:
            session.close()

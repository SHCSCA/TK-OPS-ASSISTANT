"""
利润核算 Worker
负责解析 Excel 文件和执行利润计算
"""
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal
import logging
import os

logger = logging.getLogger(__name__)

class ExcelParserWorker(QThread):
    """
    负责解析 EchoTik/Kalodata 导出的大型 Excel 文件。
    避免阻塞主 UI 线程。
    """
    finished = pyqtSignal(list, str)  # data_rows, error_msg
    progress = pyqtSignal(int, str)   # percentage, message

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        if not os.path.exists(self.file_path):
            self.finished.emit([], "文件不存在")
            return

        try:
            self.progress.emit(10, "正在读取 Excel 文件...")
            
            # 使用 pandas 读取，支持 .xlsx 和 .csv
            if self.file_path.endswith('.csv'):
                df = pd.read_csv(self.file_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(self.file_path, engine='openpyxl')
            
            self.progress.emit(30, "正在识别列...")
            
            # 智能字段映射逻辑（根据关键词猜测）
            column_map = {}
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['title', '名称', '标题', 'name', 'product']):
                    column_map['title'] = col
                elif any(keyword in col_str for keyword in ['price', '售价', '价格']):
                    column_map['tk_price'] = col
                elif any(keyword in col_str for keyword in ['sales', '销量', 'sold']):
                    column_map['sales'] = col
                elif any(keyword in col_str for keyword in ['image', '主图', 'img', 'pic']):
                    column_map['image_url'] = col

            if 'title' not in column_map:
                self.finished.emit([], "无法识别表格格式：未找到【商品标题】列")
                return

            self.progress.emit(50, f"开始解析 {len(df)} 条数据...")
            
            processed_data = []
            for index, row in df.iterrows():
                # 提取并清洗数据
                tk_price_raw = row.get(column_map.get('tk_price'), 0)
                try:
                    # 移除美元符号和逗号
                    tk_price = float(str(tk_price_raw).replace('$', '').replace(',', '').strip())
                except:
                    tk_price = 0.0

                item = {
                    'title': str(row.get(column_map.get('title'), 'Unknown')).strip(),
                    'tk_price': tk_price,
                    'sales': str(row.get(column_map.get('sales'), 0)),
                    'image_url': str(row.get(column_map.get('image_url'), '')),
                    # 默认初始化值（用户手动填写）
                    'cny_cost': 0.0,
                    'weight': 0.0,
                    'net_profit': 0.0
                }
                processed_data.append(item)
                
                # 更新进度
                if (index + 1) % 100 == 0:
                    progress = 50 + int((index + 1) / len(df) * 40)
                    self.progress.emit(progress, f"已解析 {index + 1}/{len(df)} 条")

            self.progress.emit(100, "解析完成")
            self.finished.emit(processed_data, "")

        except Exception as e:
            logger.error(f"Excel 解析失败: {e}", exc_info=True)
            self.finished.emit([], f"解析失败: {str(e)}")


class ProfitCalculator:
    """
    静态工具类：执行利润核算
    公式：净利润 = TK售价 - (1688进价/汇率) - (重量*头程) - (TK售价*佣金率 + 固定费)
    """
    
    @staticmethod
    def calculate(tk_price, cny_cost, weight, exchange_rate, shipping_cost_per_kg, commission_rate, fixed_fee):
        """
        返回: (净利润, ROI百分比)
        """
        try:
            # 成本计算
            product_cost_usd = cny_cost / exchange_rate
            shipping_fee = weight * shipping_cost_per_kg
            platform_fee = (tk_price * commission_rate) + fixed_fee
            
            total_cost = product_cost_usd + shipping_fee + platform_fee
            net_profit = tk_price - total_cost
            
            # ROI 计算
            roi = (net_profit / total_cost * 100) if total_cost > 0 else 0
            
            return net_profit, roi
            
        except (ValueError, ZeroDivisionError) as e:
            logger.warning(f"利润计算异常: {e}")
            return 0.0, 0.0


class AIAnalysisWorker(QThread):
    """
    负责调用 DeepSeek 进行选品分析的异步 Worker。
    避免界面卡死。
    """
    finished = pyqtSignal(str, str) # title, analysis_result_text
    error = pyqtSignal(str, str)    # title, error_message

    def __init__(self, title, price, sales):
        super().__init__()
        self.title = title
        self.price = price
        self.sales = sales

    def run(self):
        try:
            from api.deepseek_client import get_deepseek_client
            client = get_deepseek_client()
            
            if not client.is_configured():
                self.error.emit(self.title, "未配置 AI API Key")
                return

            # Simulate network delay if needed, or just call
            analysis = client.analyze_product_potential(
                self.title, 
                self.price, 
                self.sales
            )
            self.finished.emit(self.title, analysis)
        except Exception as e:
            logger.error(f"AI Analysis Failed: {e}", exc_info=True)
            self.error.emit(self.title, str(e))

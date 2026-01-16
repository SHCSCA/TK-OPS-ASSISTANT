"""蓝海监测后台线程（QThread）"""
from typing import List, Dict, Optional
from PyQt5.QtCore import pyqtSignal
import config
from api.echotik_api import EchoTikApiClient
from api.taobao_utils import generate_taobao_search_url
from workers.base_worker import BaseWorker
import time


class BlueOceanWorker(BaseWorker):
    """Worker for blue ocean product detection"""

    # 将结果直接发回 UI（列表：每个元素为商品字典）
    result_signal = pyqtSignal(list)
    
    def __init__(
        self,
        keyword: str = None,
        use_trending: bool = True,
        growth_threshold: int | None = None,
        max_reviews: int | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        **kwargs,
    ):
        """
        Initialize blue ocean worker
        
        Args:
            keyword: Search keyword (if not using trending)
            use_trending: Whether to fetch trending or search
            **kwargs: API credentials
        """
        super().__init__()
        self.keyword = keyword
        self.use_trending = use_trending
        self.api_client = EchoTikApiClient()
        self.products = []
        self.filtered_products = []

        self.growth_threshold = int(growth_threshold) if growth_threshold is not None else int(getattr(config, "GROWTH_RATE_THRESHOLD", 500))
        self.max_reviews = int(max_reviews) if max_reviews is not None else int(getattr(config, "MAX_REVIEWS", 50))
        self.price_min = float(price_min) if price_min is not None else float(getattr(config, "PRICE_MIN", 20))
        self.price_max = float(price_max) if price_max is not None else float(getattr(config, "PRICE_MAX", 80))
    
    def _run_impl(self):
        """Execute blue ocean detection"""
        self.emit_log("开始蓝海监测（数据源：EchoTik）...")
        self.emit_progress(0)

        # Step 1: Fetch products
        self.emit_log("正在从 EchoTik API 获取数据...")
        products = self._fetch_products()

        if not products:
            self.emit_error("API请求失败或未返回数据 (请检查 EchoTik 是否正确配置)")
            self.emit_finished(False, "未返回数据")
            return

        self.products = products
        self.emit_log(f"成功获取 {len(products)} 个商品")
        self.emit_progress(20)

        # Step 2: Filter products
        self.emit_log("正在应用蓝海筛选条件...")
        self.filtered_products = self._apply_filters(products)
        self.emit_log(f"筛选结果：{len(self.filtered_products)} 个蓝海商品")
        self.emit_progress(50)

        # Step 3: Enrich data
        self.emit_log("正在补充商品信息（如 1688 搜索链接）...")
        enriched_products = self._enrich_products(self.filtered_products)
        self.emit_progress(80)

        # Step 4: Report results
        self.emit_log(f"✓ 监测完成！发现 {len(enriched_products)} 个高潜力商品")
        for product in enriched_products:
            self.emit_log(
                f"  *** 命中蓝海 *** {product['title']} (销量: {product.get('growth_rate', '?')}, 价格: ${product.get('price', '?')})"
            )

        try:
            self.result_signal.emit(enriched_products)
        except Exception:
            pass
        try:
            self.data_signal.emit(enriched_products)
        except Exception:
            pass
        self.emit_progress(100)
        self.emit_finished(True, "蓝海监测完成")
    
    def _fetch_products(self) -> Optional[List[Dict]]:
        """从 EchoTik 拉取候选商品列表。"""
        if self.use_trending:
            self.emit_log("获取商品榜单（周销量榜）...")
            return self.api_client.fetch_trending_products(count=100)
        else:
            if not self.keyword:
                self.emit_error("未提供搜索关键字")
                return None
            # TODO：待 EchoTik 的关键字搜索接口确认后再接入；当前先回退到热门榜单。
            self.emit_log("暂未支持关键字搜索，已回退为获取热门榜单...")
            return self.api_client.fetch_trending_products(count=50)
    
    def _apply_filters(self, products: List[Dict]) -> List[Dict]:
        """
        应用过滤条件 + 将 EchoTik 字段映射到本项目内部 schema。

        备注：
        - EchoTik 字段命名可能随版本变化，建议在这里集中做兼容处理。
        """
        filtered = []
        
        for p in products:
            # 字段映射：
            # - total_sale_cnt：近7日销量/增长指标（本项目用 growth_rate）
            # - spu_avg_price / max_price：价格
            # - comment_cnt / review_cnt：评论数
            
            try:
                growth_rate = int(float(p.get('total_sale_cnt') or 0))
            except Exception:
                growth_rate = 0

            try:
                review_count = int(float(p.get('comment_cnt') or p.get('review_cnt') or 0))
            except Exception:
                review_count = 0

            try:
                price = float(p.get('spu_avg_price') or p.get('max_price') or 0)
            except Exception:
                price = 0.0

            mapped_product = {
                'title': p.get('product_name', 'Unknown'),
                'tk_url': f"https://shop.tiktok.com/view/product/{p.get('product_id')}",
                'main_image_url': p.get('cover', ''),
                'growth_rate': growth_rate,
                'review_count': review_count,
                'price': price,
                'top_video_url': "",
                'id': p.get('product_id')
            }
            
            # Filtering Logic
            # 1. Growth Filter (Sales Volume)
            if mapped_product['growth_rate'] < self.growth_threshold:
                continue
                
            # 2. Review Count Filter
            if mapped_product['review_count'] > self.max_reviews:
                continue
            
            # 3. Price Filter
            if not (self.price_min <= mapped_product['price'] <= self.price_max):
                continue
            
            filtered.append(mapped_product)
            
        return filtered

    def _enrich_products(self, products: List[Dict]) -> List[Dict]:
        """Add computed fields like profit margin and 1688 links"""
        enriched = []
        for p in products:
            # 1688 Search Link
            taobao_url = generate_taobao_search_url(p['title'])
            
            p['taobao_url'] = taobao_url
            # 统一用数值类型（百分比），避免 UI/导出阶段再出现字符串比较错误
            # 这里仍是估算：后续若接入真实成本，可替换为真实毛利
            estimated_margin_pct = 50.0
            p['profit_margin'] = estimated_margin_pct

            # 兜底：如果配置了 MIN_PROFIT_MARGIN，允许后续筛选/标注使用
            # （不在此处强行过滤，避免改变现有业务行为）
            
            enriched.append(p)
        return enriched


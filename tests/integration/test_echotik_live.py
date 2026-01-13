import pytest
import sys
import os
from pathlib import Path

# Add src to path if not present
sys.path.append(str(Path(__file__).parents[2] / "src"))

from api.echotik_api import EchoTikApiClient
from workers.blue_ocean_worker import BlueOceanWorker

# Credentials provided by user
USERNAME = "250430516894748909"
PASSWORD = "7c208ed72d0c4347aa744432362edbf2"

def test_echotik_connectivity():
    """Test direct API connectivity"""
    print(f"\n[测试 1] 验证 EchoTik API 连接...")
    client = EchoTikApiClient(api_key=USERNAME, api_secret=PASSWORD)
    success, msg = client.check_connection()
    print(f"连接结果: {msg}")
    
    assert success is True, f"连接失败: {msg}"

def test_blue_ocean_worker_flow():
    """Test Blue Ocean Worker Logic (Integration)"""
    print(f"\n[测试 2] 验证蓝海选品逻辑...")
    
    # Initialize worker
    worker = BlueOceanWorker(use_trending=True)
    
    # Manually inject credentials into the worker's client
    worker.api_client = EchoTikApiClient(api_key=USERNAME, api_secret=PASSWORD)
    
    # 1. Fetch products
    print("步骤 1: 获取商品列表...")
    products = worker._fetch_products()
    
    assert products is not None, "获取商品失败，返回为 None"
    assert len(products) > 0, f"获取商品数量为 0"
    print(f"成功获取原始商品: {len(products)} 个")
    
    # 2. Filter products
    print("步骤 2: 应用蓝海过滤...")
    filtered = worker._apply_filters(products)
    print(f"筛选后剩余: {len(filtered)} 个")
    # Note: It's okay if filtered is 0, depends on realtime data and thresholds
    # But we want to ensure the function ran correctly
    assert isinstance(filtered, list)
    
    # 3. Enrich products
    if len(filtered) > 0:
        print("步骤 3: 补充信息...")
        enriched = worker._enrich_products(filtered)
        print(f"最终结果示例: {enriched[0]['title']} (利润: {enriched[0]['profit_margin']})")
        print(f"DEBUG Keys: {enriched[0].keys()}")
        assert 'taobao_url' in enriched[0]
        assert 'profit_margin' in enriched[0]
    else:
        print("没有商品满足蓝海条件，但逻辑执行正常。")

if __name__ == "__main__":
    # Allow running directly with python
    try:
        test_echotik_connectivity()
        test_blue_ocean_worker_flow()
        print("\n所有测试通过！✅")
    except AssertionError as e:
        import traceback
        traceback.print_exc()
        print(f"\n测试失败 ❌: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n发生错误 ❌: {e}")

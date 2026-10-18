#!/usr/bin/env python3
"""调试地图坐标问题"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.amap_service import get_amap_service
from core.logger import logger

def test_poi_search():
    """测试POI搜索并查看返回数据格式"""
    print("=" * 60)
    print("测试高德地图POI搜索")
    print("=" * 60)

    try:
        service = get_amap_service()
        print("✅ AmapService 初始化成功")

        # 搜索杭州西湖
        print("\n🔍 搜索杭州西湖...")
        results = service.search_poi("西湖", "杭州")

        print(f"\n✅ 找到 {len(results)} 个结果")

        for i, poi in enumerate(results[:3]):
            print(f"\n--- POI {i+1} ---")
            print(f"名称: {poi.get('name', 'N/A')}")
            print(f"地址: {poi.get('address', 'N/A')}")
            print(f"位置: {poi.get('location', 'N/A')}")

            # 检查是否有经纬度字段
            if 'location' in poi:
                loc = poi['location']
                if isinstance(loc, str) and ',' in loc:
                    lon, lat = loc.split(',')
                    print(f"  - 经度: {lon}")
                    print(f"  - 纬度: {lat}")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_poi_search()

"""高德地图MCP服务封装 - 基于EsAgent框架"""

from typing import List, Dict, Any, Optional
from settings import settings
from core.logger import logger
from core.EsAgent.tools import MCPTool


def get_amap_mcp_tool() -> MCPTool:
    """
    获取高德地图MCP工具实例(单例模式，使用 MCPTool.get_or_create)

    Returns:
        MCPTool实例
    """
    if not settings.AMAP_API_KEY:
        raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")

    # 使用 MCPTool.get_or_create() 获取单例
    tool = MCPTool.get_or_create(
        name="amap",
        description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",
        server_command=["uvx", "amap-mcp-server"],
        env={"AMAP_MAPS_API_KEY": settings.AMAP_API_KEY},
        auto_expand=True
    )

    logger.info("高德地图MCP工具单例获取成功")
    return tool


class AmapService:
    """高德地图服务封装类"""

    def __init__(self):
        """初始化服务"""
        self.mcp_tool = get_amap_mcp_tool()

    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[Dict[str, Any]]:
        """
        搜索POI

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_text_search",
                "arguments": {
                    "keywords": keywords,
                    "city": city,
                    "citylimit": str(citylimit).lower()
                }
            })

            # 尝试解析JSON结果
            import json
            import re

            # 先直接尝试解析整个结果
            data = None
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                pass

            # 如果直接解析失败，尝试正则提取
            if data is None:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

            # 如果解析成功，处理数据
            if data is not None:
                if isinstance(data, dict):
                    # 根据amap-mcp-server的返回格式解析
                    if 'pois' in data:
                        return data['pois']
                    elif 'data' in data and isinstance(data['data'], list):
                        return data['data']
                elif isinstance(data, list):
                    return data

            return []

        except Exception as e:
            logger.error(f"POI搜索失败: {str(e)}")
            return []

    def get_weather(self, city: str) -> List[Dict[str, Any]]:
        """
        查询天气

        Args:
            city: 城市名称

        Returns:
            天气信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_weather",
                "arguments": {
                    "city": city
                }
            })

            logger.debug(f"天气查询结果: {result[:200]}...")

            # 尝试解析JSON结果
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if isinstance(data, dict):
                        if 'forecasts' in data:
                            return data['forecasts']
                        elif 'data' in data and isinstance(data['data'], list):
                            return data['data']
                except json.JSONDecodeError:
                    pass

            return [{"raw": result}]

        except Exception as e:
            logger.error(f"天气查询失败: {str(e)}")
            return []

    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Dict[str, Any]:
        """
        规划路线

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)

        Returns:
            路线信息
        """
        try:
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
                "transit": "maps_direction_transit_integrated_by_address"
            }

            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")

            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address
            }

            # 公共交通需要城市参数
            if route_type == "transit":
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            else:
                # 其他路线类型也可以提供城市参数提高准确性
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city

            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": tool_name,
                "arguments": arguments
            })

            logger.debug(f"路线规划结果: {result[:200]}...")

            # 尝试解析JSON结果
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return data
                except json.JSONDecodeError:
                    pass

            return {"raw": result}

        except Exception as e:
            logger.error(f"路线规划失败: {str(e)}")
            return {}

    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Dict[str, float]]:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标 {"longitude": float, "latitude": float}
        """
        try:
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_geo",
                "arguments": arguments
            })

            logger.debug(f"地理编码结果: {result[:200]}...")

            # 尝试解析JSON结果
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if isinstance(data, dict):
                        if 'geocodes' in data and data['geocodes']:
                            geo = data['geocodes'][0]
                            if 'location' in geo:
                                lon, lat = geo['location'].split(',')
                                return {"longitude": float(lon), "latitude": float(lat)}
                except json.JSONDecodeError:
                    pass

            return None

        except Exception as e:
            logger.error(f"地理编码失败: {str(e)}")
            return None

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        try:
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_search_detail",
                "arguments": {
                    "id": poi_id
                }
            })

            # 解析结果
            import json
            import re

            data = None
            # 先直接尝试解析
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                pass

            # 正则提取
            if data is None:
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

            if data is not None:
                # 如果有pois字段，取第一个
                if isinstance(data, dict) and 'pois' in data and data['pois']:
                    return data['pois'][0]
                # 如果是dict直接返回
                if isinstance(data, dict):
                    return data

            return {}

        except Exception as e:
            logger.error(f"获取POI详情失败: {str(e)}")
            return {}


# 创建全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service

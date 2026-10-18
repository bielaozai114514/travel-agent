"""地图服务API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from schemas.trip import (
    POISearchRequest,
    POISearchResponse,
    RouteRequest,
    RouteResponse,
    WeatherResponse,
    ErrorResponse
)
from services.amap_service import get_amap_service
from core.logger import logger

router = APIRouter(prefix="/map", tags=["地图服务"])


@router.get(
    "/poi",
    response_model=POISearchResponse,
    responses={500: {"model": ErrorResponse}},
    summary="搜索POI",
    description="根据关键词搜索POI(兴趣点)"
)
async def search_poi(
    keywords: str = Query(..., description="搜索关键词", examples="故宫"),
    city: str = Query(..., description="城市", examples="北京"),
    citylimit: bool = Query(True, descriptions="是否限制在城市范围内")
):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市
        citylimit: 是否限制在城市范围内

    Returns:
        POI搜索结果
    """
    try:
        logger.info(f"搜索POI: keywords={keywords}, city={city}")

        # 获取服务实例
        service = get_amap_service()

        # 搜索POI
        pois = service.search_poi(keywords, city, citylimit)

        # 转换为POIInfo列表（简化处理，实际应解析返回数据）
        from schemas.trip import POIInfo, Location
        poi_list = []
        for i, poi in enumerate(pois[:10]):  # 最多返回10个
            if isinstance(poi, dict):
                # 尝试从字典中提取信息
                poi_info = POIInfo(
                    id=poi.get('id', str(i)),
                    name=poi.get('name', f'POI-{i}'),
                    type=poi.get('type', '景点'),
                    address=poi.get('address', ''),
                    location=Location(
                        longitude=poi.get('longitude', 116.4),
                        latitude=poi.get('latitude', 39.9)
                    ),
                    tel=poi.get('tel')
                )
                poi_list.append(poi_info)

        return POISearchResponse(
            success=True,
            message="POI搜索成功",
            data=poi_list
        )

    except Exception as e:
        logger.error(f"POI搜索失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"POI搜索失败: {str(e)}"
        )


@router.get(
    "/weather",
    response_model=WeatherResponse,
    responses={500: {"model": ErrorResponse}},
    summary="查询天气",
    description="查询指定城市的天气信息"
)
async def get_weather(
    city: str = Query(..., description="城市名称", examples="北京")
):
    """
    查询天气

    Args:
        city: 城市名称

    Returns:
        天气信息
    """
    try:
        logger.info(f"查询天气: city={city}")

        # 获取服务实例
        service = get_amap_service()

        # 查询天气
        weather_data = service.get_weather(city)

        # 转换为WeatherInfo列表
        from schemas.trip import WeatherInfo
        weather_list = []
        for i, weather in enumerate(weather_data[:7]):  # 最多返回7天
            if isinstance(weather, dict):
                weather_info = WeatherInfo(
                    date=weather.get('date', ''),
                    day_weather=weather.get('day_weather', ''),
                    night_weather=weather.get('night_weather', ''),
                    day_temp=weather.get('day_temp', 0),
                    night_temp=weather.get('night_temp', 0),
                    wind_direction=weather.get('wind_direction', ''),
                    wind_power=weather.get('wind_power', '')
                )
                weather_list.append(weather_info)

        return WeatherResponse(
            success=True,
            message="天气查询成功",
            data=weather_list
        )

    except Exception as e:
        logger.error(f"天气查询失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"天气查询失败: {str(e)}"
        )


@router.post(
    "/route",
    response_model=RouteResponse,
    responses={500: {"model": ErrorResponse}},
    summary="规划路线",
    description="规划两点之间的路线"
)
async def plan_route(request: RouteRequest):
    """
    规划路线

    Args:
        request: 路线规划请求

    Returns:
        路线信息
    """
    try:
        logger.info(f"规划路线: {request.origin_address} -> {request.destination_address}")

        # 获取服务实例
        service = get_amap_service()

        # 规划路线
        route_data = service.plan_route(
            origin_address=request.origin_address,
            destination_address=request.destination_address,
            origin_city=request.origin_city,
            destination_city=request.destination_city,
            route_type=request.route_type
        )

        # 构建RouteInfo
        from schemas.trip import RouteInfo
        route_info = RouteInfo(
            distance=route_data.get('distance', 0) if isinstance(route_data, dict) else 0,
            duration=route_data.get('duration', 0) if isinstance(route_data, dict) else 0,
            route_type=request.route_type,
            description=route_data.get('description', '') if isinstance(route_data, dict) else str(route_data)
        )

        return RouteResponse(
            success=True,
            message="路线规划成功",
            data=route_info
        )

    except Exception as e:
        logger.error(f"路线规划失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"路线规划失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查地图服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 检查服务是否可用
        service = get_amap_service()

        return {
            "status": "healthy",
            "service": "map-service",
            "mcp_tools_available": service.mcp_tool is not None,
            "mcp_tools_count": len(service.mcp_tool._available_tools) if service.mcp_tool else 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )

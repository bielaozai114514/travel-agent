"""POI相关API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from schemas.trip import ErrorResponse
from services.amap_service import get_amap_service
from core.logger import logger

router = APIRouter(prefix="/poi", tags=["POI"])


class POIDetailResponse:
    """POI详情响应"""
    success: bool
    message: str
    data: Optional[dict] = None


@router.get(
    "/detail/{poi_id}",
    summary="获取POI详情",
    description="根据POI ID获取详细信息",
    responses={500: {"model": ErrorResponse}}
)
async def get_poi_detail(poi_id: str):
    """
    获取POI详情

    Args:
        poi_id: POI ID

    Returns:
        POI详情响应
    """
    try:
        logger.info(f"获取POI详情: poi_id={poi_id}")
        amap_service = get_amap_service()

        # 调用高德地图POI详情API
        result = amap_service.get_poi_detail(poi_id)

        return {
            "success": True,
            "message": "获取POI详情成功",
            "data": result
        }

    except Exception as e:
        logger.error(f"获取POI详情失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取POI详情失败: {str(e)}"
        )


@router.get(
    "/search",
    summary="搜索POI",
    description="根据关键词搜索POI",
    responses={500: {"model": ErrorResponse}}
)
async def search_poi(
    keywords: str = Query(..., description="搜索关键词"),
    city: str = Query("北京", description="城市名称")
):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    try:
        logger.info(f"搜索POI: keywords={keywords}, city={city}")
        amap_service = get_amap_service()
        result = amap_service.search_poi(keywords, city)

        return {
            "success": True,
            "message": "搜索成功",
            "data": result
        }

    except Exception as e:
        logger.error(f"搜索POI失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索POI失败: {str(e)}"
        )

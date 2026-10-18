"""坐标修正服务 - 确保景点坐标正确"""

from typing import List, Dict, Any, Optional
from core.logger import logger
from services.amap_service import get_amap_service
from schemas.trip import TripPlan, Attraction, DayPlan, Location


def is_valid_coordinate(lon: float, lat: float) -> bool:
    """
    检查坐标是否在中国范围内（大致范围）

    中国大致范围:
    经度: 73.5 ~ 135.0
    纬度: 18.0 ~ 53.5
    """
    return 73.5 <= lon <= 135.0 and 18.0 <= lat <= 53.5


def fix_trip_plan_locations(trip_plan: TripPlan) -> TripPlan:
    """
    修正旅行计划中所有景点的坐标

    Args:
        trip_plan: 原始旅行计划

    Returns:
        修正后的旅行计划
    """
    logger.info(f"🔧 [LocationFix] 开始修正坐标: {trip_plan.city}")

    try:
        amap_service = get_amap_service()
    except Exception as e:
        logger.warning(f"⚠️  [LocationFix] 无法获取高德地图服务: {e}，跳过坐标修正")
        return trip_plan

    fixed_count = 0
    total_count = 0

    for day_idx, day_plan in enumerate(trip_plan.days):
        fixed_attractions = []

        for attraction in day_plan.attractions:
            total_count += 1
            original_loc = attraction.location
            fixed_attraction = fix_attraction_location(
                attraction,
                trip_plan.city,
                amap_service
            )

            if fixed_attraction.location != original_loc:
                fixed_count += 1

            fixed_attractions.append(fixed_attraction)

        day_plan.attractions = fixed_attractions

    logger.info(f"✅ [LocationFix] 坐标修正完成: 修正 {fixed_count}/{total_count} 个景点")
    return trip_plan


def fix_attraction_location(
    attraction: Attraction,
    city: str,
    amap_service
) -> Attraction:
    """
    修正单个景点的坐标

    Args:
        attraction: 景点对象
        city: 城市名
        amap_service: 高德地图服务

    Returns:
        修正后的景点对象
    """
    # 先保留原坐标做参考
    original_location = attraction.location

    # 尝试通过地址或名称获取坐标
    search_keyword = attraction.name
    if attraction.address:
        search_keyword = f"{attraction.name} {attraction.address}"

    try:
        # 先尝试POI搜索
        pois = amap_service.search_poi(search_keyword, city)

        if pois and len(pois) > 0:
            poi = pois[0]

            # 尝试提取坐标
            location_found = False
            lon, lat = None, None

            if 'location' in poi:
                loc_str = poi['location']
                if isinstance(loc_str, str) and ',' in loc_str:
                    lon_str, lat_str = loc_str.split(',')
                    try:
                        lon = float(lon_str)
                        lat = float(lat_str)
                        location_found = True
                    except (ValueError, TypeError):
                        pass

            # 如果没找到location，且有POI ID，尝试获取POI详情
            if not location_found and 'id' in poi:
                poi_id = poi['id']
                detail = amap_service.get_poi_detail(poi_id)
                if 'location' in detail:
                    loc_str = detail['location']
                    if isinstance(loc_str, str) and ',' in loc_str:
                        lon_str, lat_str = loc_str.split(',')
                        try:
                            lon = float(lon_str)
                            lat = float(lat_str)
                            location_found = True
                        except (ValueError, TypeError):
                            pass

            # 如果找到坐标，更新
            if location_found and lon is not None and lat is not None and is_valid_coordinate(lon, lat):
                attraction.location = Location(
                    longitude=lon,
                    latitude=lat
                )
                # 同时更新地址
                if 'address' in poi and poi['address']:
                    attraction.address = poi['address']

                logger.info(f"✅ [LocationFix] {attraction.name}: 使用高德坐标")
                return attraction

        # 如果POI搜索失败，尝试地理编码
        # 先用景点名称+城市
        geo_result = amap_service.geocode(attraction.name, city)
        if geo_result:
            if is_valid_coordinate(geo_result['longitude'], geo_result['latitude']):
                attraction.location = Location(
                    longitude=geo_result['longitude'],
                    latitude=geo_result['latitude']
                )
                logger.info(f"✅ [LocationFix] {attraction.name}: 使用地理编码(名称)")
                return attraction
        # 再用地址
        if attraction.address:
            geo_result = amap_service.geocode(attraction.address, city)
            if geo_result:
                if is_valid_coordinate(geo_result['longitude'], geo_result['latitude']):
                    attraction.location = Location(
                        longitude=geo_result['longitude'],
                        latitude=geo_result['latitude']
                    )
                    logger.info(f"✅ [LocationFix] {attraction.name}: 使用地理编码(地址)")
                    return attraction

    except Exception as e:
        logger.warning(f"⚠️  [LocationFix] {attraction.name}: 获取坐标异常: {e}")

    # 如果所有搜索方法都失败，再尝试使用原坐标（如果有效）
    if original_location and original_location.longitude and original_location.latitude:
        lon = original_location.longitude
        lat = original_location.latitude
        if is_valid_coordinate(lon, lat):
            logger.debug(f"🔄 [LocationFix] {attraction.name}: 搜索失败，使用大模型坐标")
            attraction.location = original_location
            return attraction

    # 如果所有方法都失败，使用城市中心坐标作为后备
    attraction.location = get_city_center_location(city)
    logger.debug(f"🏙️  [LocationFix] {attraction.name}: 使用城市中心坐标")

    return attraction


def get_city_center_location(city: str) -> Location:
    """
    获取城市中心坐标（后备方案）

    Args:
        city: 城市名

    Returns:
        城市中心坐标
    """
    # 主要城市中心坐标
    city_centers = {
        "北京": Location(longitude=116.397428, latitude=39.90923),
        "上海": Location(longitude=121.4737, latitude=31.2304),
        "广州": Location(longitude=113.2644, latitude=23.1291),
        "深圳": Location(longitude=114.0579, latitude=22.5431),
        "杭州": Location(longitude=120.1551, latitude=30.2741),
        "成都": Location(longitude=104.0668, latitude=30.5728),
        "重庆": Location(longitude=106.5516, latitude=29.5630),
        "武汉": Location(longitude=114.3055, latitude=30.5931),
        "西安": Location(longitude=108.9398, latitude=34.3416),
        "南京": Location(longitude=118.7969, latitude=32.0603),
        "苏州": Location(longitude=120.6196, latitude=31.2990),
        "厦门": Location(longitude=118.0894, latitude=24.4798),
        "青岛": Location(longitude=120.3827, latitude=36.0671),
        "大连": Location(longitude=121.6147, latitude=38.9140),
        "昆明": Location(longitude=102.7103, latitude=25.0406),
        "长沙": Location(longitude=112.9388, latitude=28.2282),
        "郑州": Location(longitude=113.6254, latitude=34.7466),
        "济南": Location(longitude=117.1201, latitude=36.6512),
        "沈阳": Location(longitude=123.4315, latitude=41.8045),
        "哈尔滨": Location(longitude=126.5356, latitude=45.8038),
        "长春": Location(longitude=125.3235, latitude=43.8868),
        "石家庄": Location(longitude=114.5149, latitude=38.0423),
        "太原": Location(longitude=112.5489, latitude=37.8570),
        "合肥": Location(longitude=117.2830, latitude=31.8612),
        "福州": Location(longitude=119.2965, latitude=26.0998),
        "南昌": Location(longitude=115.8922, latitude=28.6765),
        "南宁": Location(longitude=108.3200, latitude=22.8240),
        "海口": Location(longitude=110.1999, latitude=20.0442),
        "贵阳": Location(longitude=106.7135, latitude=26.5783),
        "兰州": Location(longitude=103.8236, latitude=36.0580),
        "银川": Location(longitude=106.2784, latitude=38.4684),
        "西宁": Location(longitude=101.7802, latitude=36.6171),
        "乌鲁木齐": Location(longitude=87.6177, latitude=43.7928),
        "拉萨": Location(longitude=91.1375, latitude=29.6525),
        "呼和浩特": Location(longitude=111.6708, latitude=40.8414),
        "无锡": Location(longitude=120.3053, latitude=31.5747),
        "常州": Location(longitude=119.9741, latitude=31.8112),
        "宁波": Location(longitude=121.5494, latitude=29.8683),
        "温州": Location(longitude=120.6994, latitude=27.9942),
    }

    # 精确匹配
    if city in city_centers:
        return city_centers[city]

    # 前缀匹配
    for city_name, loc in city_centers.items():
        if city.startswith(city_name) or city_name.startswith(city):
            return loc

    # 默认使用北京坐标
    logger.warning(f"⚠️  [LocationFix] 未知城市: {city}，使用默认坐标")
    return Location(longitude=116.397428, latitude=39.90923)

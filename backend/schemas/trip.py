"""旅行规划数据模型"""

from typing import List, Optional, Union, Annotated
from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict


# ============ 基础模型（提前定义以解决前向引用） ============

class Location(BaseModel):
    """地理位置"""
    longitude: Annotated[float, Field(..., description="经度")]
    latitude: Annotated[float, Field(..., description="纬度")]


class WeatherInfo(BaseModel):
    """天气信息"""
    date: Annotated[str, Field(..., description="日期 YYYY-MM-DD")]
    day_weather: Annotated[str, Field(default="", description="白天天气")]
    night_weather: Annotated[str, Field(default="", description="夜间天气")]
    day_temp: Annotated[Union[int, str], Field(default=0, description="白天温度")]
    night_temp: Annotated[Union[int, str], Field(default=0, description="夜间温度")]
    wind_direction: Annotated[str, Field(default="", description="风向")]
    wind_power: Annotated[str, Field(default="", description="风力")]

    @field_validator('day_temp', 'night_temp', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        """解析温度,移除°C等单位"""
        if isinstance(v, str):
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


# ============ 地图相关模型 ============

class POISearchRequest(BaseModel):
    """POI搜索请求"""
    keywords: Annotated[str, Field(..., description="搜索关键词")]
    city: Annotated[str, Field(..., description="城市")]
    citylimit: Annotated[bool, Field(default=True, description="是否限制在城市范围内")]


class RouteRequest(BaseModel):
    """路线规划请求"""
    origin_address: Annotated[str, Field(..., description="起点地址")]
    destination_address: Annotated[str, Field(..., description="终点地址")]
    origin_city: Annotated[Optional[str], Field(default=None, description="起点城市")]
    destination_city: Annotated[Optional[str], Field(default=None, description="终点城市")]
    route_type: Annotated[str, Field(default="walking", description="路线类型: walking/driving/transit")]


class POIInfo(BaseModel):
    """POI信息"""
    id: Annotated[str, Field(..., description="POI ID")]
    name: Annotated[str, Field(..., description="名称")]
    type: Annotated[str, Field(..., description="类型")]
    address: Annotated[str, Field(..., description="地址")]
    location: Annotated[Location, Field(..., description="经纬度坐标")]
    tel: Annotated[Optional[str], Field(default=None, description="电话")]


class POISearchResponse(BaseModel):
    """POI搜索响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[List[POIInfo], Field(default=[], description="POI列表")]


class RouteInfo(BaseModel):
    """路线信息"""
    distance: Annotated[float, Field(..., description="距离(米)")]
    duration: Annotated[int, Field(..., description="时间(秒)")]
    route_type: Annotated[str, Field(..., description="路线类型")]
    description: Annotated[str, Field(..., description="路线描述")]


class RouteResponse(BaseModel):
    """路线规划响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[Optional[RouteInfo], Field(default=None, description="路线信息")]


class WeatherResponse(BaseModel):
    """天气查询响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[List[WeatherInfo], Field(default=[], description="天气信息")]


class ErrorResponse(BaseModel):
    """错误响应"""
    success: Annotated[bool, Field(default=False, description="是否成功")]
    message: Annotated[str, Field(..., description="错误消息")]
    error_code: Annotated[Optional[str], Field(default=None, description="错误代码")]


# ============ 旅行规划模型 ============

class TripRequest(BaseModel):
    """旅行规划请求"""
    city: Annotated[str, Field(..., description="目的地城市")]
    start_date: Annotated[str, Field(..., description="开始日期 YYYY-MM-DD")]
    end_date: Annotated[str, Field(..., description="结束日期 YYYY-MM-DD")]
    travel_days: Annotated[int, Field(..., description="旅行天数", ge=1, le=30)]
    transportation: Annotated[str, Field(default="公共交通", description="交通方式")]
    accommodation: Annotated[str, Field(default="经济型酒店", description="住宿偏好")]
    preferences: Annotated[List[str], Field(default=[], description="旅行偏好标签")]
    free_text_input: Annotated[Optional[str], Field(default="", description="额外要求")]

    model_config = ConfigDict(
        json_schema_extra={
                "example": {
                    "city": "北京",
                    "start_date": "2025-06-01",
                    "end_date": "2025-06-03",
                    "travel_days": 3,
                    "transportation": "公共交通",
                    "accommodation": "经济型酒店",
                    "preferences": ["历史文化", "美食"],
                    "free_text_input": "希望多安排一些博物馆"
                }
            }
        )


class Attraction(BaseModel):
    """景点信息"""
    name: Annotated[str, Field(..., description="景点名称")]
    address: Annotated[str, Field(..., description="地址")]
    location: Annotated[Optional[Location], Field(default=None, description="经纬度坐标")]
    visit_duration: Annotated[int, Field(default=120, description="建议游览时间(分钟)")]
    description: Annotated[str, Field(default="", description="景点描述")]
    category: Annotated[Optional[str], Field(default="景点", description="景点类别")]
    rating: Annotated[Optional[float], Field(default=None, description="评分")]
    ticket_price: Annotated[int, Field(default=0, description="门票价格(元)")]


class Meal(BaseModel):
    """餐饮信息"""
    type: Annotated[str, Field(..., description="餐饮类型: breakfast/lunch/dinner/snack")]
    name: Annotated[str, Field(..., description="餐饮名称")]
    description: Annotated[Optional[str], Field(default=None, description="描述")]
    estimated_cost: Annotated[int, Field(default=0, description="预估费用(元)")]


class Hotel(BaseModel):
    """酒店信息"""
    name: Annotated[str, Field(..., description="酒店名称")]
    address: Annotated[str, Field(default="", description="酒店地址")]
    location: Annotated[Optional[Location], Field(default=None, description="酒店位置")]
    price_range: Annotated[str, Field(default="", description="价格范围")]
    rating: Annotated[str, Field(default="", description="评分")]
    distance: Annotated[str, Field(default="", description="距离景点距离")]
    type: Annotated[str, Field(default="", description="酒店类型")]
    estimated_cost: Annotated[int, Field(default=0, description="预估费用(元/晚)")]


class DayPlan(BaseModel):
    """单日行程"""
    date: Annotated[str, Field(..., description="日期 YYYY-MM-DD")]
    day_index: Annotated[int, Field(..., description="第几天(从0开始)")]
    description: Annotated[str, Field(..., description="当日行程描述")]
    transportation: Annotated[str, Field(..., description="交通方式")]
    accommodation: Annotated[str, Field(..., description="住宿")]
    hotel: Annotated[Optional[Hotel], Field(default=None, description="推荐酒店")]
    attractions: Annotated[List[Attraction], Field(default=[], description="景点列表")]
    meals: Annotated[List[Meal], Field(default=[], description="餐饮列表")]


class Budget(BaseModel):
    """预算信息"""
    total_attractions: Annotated[int, Field(default=0, description="景点门票总费用")]
    total_hotels: Annotated[int, Field(default=0, description="酒店总费用")]
    total_meals: Annotated[int, Field(default=0, description="餐饮总费用")]
    total_transportation: Annotated[int, Field(default=0, description="交通总费用")]
    total: Annotated[int, Field(default=0, description="总费用")]


class TripPlan(BaseModel):
    """旅行计划"""
    city: Annotated[str, Field(..., description="目的地城市")]
    start_date: Annotated[str, Field(..., description="开始日期")]
    end_date: Annotated[str, Field(..., description="结束日期")]
    days: Annotated[List[DayPlan], Field(..., description="每日行程")]
    weather_info: Annotated[List[WeatherInfo], Field(default=[], description="天气信息")]
    overall_suggestions: Annotated[str, Field(default="", description="总体建议")]
    budget: Annotated[Optional[Budget], Field(default=None, description="预算信息")]

    # ========== 新增：风险识别结果 ==========
    identified_risks: Annotated[List[dict], Field(default=[], description="识别到的风险列表")]
    risk_summary: Annotated[Optional[dict], Field(default=None, description="风险汇总（高/中/低风险数量）")]


class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[Optional[TripPlan], Field(default=None, description="旅行计划数据")]


class TripPlanRecordResponse(BaseModel):
    """旅行计划记录响应"""
    id: Annotated[int, Field(..., description="记录ID")]
    user_id: Annotated[int, Field(..., description="用户ID")]
    title: Annotated[str, Field(..., description="计划标题")]
    city: Annotated[str, Field(..., description="目的地城市")]
    start_date: Annotated[str, Field(..., description="开始日期")]
    end_date: Annotated[str, Field(..., description="结束日期")]
    travel_days: Annotated[int, Field(..., description="旅行天数")]
    plan_data: Annotated[dict, Field(..., description="计划数据")]

    @field_serializer('id', 'user_id')
    def serialize_id(self, value: int) -> str:
        return str(value)

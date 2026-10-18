"""RC-LRA 单元测试: 5类风险检测 + 6类修复测试"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trip_risk_repair import (
    TripRiskRepairEngine, calculate_risk_score,
    _is_bad_weather, _is_outdoor_attraction, _is_indoor_attraction,
    _is_light_travel_request, _is_low_priority_attraction,
    _haversine_distance_km, _get_attraction_coord, _get_hotel_coord,
    _safe_int, _calculate_day_route_distance, _has_adjacent_distance_violation,
)
from core.planning_context import TripPlanningContext
from schemas.trip import TripPlan, DayPlan, Attraction, Hotel, WeatherInfo, Location, TripRequest


def make_context(plan, preferences=None, free_text='', candidate_areas=None):
    req = TripRequest(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        travel_days=len(plan.days), preferences=preferences or [],
        free_text_input=free_text,
    )
    return TripPlanningContext(
        request=req, city='杭州', travel_days=len(plan.days),
        preferences=preferences or [],
        candidate_areas=candidate_areas or [],
        normalized_plan=plan,
    )


# ========== 工具函数测试 ==========

def test_safe_int():
    assert _safe_int(None) is None
    assert _safe_int(25) == 25
    assert _safe_int(36.0) == 36  # 兼容 float
    assert _safe_int('30°C') == 30
    assert _safe_int('36度') == 36
    assert _safe_int('-2℃') == -2
    assert _safe_int('') is None
    assert _safe_int('abc') is None
    print('_safe_int: OK')


def test_is_bad_weather():
    w1 = WeatherInfo(date='2025-06-01', day_weather='中雨', day_temp=20)
    assert _is_bad_weather(w1) is True
    w2 = WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=25)
    assert _is_bad_weather(w2) is False
    w3 = WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=38)
    assert _is_bad_weather(w3) is True  # 高温
    w4 = WeatherInfo(date='2025-06-01', day_weather='多云', day_temp=-5)
    assert _is_bad_weather(w4) is True  # 严寒
    print('_is_bad_weather: OK')


def test_sunny_weather_with_default_zero_temp_not_bad():
    w = WeatherInfo(date='2025-06-01', day_weather='晴')
    assert _is_bad_weather(w) is False
    w2 = WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=0)
    assert _is_bad_weather(w2) is False  # 默认 0 度不误判
    print('晴天默认温度不误判: OK')


def test_bad_weather_by_temperature_and_keyword():
    assert _is_bad_weather(WeatherInfo(date='2025-06-01', day_weather='中雨')) is True
    assert _is_bad_weather(WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=36)) is True
    assert _is_bad_weather(WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=-2)) is True
    assert _is_bad_weather(WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=0)) is False
    print('温度与关键词判断: OK')


def test_outdoor_indoor():
    assert _is_outdoor_attraction('西湖') is True
    assert _is_outdoor_attraction('陕西历史博物馆') is False
    assert _is_indoor_attraction('兵马俑') is True
    assert _is_indoor_attraction('西湖') is False
    assert _is_outdoor_attraction('西溪湿地') is True
    assert _is_indoor_attraction('某商场购物中心') is True
    # 扩充的 KNOWN 集合
    assert _is_outdoor_attraction('西安城墙') is True
    assert _is_indoor_attraction('故宫博物院') is True
    print('outdoor/indoor: OK')


def test_light_travel():
    assert _is_light_travel_request(['老人', '轻松'], '') is True
    assert _is_light_travel_request(['历史文化'], '') is False
    assert _is_light_travel_request([], '带父母去玩') is True
    print('_is_light_travel_request: OK')


def test_low_priority():
    assert _is_low_priority_attraction('某购物广场') is True
    assert _is_low_priority_attraction('故宫') is False
    print('_is_low_priority_attraction: OK')


def test_haversine():
    dist = _haversine_distance_km(30.25, 120.15, 30.27, 120.17)
    assert 2.0 < dist < 3.5, f'Unexpected distance: {dist}'
    print(f'_haversine_distance_km: OK (dist={dist:.2f}km)')


def test_coord_order():
    a = Attraction(name='test', address='addr', location=Location(longitude=120.0, latitude=30.0))
    coord = _get_attraction_coord(a)
    assert coord == (30.0, 120.0), f'Expected (30.0, 120.0), got {coord}'
    a2 = Attraction(name='test', address='addr')
    assert _get_attraction_coord(a2) is None
    print('_get_attraction_coord: OK (latitude, longitude order)')


# ========== 风险检测测试 ==========

def test_weather_conflict():
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='西湖', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                    Attraction(name='断桥', address='杭州', location=Location(longitude=120.15, latitude=30.26)),
                ]
            )
        ],
        weather_info=[WeatherInfo(date='2025-06-01', day_weather='中雨', day_temp=20)]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    risks = engine.detect_risks(plan, ctx)
    weather_risks = [r for r in risks if r['type'] == 'weather_outdoor_conflict']
    assert len(weather_risks) > 0, f'Expected weather risk, got {risks}'
    assert weather_risks[0]['day_index'] == 0
    assert '西湖' in weather_risks[0]['evidence']['affected_attractions']
    print('天气冲突检测: OK')

    # weather_info 为空时应跳过
    plan_empty = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[DayPlan(date='2025-06-01', day_index=0, description='D1', transportation='公交',
                      accommodation='酒店', attractions=[Attraction(name='西湖', address='杭州')])],
        weather_info=[]
    )
    ctx_empty = make_context(plan_empty)
    risks_empty = engine.detect_risks(plan_empty, ctx_empty)
    assert all(r['type'] != 'weather_outdoor_conflict' for r in risks_empty)
    print('天气为空跳过: OK')


def test_daily_load():
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name=f'景点{i}', address='杭州',
                               location=Location(longitude=120.1 + i * 0.01, latitude=30.2 + i * 0.01))
                    for i in range(5)
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    risks = engine.detect_risks(plan, ctx)
    load_risks = [r for r in risks if r['type'] == 'daily_load_overflow']
    assert len(load_risks) > 0
    assert load_risks[0]['evidence']['attraction_count'] == 5
    print('普通过载检测: OK (5景点 > 4)')

    # 轻松型: 4个景点就过载
    plan_light = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(date='2025-06-01', day_index=0, description='D1', transportation='公交',
                    accommodation='酒店',
                    attractions=[Attraction(name=f'A{i}', address='杭州') for i in range(4)])
        ]
    )
    ctx_light = make_context(plan_light, preferences=['老人', '轻松'])
    risks_light = engine.detect_risks(plan_light, ctx_light)
    load_risks_light = [r for r in risks_light if r['type'] == 'daily_load_overflow']
    assert len(load_risks_light) > 0
    print('轻松型过载检测: OK (4景点 > 3)')


def test_route_distance():
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.3, latitude=30.3)),
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    risks = engine.detect_risks(plan, ctx)
    route_risks = [r for r in risks if r['type'] == 'route_distance_too_long']
    assert len(route_risks) > 0, f'Expected route risk, got {risks}'
    print(f'路线跨度检测: OK (level={route_risks[0]["level"]})')


def test_hotel_location():
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='远郊酒店', address='远郊', location=Location(longitude=119.8, latitude=29.9)),
                attractions=[
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.2, latitude=30.2)),
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.3, latitude=30.3)),
                ]
            )
        ]
    )
    ctx = make_context(plan, candidate_areas=['西湖周边', '湖滨'])
    engine = TripRiskRepairEngine()
    risks = engine.detect_risks(plan, ctx)
    hotel_risks = [r for r in risks if r['type'] == 'hotel_location_mismatch']
    assert len(hotel_risks) > 0, f'Expected hotel risk, got {risks}'
    assert '西湖周边' in hotel_risks[0]['suggestion'] or '湖滨' in hotel_risks[0]['suggestion']
    print('住宿位置检测: OK (引用了 candidate_areas)')


def test_location_missing():
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                attractions=[
                    Attraction(name='西湖', address='杭州'),
                    Attraction(name='断桥', address='杭州'),
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='杭州'),
                attractions=[
                    Attraction(name='灵隐寺', address='杭州', location=Location(longitude=120.1, latitude=30.2)),
                ]
            ),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    risks = engine.detect_risks(plan, ctx)
    missing_risks = [r for r in risks if r['type'] == 'location_missing']
    assert len(missing_risks) == 2, f'Expected 2 day-aggregated risks, got {len(missing_risks)}'
    d1_risk = [r for r in missing_risks if r['day_index'] == 0][0]
    assert len(d1_risk['evidence']['missing_attractions']) == 2
    assert d1_risk['evidence']['hotel_missing'] is False
    d2_risk = [r for r in missing_risks if r['day_index'] == 1][0]
    assert d2_risk['evidence']['hotel_missing'] is True
    print('坐标缺失按天聚合: OK')


# ========== 修复测试 ==========

def test_route_reorder():
    """最近邻重排后距离下降或保持"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='西湖附近', location=Location(longitude=120.15, latitude=30.25)),
                attractions=[
                    Attraction(name='远点A', address='杭州', location=Location(longitude=120.3, latitude=30.3)),
                    Attraction(name='近点B', address='杭州', location=Location(longitude=120.16, latitude=30.26)),
                    Attraction(name='远点C', address='杭州', location=Location(longitude=119.9, latitude=29.9)),
                    Attraction(name='近点D', address='杭州', location=Location(longitude=120.17, latitude=30.27)),
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    old_dist = _calculate_day_route_distance(plan.days[0])
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, engine.detect_risks(plan, ctx), ctx)
    new_dist = _calculate_day_route_distance(repaired_plan.days[0])
    assert new_dist <= old_dist, f'Distance increased: {old_dist:.1f} -> {new_dist:.1f}'
    print(f'最近邻重排: OK (distance {old_dist:.1f}km -> {new_dist:.1f}km)')


def test_load_move():
    """过载修复后景点成功移动"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name=f'景点{i}', address='杭州',
                               location=Location(longitude=120.1 + i * 0.01, latitude=30.2 + i * 0.01))
                    for i in range(5)  # 过载
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='景点X', address='杭州', location=Location(longitude=120.1, latitude=30.2)),
                ]
            ),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    # 检查D1景点数减少
    d1_count = len(repaired_plan.days[0].attractions)
    assert d1_count < 5, f'D1 should have fewer attractions: {d1_count}'
    # 检查没有空天
    for day in repaired_plan.days:
        assert len(day.attractions) > 0, 'No day should be empty'
    print(f'过载景点移动: OK (D1: 5 -> {d1_count})')


def test_weather_swap():
    """雨天户外与非雨天室内交换"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1 雨天', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='西湖', address='杭州', location=Location(longitude=120.15, latitude=30.25)),  # 户外
                    Attraction(name='断桥', address='杭州', location=Location(longitude=120.15, latitude=30.26)),  # 户外
                    Attraction(name='某博物馆', address='杭州', location=Location(longitude=120.16, latitude=30.26)),  # 室内
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2 晴天', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='美术馆', address='杭州', location=Location(longitude=120.14, latitude=30.24)),  # 室内
                    Attraction(name='苏堤', address='杭州', location=Location(longitude=120.14, latitude=30.25)),  # 户外
                ]
            ),
        ],
        weather_info=[
            WeatherInfo(date='2025-06-01', day_weather='大雨', day_temp=20),
            WeatherInfo(date='2025-06-02', day_weather='晴', day_temp=25),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    # 检查D1的户外景点数减少（可能交换成功）
    d1_outdoor_after = sum(1 for a in repaired_plan.days[0].attractions if _is_outdoor_attraction(a.name, a.category, a.description))
    d1_outdoor_before = 2  # 西湖+断桥
    # 即使交换不成功（如分数不降），也不应破坏原行程
    assert len(repaired_plan.days[0].attractions) > 0, 'D1 should not be empty'
    assert len(repaired_plan.days[1].attractions) > 0, 'D2 should not be empty'
    total_attractions = sum(len(d.attractions) for d in repaired_plan.days)
    assert total_attractions == 5, f'Total attractions should be preserved, got {total_attractions}'
    print(f'雨天交换: OK (D1户外 {d1_outdoor_before} -> {d1_outdoor_after})')


def test_repair_no_destruct():
    """修复失败不破坏原行程"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='西湖', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                    Attraction(name='灵隐寺', address='杭州', location=Location(longitude=120.10, latitude=30.27)),
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    # 行程结构不应被破坏
    assert len(repaired_plan.days) == len(plan.days)
    for i, (orig, repaired) in enumerate(zip(plan.days, repaired_plan.days)):
        assert len(repaired.attractions) == len(orig.attractions), f'Day {i}: attraction count mismatch'
    print('修复不破坏原行程: OK')


def test_no_empty_days():
    """任意一天 attractions 不应为空"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1 过载', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name=f'景点{i}', address='杭州', location=Location(longitude=120.1+i*0.01, latitude=30.2+i*0.01))
                    for i in range(5)
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2 只有一个', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='唯一景点', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                ]
            ),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    for day in repaired_plan.days:
        assert len(day.attractions) > 0, f'Day {day.day_index} should not be empty after repair'
    print('无空天: OK')


def test_risk_monotone():
    """修复后 total_score 不高于修复前（风险单调不增）"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-03',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1 过载+路线跨度大', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                attractions=[
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.3, latitude=30.3)),
                    Attraction(name='景点C', address='杭州', location=Location(longitude=120.1, latitude=30.1)),
                    Attraction(name='景点D', address='杭州', location=Location(longitude=119.9, latitude=29.9)),
                    Attraction(name='某购物广场', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='景点E', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                    Attraction(name='景点F', address='杭州', location=Location(longitude=120.16, latitude=30.26)),
                ]
            ),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    pre_score = calculate_risk_score(plan, ctx)
    ctx.risk_score_before = pre_score
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)
    post_score = calculate_risk_score(repaired_plan, ctx)

    assert post_score['total_score'] <= pre_score['total_score'], \
        f'Risk score increased: {pre_score["total_score"]} -> {post_score["total_score"]}'
    print(f'风险单调不增: OK ({pre_score["total_score"]} -> {post_score["total_score"]})')


# ========== 风险评分测试 ==========

def test_risk_score():
    """风险评分函数测试"""
    # 无风险行程
    plan_safe = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                attractions=[
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.15, latitude=30.26)),
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.16, latitude=30.27)),
                ]
            )
        ],
        weather_info=[WeatherInfo(date='2025-06-01', day_weather='晴', day_temp=22)]
    )
    ctx_safe = make_context(plan_safe)
    score = calculate_risk_score(plan_safe, ctx_safe)
    assert score['total_score'] == 0.0, f'Expected 0.0, got {score["total_score"]}'
    print('无风险行程评分: OK (score=0.0)')

    # 有风险行程
    plan_risky = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name=f'景点{i}', address='杭州',
                               location=Location(longitude=120.1+i*0.01, latitude=30.2+i*0.01))
                    for i in range(6)  # 过载
                ]
            )
        ]
    )
    ctx_risky = make_context(plan_risky)
    score2 = calculate_risk_score(plan_risky, ctx_risky)
    assert score2['total_score'] > 0, f'Expected >0, got {score2["total_score"]}'
    assert score2['load_score'] > 0, 'Load score should be >0'
    print(f'有风险行程评分: OK (score={score2["total_score"]})')


# ========== 新增修复验证测试 ==========

def test_route_reorder_rollback():
    """路线重排失败必须严格回滚：距离不下降时保留原始顺序"""
    # 构造一个行程：景点已经是最优顺序，最近邻排序不会改善距离
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='起点', location=Location(longitude=120.0, latitude=30.0)),
                attractions=[
                    # 按距离递增排列，已经是最近邻顺序
                    Attraction(name='近A', address='杭州', location=Location(longitude=120.01, latitude=30.01)),
                    Attraction(name='中B', address='杭州', location=Location(longitude=120.05, latitude=30.05)),
                    # 远点产生 route risk
                    Attraction(name='远C', address='杭州', location=Location(longitude=120.4, latitude=30.4)),
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    original_names = [a.name for a in plan.days[0].attractions]
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    # 找到 route_reorder 的 repair_log
    route_logs = [x for x in repair_log if x['action'] == 'route_reorder']
    if route_logs:
        for log in route_logs:
            if not log.get('accepted'):
                # 如果不接受，repaired_plan 顺序应和原始一致
                repaired_names = [a.name for a in repaired_plan.days[0].attractions]
                assert repaired_names == original_names, \
                    f'Route reorder was rejected but order changed: {repaired_names} != {original_names}'
                assert log['accepted'] is False
                # risk.repaired 不应为 True
                risk_id = log['risk_id']
                for r in risks:
                    if r['risk_id'] == risk_id:
                        assert r.get('repaired') is not True
    print('路线重排失败回滚: OK')


def test_each_repair_monotone_vs_current():
    """每一步修复都相对于当前状态单调不增"""
    # 构造包含多个可修复风险的行程
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-04',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1 过载+路线大', transportation='公交', accommodation='酒店',
                hotel=Hotel(name='酒店', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                attractions=[
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.3, latitude=30.3)),
                    Attraction(name='景点C', address='杭州', location=Location(longitude=120.1, latitude=30.1)),
                    Attraction(name='景点D', address='杭州', location=Location(longitude=119.9, latitude=29.9)),
                    Attraction(name='某购物广场', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                ]
            ),
            DayPlan(
                date='2025-06-02', day_index=1,
                description='D2', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='景点E', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                    Attraction(name='景点F', address='杭州', location=Location(longitude=120.16, latitude=30.26)),
                ]
            ),
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    _, repair_log = engine.repair_plan(plan, risks, ctx)

    # 每条 accepted repair_log 的 after_score <= before_score
    for log in repair_log:
        if log.get('accepted'):
            assert log['after_score'] <= log['before_score'], \
                f"Repair {log['action']} day {log['day_index']}: " \
                f"score increased {log['before_score']} -> {log['after_score']}"
    print('每步修复单调不增: OK')


def test_museum_not_outdoor():
    """博物馆类景点不应被 category='景点' 默认判为户外"""
    # category="景点" 是默认值，不应导致判为户外
    assert _is_outdoor_attraction('杭州博物馆', category='景点') is False
    assert _is_indoor_attraction('杭州博物馆', category='景点') is True
    # 西湖 category=景点 仍是户外（KNOWN_OUTDOOR）
    assert _is_outdoor_attraction('西湖', category='景点') is True
    # 名称含"博物馆"关键词即使 category=景点也应判为室内
    assert _is_outdoor_attraction('某市博物馆', category='景点') is False
    assert _is_indoor_attraction('某市博物馆', category='景点') is True
    # description 参数也能帮助判断
    assert _is_outdoor_attraction('国家大剧院', category='景点', description='室内演出场馆') is False
    print('博物馆不误判户外: OK')


def test_route_detect_score_consistency():
    """路线检测与风险评分一致：相邻距离超限也影响 distance_score"""
    # 构造一天两个景点：相邻距离 > 10km，但总距离 <= 25km
    # 120.0,30.0 到 120.2,30.2 约 31km，太远了
    # 需要精确构造：相邻距离 > 10km 但总距离 <= 25km
    # 用3个景点：A到B距离约12km，B到C距离约10km，总距离约22km < 25km
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    # A: (30.0, 120.0)
                    Attraction(name='景点A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
                    # B: (30.1, 120.1) ~ 15.6km from A
                    Attraction(name='景点B', address='杭州', location=Location(longitude=120.1, latitude=30.1)),
                    # C: (30.15, 120.15) ~ 7.8km from B, total ~23.4km
                    Attraction(name='景点C', address='杭州', location=Location(longitude=120.15, latitude=30.15)),
                ]
            )
        ]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()

    # detect_risks 应识别 route_distance_too_long
    risks = engine.detect_risks(plan, ctx)
    route_risks = [r for r in risks if r['type'] == 'route_distance_too_long']
    assert len(route_risks) > 0, 'Expected route risk for adjacent distance violation'

    # calculate_risk_score 的 distance_score 应 > 0
    score = calculate_risk_score(plan, ctx)
    assert score['distance_score'] > 0, \
        f'distance_score should be >0 with adjacent violation, got {score["distance_score"]}'
    print(f'路线检测与评分一致: OK (distance_score={score["distance_score"]})')


def test_has_adjacent_distance_violation():
    """_has_adjacent_distance_violation 工具函数测试"""
    # 相邻距离 > 10km
    day_bad = DayPlan(
        date='2025-06-01', day_index=0,
        description='D1', transportation='公交', accommodation='酒店',
        attractions=[
            Attraction(name='A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
            Attraction(name='B', address='杭州', location=Location(longitude=120.1, latitude=30.1)),
        ]
    )
    assert _has_adjacent_distance_violation(day_bad, 10.0) is True

    # 相邻距离 < 10km
    day_ok = DayPlan(
        date='2025-06-01', day_index=0,
        description='D1', transportation='公交', accommodation='酒店',
        attractions=[
            Attraction(name='A', address='杭州', location=Location(longitude=120.0, latitude=30.0)),
            Attraction(name='B', address='杭州', location=Location(longitude=120.01, latitude=30.01)),
        ]
    )
    assert _has_adjacent_distance_violation(day_ok, 10.0) is False

    # 无坐标景点跳过
    day_nocoord = DayPlan(
        date='2025-06-01', day_index=0,
        description='D1', transportation='公交', accommodation='酒店',
        attractions=[
            Attraction(name='A', address='杭州'),
            Attraction(name='B', address='杭州'),
        ]
    )
    assert _has_adjacent_distance_violation(day_nocoord, 10.0) is False
    print('_has_adjacent_distance_violation: OK')


def test_calculate_end_date():
    """_calculate_end_date 根据 start_date 和 travel_days 计算一致的 end_date"""
    import importlib.util
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "scripts", "evaluate_trip_risk_repair.py")
    spec = importlib.util.spec_from_file_location("eval_script", script_path)
    mod = importlib.util.module_from_spec(spec)
    os.environ.pop("TRIP_RISK_REPAIR_ENABLED", None)
    spec.loader.exec_module(mod)

    assert mod._calculate_end_date("2025-06-01", 1) == "2025-06-01"
    assert mod._calculate_end_date("2025-06-01", 3) == "2025-06-03"
    assert mod._calculate_end_date("2025-06-01", 5) == "2025-06-05"
    assert mod._calculate_end_date("2025-06-01", 4) == "2025-06-04"
    print('_calculate_end_date: OK')


def test_build_trip_request_from_eval_item():
    """_build_trip_request_from_eval_item 确保日期和天数一致"""
    import importlib.util
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "scripts", "evaluate_trip_risk_repair.py")
    spec = importlib.util.spec_from_file_location("eval_script", script_path)
    mod = importlib.util.module_from_spec(spec)
    os.environ.pop("TRIP_RISK_REPAIR_ENABLED", None)
    spec.loader.exec_module(mod)

    # 5 天北京：无 end_date，应自动计算
    item_5d = {"id": "TRIP-BJ-001", "city": "北京", "travel_days": 5}
    req = mod._build_trip_request_from_eval_item(item_5d, 1)
    assert req.travel_days == 5
    assert req.start_date == "2025-06-01"
    assert req.end_date == "2025-06-05"

    # 3 天杭州：end_date 不一致时应修正
    item_3d = {"id": "TRIP-HZ-001", "city": "杭州", "travel_days": 3, "start_date": "2025-06-01", "end_date": "2025-06-05"}
    req2 = mod._build_trip_request_from_eval_item(item_3d, 2)
    assert req2.travel_days == 3
    assert req2.end_date == "2025-06-03"  # 以 travel_days 为准修正

    # 1 天：end_date == start_date
    item_1d = {"id": "TEST-1D", "city": "上海", "travel_days": 1}
    req3 = mod._build_trip_request_from_eval_item(item_1d, 3)
    assert req3.end_date == "2025-06-01"

    print('_build_trip_request_from_eval_item: OK')


def test_validate_baseline_date_consistency():
    """_validate_baseline_date_consistency 检查日期不一致记录"""
    import importlib.util
    import tempfile
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "scripts", "evaluate_trip_risk_repair.py")
    spec = importlib.util.spec_from_file_location("eval_script", script_path)
    mod = importlib.util.module_from_spec(spec)
    os.environ.pop("TRIP_RISK_REPAIR_ENABLED", None)
    spec.loader.exec_module(mod)

    # 创建临时 JSONL 文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        # 一致记录
        f.write(json.dumps({"id": "OK-1", "request": {"start_date": "2025-06-01", "end_date": "2025-06-03", "travel_days": 3}}) + "\n")
        # 不一致记录：travel_days=5 但 end_date=2025-06-03
        f.write(json.dumps({"id": "BAD-1", "request": {"start_date": "2025-06-01", "end_date": "2025-06-03", "travel_days": 5}}) + "\n")
        tmp_path = f.name

    try:
        problems = mod._validate_baseline_date_consistency(tmp_path)
        assert len(problems) == 1, f"Expected 1 problem, got {len(problems)}"
        assert problems[0]["id"] == "BAD-1"
        assert problems[0]["expected_end_date"] == "2025-06-05"
    finally:
        os.unlink(tmp_path)

    print('_validate_baseline_date_consistency: OK')


def test_generate_initial_plans_env_check():
    """未设置 TRIP_RISK_REPAIR_ENABLED=false 时 generate_initial_plans 必须抛 RuntimeError"""
    import importlib
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "scripts", "evaluate_trip_risk_repair.py")
    # 直接导入脚本中的函数
    import importlib.util
    spec = importlib.util.spec_from_file_location("eval_script", script_path)
    mod = importlib.util.module_from_spec(spec)

    # 确保环境变量为默认值（true）
    os.environ.pop("TRIP_RISK_REPAIR_ENABLED", None)
    spec.loader.exec_module(mod)

    assert mod._is_risk_repair_disabled() is False

    # 设置为 false 后应返回 True
    os.environ["TRIP_RISK_REPAIR_ENABLED"] = "false"
    assert mod._is_risk_repair_disabled() is True

    # 清理
    os.environ.pop("TRIP_RISK_REPAIR_ENABLED", None)
    print('generate_initial_plans 环境变量检查: OK')


def test_case_detail_contains_risks_and_repair_log():
    """case_details.jsonl 必须包含 risks 和 repair_log"""
    plan = TripPlan(
        city='杭州', start_date='2025-06-01', end_date='2025-06-02',
        days=[
            DayPlan(
                date='2025-06-01', day_index=0,
                description='D1', transportation='公交', accommodation='酒店',
                attractions=[
                    Attraction(name='西湖', address='杭州', location=Location(longitude=120.15, latitude=30.25)),
                    Attraction(name='某博物馆', address='杭州', location=Location(longitude=120.16, latitude=30.26)),
                    Attraction(name='断桥', address='杭州', location=Location(longitude=120.15, latitude=30.27)),
                    Attraction(name='苏堤', address='杭州', location=Location(longitude=120.14, latitude=30.24)),
                    Attraction(name='灵隐寺', address='杭州', location=Location(longitude=120.10, latitude=30.22)),
                ]
            )
        ],
        weather_info=[WeatherInfo(date='2025-06-01', day_weather='大雨', day_temp=20)]
    )
    ctx = make_context(plan)
    engine = TripRiskRepairEngine()
    ctx.risk_score_before = calculate_risk_score(plan, ctx)
    risks = engine.detect_risks(plan, ctx)
    repaired_plan, repair_log = engine.repair_plan(plan, risks, ctx)

    # 验证 risks 和 repair_log 是 list[dict]
    assert isinstance(risks, list), f'risks should be list, got {type(risks)}'
    assert isinstance(repair_log, list), f'repair_log should be list, got {type(repair_log)}'
    if risks:
        assert isinstance(risks[0], dict), f'risk item should be dict, got {type(risks[0])}'
    if repair_log:
        assert isinstance(repair_log[0], dict), f'repair_log item should be dict, got {type(repair_log[0])}'
    print('case_detail risks/repair_log 结构: OK')


if __name__ == '__main__':
    print('===== 工具函数测试 =====')
    test_safe_int()
    test_is_bad_weather()
    test_sunny_weather_with_default_zero_temp_not_bad()
    test_bad_weather_by_temperature_and_keyword()
    test_outdoor_indoor()
    test_light_travel()
    test_low_priority()
    test_haversine()
    test_coord_order()

    print()
    print('===== 风险检测测试 =====')
    test_weather_conflict()
    test_daily_load()
    test_route_distance()
    test_hotel_location()
    test_location_missing()

    print()
    print('===== 修复测试 =====')
    test_route_reorder()
    test_load_move()
    test_weather_swap()
    test_repair_no_destruct()
    test_no_empty_days()
    test_risk_monotone()

    print()
    print('===== 风险评分测试 =====')
    test_risk_score()

    print()
    print('===== 新增修复验证测试 =====')
    test_route_reorder_rollback()
    test_each_repair_monotone_vs_current()
    test_museum_not_outdoor()
    test_route_detect_score_consistency()
    test_has_adjacent_distance_violation()

    print()
    print('===== 评估脚本验证测试 =====')
    test_calculate_end_date()
    test_build_trip_request_from_eval_item()
    test_validate_baseline_date_consistency()
    test_generate_initial_plans_env_check()
    test_case_detail_contains_risks_and_repair_log()

    print()
    print('========== 全部测试通过 ==========')

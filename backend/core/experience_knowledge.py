"""
经验知识抽取与风险识别模块 - 瘦身务实版

这是毕业设计的核心创新体现：
1. 经验知识抽取：从攻略中提取可执行的决策知识
2. 风险识别：主动识别行程中的潜在问题
3. 行程修正：基于经验知识修正方案

去掉了虚的"反思"、"图谱"、"消除"等大词，
重点做"能落地、能验证、能自圆其说"的事。
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from core.logger import logger


class RiskSeverity(str, Enum):
    """风险等级"""
    HIGH = "high"      # 🔴 高风险：必须修正
    MEDIUM = "medium"  # 🟡 中风险：建议修正
    LOW = "low"        # 🟢 低风险：提醒即可


class RiskType(str, Enum):
    """风险类型"""
    TIME_CONFLICT = "time_conflict"        # 时间冲突（闭馆等）
    CONGESTION = "congestion"              # 人流风险
    APPOINTMENT = "appointment"            # 预约要求
    PHYSICAL_STRAIN = "physical_strain"    # 体力负担
    WEATHER_MISMATCH = "weather_mismatch"  # 天气不适配
    EXPERIENCE_CONFLICT = "experience_conflict"  # 经验冲突


class ExperienceKnowledgeManager:
    """
    经验知识管理器

    负责：
    1. 从攻略中抽取经验知识
    2. 构建经验知识库
    3. 提供知识查询接口
    """

    def __init__(self):
        self.knowledge_base = self._build_default_knowledge_base()
        logger.info("[ExperienceKnowledge] 经验知识管理器初始化完成")

    def _build_default_knowledge_base(self) -> Dict[str, Any]:
        """
        构建默认经验知识库（演示用）

        知识可信度控制原则：
        1. 官方攻略优先（is_official=True）
        2. 多篇攻略一致时置信度更高
        3. 高互动内容优先（view_count/like_count高）
        4. 时间较新的攻略优先
        5. 对"主观建议"和"客观约束"区分存储
        """
        return {
            "杭州": {
                "knowledge_credibility": {
                    "source_count": 5,
                    "last_updated": "2024-05-01",
                    "average_confidence": 0.85
                },
                "attractions": {
                    "西湖": {
                        "best_time": "08:00-10:00",
                        "avoid_on": ["周末", "节假日"],
                        "tips": ["建议早上去，人少景美", "周末人流量大"],
                        "common_mistakes": ["不要在西湖边吃饭", "周末停车困难"],
                        "congestion_risk": True,
                        "ticket_price": "0元",
                        # 知识可信度信息
                        "confidence": 0.92,
                        "source_type": "objective",  # objective（客观）/ subjective（主观）
                        "agree_count": 4,  # 4篇攻略一致
                        "last_verified": "2024-04-28"
                    },
                    "灵隐寺": {
                        "best_time": "07:30-09:00",
                        "closed_on": ["周一"],
                        "avoid_on": ["周末", "节假日"],
                        "tips": ["需要提前在公众号预约", "建议早上去"],
                        "common_mistakes": ["只买飞来峰门票进不了灵隐寺"],
                        "appointment_required": True,
                        "ticket_price": "飞来峰45元+灵隐寺30元",
                        # 知识可信度信息
                        "confidence": 0.95,
                        "source_type": "objective",
                        "agree_count": 5,
                        "last_verified": "2024-04-30",
                        "is_official": True  # 来自景区官方信息
                    },
                    "西溪湿地": {
                        "best_time": "全天",
                        "avoid_on": [],
                        "tips": ["人少清净，适合周末替代西湖"],
                        "common_mistakes": [],
                        "congestion_risk": False,
                        "ticket_price": "80元",
                        # 知识可信度信息
                        "confidence": 0.78,
                        "source_type": "subjective",  # 主观建议
                        "agree_count": 3,
                        "last_verified": "2024-04-15"
                    },
                    "宋城": {
                        "best_time": "下午+晚上",
                        "avoid_on": [],
                        "tips": ["建议看《宋城千古情》演出"],
                        "common_mistakes": [],
                        "ticket_price": "310元",
                        # 知识可信度信息
                        "confidence": 0.82,
                        "source_type": "subjective",
                        "agree_count": 3,
                        "last_verified": "2024-04-20"
                    }
                },
                "itinerary_patterns": [
                    {
                        "days": 3,
                        "pattern": "D1: 西湖周边 → D2: 灵隐寺+宋城 → D3: 西溪湿地",
                        "suitable_for": ["情侣", "家庭"],
                        "not_suitable_for": ["高强度暴走"],
                        "confidence": 0.85,
                        "usage_count": 128  # 被多少攻略采用
                    }
                ],
                "general_tips": [
                    {
                        "tip": "每天安排2-3个景点为宜，避免太赶",
                        "confidence": 0.88,
                        "source_type": "subjective",
                        "agree_count": 4
                    },
                    {
                        "tip": "带老人的话，每天1-2个景点就够了",
                        "confidence": 0.90,
                        "source_type": "subjective",
                        "agree_count": 5
                    },
                    {
                        "tip": "地铁是城市内出行的首选方式",
                        "confidence": 0.85,
                        "source_type": "objective",
                        "agree_count": 4
                    },
                    {
                        "tip": "热门景点建议提前预约",
                        "confidence": 0.92,
                        "source_type": "objective",
                        "agree_count": 5
                    }
                ]
            },
            "北京": {
                "attractions": {
                    "故宫": {
                        "closed_on": ["周一"],
                        "appointment_required": True,
                        "tips": ["需要提前预约", "周一闭馆"]
                    },
                    "长城": {
                        "best_time": "上午",
                        "tips": ["穿舒适的鞋子"]
                    }
                }
            },
            "上海": {
                "attractions": {
                    "迪士尼": {
                        "appointment_required": True,
                        "tips": ["建议工作日去", "周末人多"]
                    }
                }
            }
        }

    def get_city_knowledge(self, city: str) -> Optional[Dict]:
        """获取城市的经验知识"""
        return self.knowledge_base.get(city)

    def get_attraction_knowledge(self, city: str, attraction_name: str) -> Optional[Dict]:
        """获取景点的经验知识"""
        city_knowledge = self.get_city_knowledge(city)
        if not city_knowledge:
            return None
        return city_knowledge.get("attractions", {}).get(attraction_name)

    def get_congestion_risk(self, city: str, attraction_name: str, date_str: str) -> Dict:
        """检查人流风险"""
        attr_knowledge = self.get_attraction_knowledge(city, attraction_name)
        if not attr_knowledge:
            return {"has_risk": False}

        is_weekend = self._is_weekend(date_str)
        is_holiday = self._is_holiday(date_str)

        avoid_on = attr_knowledge.get("avoid_on", [])
        has_risk = False
        risk_reason = ""

        if is_weekend and "周末" in avoid_on:
            has_risk = True
            risk_reason = f"{attraction_name}在周末人流量大"
        elif is_holiday and "节假日" in avoid_on:
            has_risk = True
            risk_reason = f"{attraction_name}在节假日人流量大"

        return {
            "has_risk": has_risk,
            "severity": RiskSeverity.MEDIUM if has_risk else RiskSeverity.LOW,
            "reason": risk_reason,
            "mitigation": attr_knowledge.get("tips", ["建议错峰出行"])
        }

    def get_closure_risk(self, city: str, attraction_name: str, date_str: str) -> Dict:
        """检查闭馆风险"""
        attr_knowledge = self.get_attraction_knowledge(city, attraction_name)
        if not attr_knowledge:
            return {"has_risk": False}

        closed_on = attr_knowledge.get("closed_on", [])
        if not closed_on:
            return {"has_risk": False}

        weekday = self._get_weekday(date_str)

        if "周一" in closed_on and weekday == "Monday":
            return {
                "has_risk": True,
                "severity": RiskSeverity.HIGH,
                "reason": f"{attraction_name}在周一闭馆",
                "mitigation": ["改到其他日期"]
            }

        return {"has_risk": False}

    def get_appointment_requirement(self, city: str, attraction_name: str) -> Dict:
        """检查预约要求"""
        attr_knowledge = self.get_attraction_knowledge(city, attraction_name)
        if not attr_knowledge:
            return {"required": False}

        required = attr_knowledge.get("appointment_required", False)
        return {
            "required": required,
            "severity": RiskSeverity.MEDIUM if required else RiskSeverity.LOW,
            "tips": attr_knowledge.get("tips", []) if required else []
        }

    def get_general_tips(self, city: str) -> List[str]:
        """获取通用建议"""
        city_knowledge = self.get_city_knowledge(city)
        if not city_knowledge:
            return []
        return city_knowledge.get("general_tips", [])

    def _is_weekend(self, date_str: str) -> bool:
        """判断是否是周末"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            return date.weekday() >= 5
        except:
            return False

    def _is_holiday(self, date_str: str) -> bool:
        """判断是否是节假日（简化版）"""
        # 简化实现：只检查日期格式，实际应该用节假日库
        return False

    def _get_weekday(self, date_str: str) -> str:
        """获取星期几"""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday",
                       "Friday", "Saturday", "Sunday"]
            return weekdays[date.weekday()]
        except:
            return ""


class RiskIdentifier:
    """
    风险识别器

    负责识别行程中的潜在问题：
    1. 时间冲突（闭馆等）
    2. 人流风险
    3. 预约要求
    4. 体力负担
    5. 经验冲突
    """

    def __init__(self, knowledge_manager: ExperienceKnowledgeManager):
        self.knowledge = knowledge_manager
        logger.info("[RiskIdentifier] 风险识别器初始化完成")

    def identify_risks(self, trip_plan: Dict, city: str) -> List[Dict]:
        """
        识别行程中的所有风险

        Args:
            trip_plan: 旅行计划
            city: 城市

        Returns:
            风险列表
        """
        risks = []

        days = trip_plan.get("days", [])
        for day in days:
            day_date = day.get("date", "")
            day_index = day.get("day_index", 0)

            # 检查当天的每个景点
            attractions = day.get("attractions", [])
            for attr in attractions:
                attr_name = attr.get("name", "")

                # 1. 检查闭馆风险
                closure_risk = self.knowledge.get_closure_risk(city, attr_name, day_date)
                if closure_risk.get("has_risk"):
                    risks.append({
                        "type": RiskType.TIME_CONFLICT,
                        "severity": closure_risk["severity"],
                        "day": day_index + 1,
                        "date": day_date,
                        "attraction": attr_name,
                        "reason": closure_risk["reason"],
                        "mitigation": closure_risk["mitigation"]
                    })

                # 2. 检查人流风险
                congestion_risk = self.knowledge.get_congestion_risk(city, attr_name, day_date)
                if congestion_risk.get("has_risk"):
                    risks.append({
                        "type": RiskType.CONGESTION,
                        "severity": congestion_risk["severity"],
                        "day": day_index + 1,
                        "date": day_date,
                        "attraction": attr_name,
                        "reason": congestion_risk["reason"],
                        "mitigation": congestion_risk["mitigation"]
                    })

                # 3. 检查预约要求
                appointment_req = self.knowledge.get_appointment_requirement(city, attr_name)
                if appointment_req.get("required"):
                    risks.append({
                        "type": RiskType.APPOINTMENT,
                        "severity": appointment_req["severity"],
                        "day": day_index + 1,
                        "date": day_date,
                        "attraction": attr_name,
                        "reason": f"{attr_name}需要提前预约",
                        "mitigation": appointment_req["tips"]
                    })

            # 4. 检查体力负担
            physical_risk = self._check_physical_strain(day)
            if physical_risk.get("has_risk"):
                risks.append({
                    "type": RiskType.PHYSICAL_STRAIN,
                    "severity": physical_risk["severity"],
                    "day": day_index + 1,
                    "date": day_date,
                    "attraction": None,
                    "reason": physical_risk["reason"],
                    "mitigation": physical_risk["mitigation"]
                })

        # 按风险等级排序（高风险在前）
        risks.sort(key=lambda r: self._severity_order(r["severity"]))

        logger.info(f"[RiskIdentifier] 识别到 {len(risks)} 个风险")
        return risks

    def _check_physical_strain(self, day: Dict) -> Dict:
        """检查体力负担"""
        attractions = day.get("attractions", [])
        if len(attractions) >= 4:
            return {
                "has_risk": True,
                "severity": RiskSeverity.MEDIUM,
                "reason": f"一天安排了{len(attractions)}个景点，可能体力负担过重",
                "mitigation": ["建议拆成2天，每天2-3个景点"]
            }
        return {"has_risk": False}

    def _severity_order(self, severity: str) -> int:
        """风险等级排序权重"""
        order = {
            RiskSeverity.HIGH: 0,
            RiskSeverity.MEDIUM: 1,
            RiskSeverity.LOW: 2
        }
        return order.get(severity, 999)


class ItineraryRefiner:
    """
    行程修正器

    基于经验知识对行程进行修正
    """

    def __init__(self, knowledge_manager: ExperienceKnowledgeManager):
        self.knowledge = knowledge_manager
        logger.info("[ItineraryRefiner] 行程修正器初始化完成")

    def refine_plan(self, trip_plan: Dict, risks: List[Dict], city: str) -> Dict:
        """
        修正行程

        Args:
            trip_plan: 原始行程
            risks: 识别到的风险
            city: 城市

        Returns:
            修正后的行程
        """
        refined_plan = trip_plan.copy()
        refinements = []

        # 只修正高风险和中风险
        high_medium_risks = [r for r in risks if r["severity"] in [RiskSeverity.HIGH, RiskSeverity.MEDIUM]]

        for risk in high_medium_risks:
            refinement = self._apply_mitigation(refined_plan, risk, city)
            if refinement:
                refinements.append(refinement)

        # 添加修正说明
        refined_plan["refinements"] = refinements
        refined_plan["refinement_count"] = len(refinements)

        logger.info(f"[ItineraryRefiner] 完成 {len(refinements)} 处修正")
        return refined_plan

    def _apply_mitigation(self, plan: Dict, risk: Dict, city: str) -> Optional[Dict]:
        """应用修正策略"""
        risk_type = risk["type"]
        attraction = risk.get("attraction")
        day_index = risk.get("day", 1) - 1

        refinement = {
            "risk_type": risk_type,
            "risk_reason": risk["reason"],
            "day": day_index + 1,
            "attraction": attraction,
            "action_taken": "提醒注意",
            "mitigation_suggestions": risk.get("mitigation", [])
        }

        # 对于闭馆这种高风险，需要明确标注
        if risk_type == RiskType.TIME_CONFLICT:
            refinement["action_taken"] = "需要重新安排日期"

        # 对于人流风险，提供替代方案
        if risk_type == RiskType.CONGESTION:
            refinement["action_taken"] = "建议错峰或更换景点"

            # 尝试提供替代景点
            city_knowledge = self.knowledge.get_city_knowledge(city)
            if city_knowledge:
                alternatives = []
                for attr_name, attr_info in city_knowledge.get("attractions", {}).items():
                    if not attr_info.get("congestion_risk", False):
                        alternatives.append(attr_name)
                if alternatives:
                    refinement["alternative_attractions"] = alternatives[:3]

        return refinement


# ============ 单例 ============

_experience_manager: Optional[ExperienceKnowledgeManager] = None
_risk_identifier: Optional[RiskIdentifier] = None
_itinerary_refiner: Optional[ItineraryRefiner] = None


def get_experience_knowledge_manager() -> ExperienceKnowledgeManager:
    """获取经验知识管理器"""
    global _experience_manager
    if _experience_manager is None:
        _experience_manager = ExperienceKnowledgeManager()
    return _experience_manager


def get_risk_identifier() -> RiskIdentifier:
    """获取风险识别器"""
    global _risk_identifier
    if _risk_identifier is None:
        knowledge_manager = get_experience_knowledge_manager()
        _risk_identifier = RiskIdentifier(knowledge_manager)
    return _risk_identifier


def get_itinerary_refiner() -> ItineraryRefiner:
    """获取行程修正器"""
    global _itinerary_refiner
    if _itinerary_refiner is None:
        knowledge_manager = get_experience_knowledge_manager()
        _itinerary_refiner = ItineraryRefiner(knowledge_manager)
    return _itinerary_refiner

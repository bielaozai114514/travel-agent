"""
TripModifierAgent - 行程修改Agent

负责根据用户需求修改已有行程：
1. 分析修改需求
2. 决定需要调用哪些工具/Agent
3. 生成修改后的行程
"""
import json
import threading
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from settings import settings
from core.EsAgent import EsAgentLLM, SimpleAgent, ToolRegistry
from core.EsAgent.tools import MCPTool, TimeTool
from core.logger import logger
from core.trace import trace_span
from core.agent_stability import RobustJSONParser
from schemas.trip import TripPlan, TripRequest, DayPlan, Attraction, Meal, Hotel, Budget, WeatherInfo, Location


def _run_sync_in_thread(func, *args, **kwargs):
    """在新线程中运行同步函数，避免阻塞异步事件循环"""
    result = None
    exception = None

    def thread_target():
        nonlocal result, exception
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            exception = e

    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join()

    if exception:
        raise exception
    return result


TRIP_MODIFIER_SYSTEM_PROMPT = """你是一个专业的行程修改专家。

你的任务是根据用户的修改需求，对现有行程进行调整。

## 核心原则（非常重要！）

**最小化修改原则：只修改用户明确要求的部分，其他部分必须保持原样！**

例如：
- 用户说"不想去西湖，换一个" → 只把西湖换成其他景点，同一天的其他景点、其他天的所有安排都不能变！
- 用户说"把第一天改成5月2日" → 只改日期和天气，景点、餐饮、酒店都不变！
- 用户说"再加一天" → 在最后新增一天，原有天数的安排都不能变！

## 工作流程

1. **分析修改需求** - 理解用户想改什么，更重要的是理解用户不想改什么
2. **决定修改策略** - 判断是直接修改JSON，还是需要调用工具获取新信息
3. **执行修改** - 生成修改后的完整行程，确保只修改指定部分

## 修改类型优先级

按以下优先级处理修改需求：

1. **修改日期** - 如果用户改了日期，必须重新查询天气
2. **更换景点** - 如果用户换景点，可能需要重新搜索景点信息
3. **修改天数** - 增加/减少天数，需要重新调整整个行程
4. **调整偏好** - 改变景点类型偏好，可能需要重新搜索景点
5. **其他修改** - 根据具体需求处理

## 输出格式

请严格按照JSON格式输出完整的行程计划，不要包含其他内容。

JSON格式与原行程保持一致。

## 重要提示

- 保持原行程的整体结构和风格
- **只修改用户要求的部分，其他尽量保持不变**（这是最重要的！）
- 如果修改涉及日期变化，必须确保 weather_info 与新日期对应
- 如果修改涉及景点变化，确保景点的经纬度坐标真实准确
- 修改后重新计算预算
- 保持每天2-3个景点、早中晚三餐的结构

现在开始工作！记住：最小化修改！
"""


class TripModifierAgent:
    """行程修改Agent（混合模式）"""

    def __init__(self, mcp_tool: Optional[MCPTool] = None):
        """
        初始化TripModifierAgent

        Args:
            mcp_tool: 外部注入的MCPTool单例
        """
        self.llm = None
        self.amap_tool = mcp_tool
        self.modifier_agent = None
        self.attraction_agent = None
        self.weather_agent = None
        self.hotel_agent = None

        self._init_all()
        logger.debug("TripModifierAgent 初始化完成")

    def _init_all(self):
        """初始化所有组件"""
        self.llm = self._create_llm()
        self.modifier_agent = self._create_modifier_agent()
        self.attraction_agent = self._create_attraction_agent()
        self.weather_agent = self._create_weather_agent()
        self.hotel_agent = self._create_hotel_agent()

    def _create_llm(self) -> EsAgentLLM:
        """创建LLM实例"""
        config = settings.get_agent_config("planner")
        return EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=config.timeout if config.timeout > 120 else 300,
        )

    def _create_llm_for_agent(self, agent_type: str) -> EsAgentLLM:
        """为特定类型的Agent创建LLM实例"""
        config = settings.get_agent_config(agent_type)
        return EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=config.timeout,
        )

    def _create_modifier_agent(self) -> SimpleAgent:
        """创建行程修改主Agent"""
        agent = SimpleAgent(
            name="行程修改专家",
            llm=self.llm,
            system_prompt=TRIP_MODIFIER_SYSTEM_PROMPT,
            enable_tool_calling=False
        )
        return agent

    def _create_attraction_agent(self) -> SimpleAgent:
        """创建景点搜索Agent（复用TripPlannerAgent的逻辑）"""
        from core.trip_planner_agent import ATTRACTION_AGENT_PROMPT

        llm = self._create_llm_for_agent("attraction")
        agent = SimpleAgent(
            name="景点搜索专家",
            llm=llm,
            system_prompt=ATTRACTION_AGENT_PROMPT,
            enable_tool_calling=self.amap_tool is not None
        )
        if self.amap_tool:
            agent.add_tool(self.amap_tool)
        return agent

    def _create_weather_agent(self) -> SimpleAgent:
        """创建天气查询Agent（复用TripPlannerAgent的逻辑）"""
        from core.trip_planner_agent import WEATHER_AGENT_PROMPT

        llm = self._create_llm_for_agent("weather")
        agent = SimpleAgent(
            name="天气查询专家",
            llm=llm,
            system_prompt=WEATHER_AGENT_PROMPT,
            enable_tool_calling=self.amap_tool is not None
        )
        if self.amap_tool:
            agent.add_tool(self.amap_tool)
        return agent

    def _create_hotel_agent(self) -> SimpleAgent:
        """创建酒店推荐Agent（复用TripPlannerAgent的逻辑）"""
        from core.trip_planner_agent import HOTEL_AGENT_PROMPT

        llm = self._create_llm_for_agent("hotel")
        agent = SimpleAgent(
            name="酒店推荐专家",
            llm=llm,
            system_prompt=HOTEL_AGENT_PROMPT,
            enable_tool_calling=self.amap_tool is not None
        )
        if self.amap_tool:
            agent.add_tool(self.amap_tool)
        return agent

    def _analyze_modification_type(self, modification_summary: str) -> Dict[str, bool]:
        """
        分析修改类型，决定需要调用哪些工具

        Returns:
            Dict indicating which tools are needed:
            {
                "need_weather": bool,
                "need_attractions": bool,
                "need_hotels": bool,
            }
        """
        summary_lower = modification_summary.lower()

        need_weather = any(keyword in summary_lower for keyword in [
            "日期", "时间", "明天", "后天", "下周", "改期", "date", "day"
        ])

        need_attractions = any(keyword in summary_lower for keyword in [
            "景点", "换成", "改景点", "加景点", "去掉景点", "attraction", "spot"
        ])

        need_hotels = any(keyword in summary_lower for keyword in [
            "酒店", "住宿", "hotel", "accommodation"
        ])

        return {
            "need_weather": need_weather,
            "need_attractions": need_attractions,
            "need_hotels": need_hotels,
        }

    async def amodify_trip(
        self,
        original_trip: TripPlan,
        modification_summary: str,
        conversation_history: Optional[str] = None
    ) -> TripPlan:
        """
        异步修改行程

        Args:
            original_trip: 原始行程
            modification_summary: 修改需求总结
            conversation_history: 对话历史（可选）

        Returns:
            修改后的行程
        """
        with trace_span(
            name="TripModifier.amodify_trip",
            level="AGENT",
            agent_type="TripModifierAgent",
        ) as span:
            span.set_input({
                "original_city": original_trip.city,
                "modification_summary": modification_summary,
            })

            try:
                logger.info(f"开始修改行程: city={original_trip.city}, modification={modification_summary[:50]}...")

                # 1. 分析修改类型
                modification_types = self._analyze_modification_type(modification_summary)
                logger.info(f"修改类型分析: {modification_types}")

                # 2. 收集补充信息（在线程池中运行同步调用）
                additional_info = {}

                if modification_types["need_weather"]:
                    with trace_span(name="query_weather", level="STEP"):
                        logger.info("需要重新查询天气")
                        weather_query = f"请查询{original_trip.city}的天气信息"
                        additional_info["weather_info"] = await asyncio.to_thread(
                            self.weather_agent.run, weather_query
                        )

                if modification_types["need_attractions"]:
                    with trace_span(name="search_attractions", level="STEP"):
                        logger.info("需要重新搜索景点")
                        attraction_query = f"请搜索{original_trip.city}的景点"
                        additional_info["attraction_info"] = await asyncio.to_thread(
                            self.attraction_agent.run, attraction_query
                        )

                if modification_types["need_hotels"]:
                    with trace_span(name="search_hotels", level="STEP"):
                        logger.info("需要重新搜索酒店")
                        hotel_query = f"请搜索{original_trip.city}的酒店"
                        additional_info["hotel_info"] = await asyncio.to_thread(
                            self.hotel_agent.run, hotel_query
                        )

                # 3. 构建修改查询
                modifier_query = self._build_modifier_query(
                    original_trip, modification_summary, additional_info, conversation_history
                )

                # 4. 调用修改Agent（在线程池中运行）
                with trace_span(name="generate_modified_plan", level="STEP"):
                    modifier_response = await asyncio.to_thread(
                        self.modifier_agent.run, modifier_query
                    )

                # 5. 解析结果
                modified_trip = self._parse_modified_response(modifier_response, original_trip)
                if modified_trip.model_dump() == original_trip.model_dump():
                    raise ValueError("行程修改结果未发生变化")

                logger.info(f"行程修改完成: city={modified_trip.city}, days={len(modified_trip.days)}")
                span.set_output({"city": modified_trip.city, "days": len(modified_trip.days)})

                return modified_trip

            except Exception as e:
                logger.error(f"修改行程失败: {str(e)}", exc_info=True)
                span.set_error(e)
                raise

    def _build_modifier_query(
        self,
        original_trip: TripPlan,
        modification_summary: str,
        additional_info: Dict[str, str],
        conversation_history: Optional[str] = None
    ) -> str:
        """构建修改查询"""

        def truncate(text: str, max_len: int, name: str = "") -> str:
            """截断文本"""
            if len(text) <= max_len:
                return text
            logger.warning(f"[TripModifier] {name} 长度超限({len(text)}>{max_len})，将进行截断")
            return text[:max_len] + "\n...[内容已截断]"

        # 将原始行程转换为JSON
        original_trip_json = json.dumps(original_trip.model_dump(), ensure_ascii=False, indent=2)

        query_parts = [
            "## 原始行程",
            truncate(original_trip_json, 8000, "原始行程"),
            "",
            "## 修改需求",
            modification_summary,
            "",
            "## 重要原则（必须遵守！）",
            "1. 只修改用户明确要求的部分，其他部分必须保持原样！",
            "2. 比如用户说'不想去西湖，换一个' → 只把西湖换成其他景点，同一天的其他景点、其他天的所有安排都不能变！",
            "3. 修改时保持原行程的整体结构和风格",
        ]

        if conversation_history:
            query_parts.extend([
                "",
                "## 对话历史参考",
                truncate(conversation_history, 2000, "对话历史"),
            ])

        if additional_info.get("weather_info"):
            query_parts.extend([
                "",
                "## 补充天气信息",
                truncate(additional_info["weather_info"], 1500, "天气信息"),
            ])

        if additional_info.get("attraction_info"):
            query_parts.extend([
                "",
                "## 补充景点信息",
                truncate(additional_info["attraction_info"], 4000, "景点信息"),
            ])

        if additional_info.get("hotel_info"):
            query_parts.extend([
                "",
                "## 补充酒店信息",
                truncate(additional_info["hotel_info"], 2000, "酒店信息"),
            ])

        query_parts.extend([
            "",
            "请根据以上信息，生成修改后的完整行程计划。",
            "注意：只输出JSON格式的完整行程，不要包含其他说明文字。",
        ])

        full_query = "\n".join(query_parts)
        logger.info(f"[TripModifier] 修改查询总长度: {len(full_query)} 字符")

        return full_query

    def _parse_modified_response(self, response: str, original_trip: TripPlan) -> TripPlan:
        """解析修改后的响应"""
        try:
            logger.info(f"[TripModifier] 开始解析响应，长度: {len(response)} 字符")

            # 使用鲁棒JSON解析器
            parse_result = RobustJSONParser.parse(response)

            if not parse_result.success:
                raise ValueError("行程修改结果不是有效JSON")

            logger.info(f"[TripModifier] JSON解析成功，使用方法: {parse_result.parse_method}")
            data = parse_result.data

            # 尝试构建TripPlan
            try:
                trip_plan = TripPlan(**data)
                logger.info(f"[TripModifier] TripPlan构建成功，天数: {len(trip_plan.days)}")
                return trip_plan
            except Exception as e:
                logger.warning(f"[TripModifier] TripPlan构建失败，尝试修复数据: {e}")
                fixed_data = self._fix_modified_trip_data(data, original_trip)
                trip_plan = TripPlan(**fixed_data)
                logger.info(f"[TripModifier] 修复后TripPlan构建成功，天数: {len(trip_plan.days)}")
                return trip_plan

        except Exception as e:
            logger.error(f"[TripModifier] 解析响应最终失败: {str(e)}", exc_info=True)
            raise

    def _fix_modified_trip_data(self, data: Dict, original_trip: TripPlan) -> Dict:
        """修复修改后的行程数据"""
        logger.info(f"[TripModifier] 开始修复修改后的TripPlan数据")

        # 确保基础字段存在，缺失时使用原行程的值
        data.setdefault("city", original_trip.city)
        data.setdefault("start_date", original_trip.start_date)
        data.setdefault("end_date", original_trip.end_date)
        data.setdefault("overall_suggestions", original_trip.overall_suggestions)
        data.setdefault("weather_info", original_trip.weather_info)
        data.setdefault("budget", original_trip.budget.model_dump() if original_trip.budget else {
            "total_attractions": 0,
            "total_hotels": 0,
            "total_meals": 0,
            "total_transportation": 0,
            "total": 0
        })

        # 确保days字段存在
        if "days" not in data or not isinstance(data["days"], list):
            logger.warning(f"[TripModifier] days字段缺失或无效，使用原行程")
            data["days"] = [day.model_dump() for day in original_trip.days]

        # 修复每一天的数据
        for i, day in enumerate(data["days"]):
            if i < len(original_trip.days):
                original_day = original_trip.days[i]
                day.setdefault("date", original_day.date)
                day.setdefault("day_index", original_day.day_index)
                day.setdefault("description", original_day.description)
                day.setdefault("transportation", original_day.transportation)
                day.setdefault("accommodation", original_day.accommodation)
                day.setdefault("attractions", [])
                day.setdefault("meals", [])

        logger.info(f"[TripModifier] 修改后的TripPlan数据修复完成")
        return data


# 单例实例（如果需要的话，但通常每次新建）
_trip_modifier_agent_instance: Optional[TripModifierAgent] = None


def get_trip_modifier_agent(mcp_tool: Optional[MCPTool] = None) -> TripModifierAgent:
    """获取TripModifierAgent实例（每次新建，保持无状态）"""
    return TripModifierAgent(mcp_tool=mcp_tool)

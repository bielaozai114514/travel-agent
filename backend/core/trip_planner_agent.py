"""旅行规划Agent服务 - 阶段式编排：攻略先导 → 候选集驱动 → 信息补全 → 初始规划"""

import json
import asyncio
import threading
from time import perf_counter
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta

from settings import settings
from core.EsAgent import EsAgentLLM, SimpleAgent, ToolRegistry
from core.EsAgent.tools import MCPTool
from core.logger import logger
from core.trace import trace_span, get_current_trace_id
from core.agent_stability import RobustJSONParser, ParseResult
from core.timing import TimingCollector
from core.planning_context import (
    TripPlanningContext, extract_candidates_from_guides, build_rag_query,
    build_key_facts_text,
)
from services.amap_service import get_amap_mcp_tool
from services.location_fix_service import fix_trip_plan_locations
from schemas.trip import (
    TripRequest, TripPlan, DayPlan, Attraction, Meal,
    WeatherInfo, Location, Hotel, Budget
)


# 延迟导入guide_rag_service
_guide_rag_service = None


def _get_guide_rag_service():
    """延迟导入guide_rag_service"""
    global _guide_rag_service
    if _guide_rag_service is None:
        from services.guide_rag_service import search_guides_rag
        _guide_rag_service = search_guides_rag
    return _guide_rag_service


# Deprecated: _run_async_in_thread 仅被 _search_guides_sync 使用，阶段式编排中不再需要。
# 保留以兼容旧 plan_trip() 同步路径。
def _run_async_in_thread(coro):
    """在新线程中运行异步函数（Deprecated — 保留仅供旧同步路径兼容）"""
    result = None
    exception = None

    def thread_target():
        nonlocal result, exception
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
        except Exception as e:
            exception = e
        finally:
            try:
                loop.close()
            except:
                pass

    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join()

    if exception:
        raise exception
    return result


ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]

用户: "搜索上海的公园"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=公园,city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 参数用逗号分隔
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

**重要提示:**
你必须使用工具来查询天气!不要自己编造天气信息!

**工具调用格式:**
使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`

**示例:**
用户: "查询北京天气"
你的回复: [TOOL_CALL:amap_maps_weather:city=北京]

用户: "上海的天气怎么样"
你的回复: [TOOL_CALL:amap_maps_weather:city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

**重要提示:**
你必须使用工具来搜索酒店!不要自己编造酒店信息!

**工具调用格式:**
使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`

**示例:**
用户: "搜索北京的酒店"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=北京]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 关键词使用"酒店"或"宾馆"
"""

# Deprecated: Guide Expert Agent 不再参与规划流程。实际攻略检索由 M5 Adaptive TCR-RAG 的 search_guides_rag() 承担。
GUIDE_EXPERT_AGENT_PROMPT_DEPRECATED = """你是旅游攻略专家。你的任务是搜索和总结已有的旅游攻略，为行程规划提供参考。

请根据用户提供的城市和偏好，搜索相关攻略，并提供以下信息：
1. 该城市最值得去的景点
2. 推荐的行程路线
3. 当地美食推荐
4. 旅行注意事项
5. 交通建议

如果没有找到相关攻略，请明确说明，不要编造信息。

输出格式请清晰、结构化，方便后续的行程规划专家使用。"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息、天气信息、酒店信息以及旅游攻略参考，生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


class TripPlannerAgent:
    """多智能体旅行规划系统（无状态化）

    每次请求新建实例，MCPTool从外部注入。
    """

    def __init__(self, mcp_tool: Optional[MCPTool] = None):
        """
        初始化TripPlannerAgent（无状态化，每次请求新建实例）

        Args:
            mcp_tool: 外部注入的MCPTool单例（可选，不传则不使用MCP）
        """
        self.llm = None
        self.amap_tool = mcp_tool  # MCP从外部注入，不自己创建
        self.attraction_agent = None
        self.weather_agent = None
        self.hotel_agent = None
        # Deprecated: guide_expert_agent 不再初始化。攻略检索由 M5 RAG Retriever 承担。
        self.planner_agent = None
        self.timing = TimingCollector()
        self.last_planning_context = None  # 供评估脚本读取真实候选信息
        self.last_timing_report: Dict = {}

        # 直接初始化，不再使用async_init双重检查
        self._init_all()
        logger.debug("TripPlannerAgent 初始化完成（阶段式编排）")

    def _init_all(self):
        """初始化所有组件（直接同步初始化）"""
        self.llm = self._create_llm()
        self.attraction_agent = self._create_attraction_agent()
        self.weather_agent = self._create_weather_agent()
        self.hotel_agent = self._create_hotel_agent()
        # Deprecated: guide_expert_agent 不再初始化
        self.planner_agent = self._create_planner_agent()

    def _create_llm(self) -> EsAgentLLM:
        """创建LLM实例（用于行程规划主Agent）"""
        config = settings.get_agent_config("planner")
        return EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=config.timeout,
        )

    #  ================为每个agent设置单独的配置（默认基础配置）

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

    def _create_attraction_agent(self) -> SimpleAgent:
        """创建景点搜索Agent"""
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
        """创建天气查询Agent"""
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
        """创建酒店推荐Agent"""
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

    # Deprecated: Guide Expert Agent 不再参与规划。攻略检索由 M5 RAG Retriever 承担。
    def _create_guide_expert_agent_deprecated(self) -> SimpleAgent:
        """[Deprecated] 创建攻略专家Agent — 不再使用。保留代码仅供参考。"""
        llm = self._create_llm_for_agent("guide_expert")
        agent = SimpleAgent(
            name="旅游攻略专家(deprecated)",
            llm=llm,
            system_prompt=GUIDE_EXPERT_AGENT_PROMPT_DEPRECATED,
            enable_tool_calling=False
        )
        return agent

    def get_timing_report(self) -> Dict:
        """获取最近一次规划的耗时报告"""
        return self.last_timing_report or self.timing.report()

    def _create_planner_agent(self) -> SimpleAgent:
        """创建行程规划Agent（单独创建LLM实例，设置更长超时）"""
        # 为 Planner Agent 单独创建 LLM，设置更长的超时时间
        config = settings.get_agent_config("planner")
        # 使用更长的超时时间：默认 300 秒（5分钟）
        planner_timeout = config.timeout if config.timeout > 120 else 300

        planner_llm = EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=planner_timeout,
        )
        logger.debug(f"[Planner] 创建行程规划Agent，超时设置: {planner_timeout}秒")

        agent = SimpleAgent(
            name="行程规划专家",
            llm=planner_llm,
            system_prompt=PLANNER_AGENT_PROMPT,
            enable_tool_calling=False
        )
        return agent

    def _search_guides_sync(self, city: str, preferences: Optional[List[str]] = None) -> str:
        """
        [Deprecated] 同步搜索旅游攻略 — 保留仅供旧 plan_trip() 同步路径参考。
        阶段式编排请使用 _retrieve_travel_guides()。
        """
        with trace_span(
            name="search_guides_rag_sync",
            level="TOOL",
        ) as span:
            span.set_tool_data(
                tool_name="search_guides_rag",
                parameters={"city": city, "preferences": preferences},
            )

            try:
                search_guides_rag = _get_guide_rag_service()

                # 构建搜索查询
                query = f"{city}旅游攻略"
                if preferences:
                    query += " " + " ".join(preferences)

                # 在新线程中运行异步搜索
                results = _run_async_in_thread(
                    search_guides_rag(
                        query=query,
                        city=city,
                        limit=5,
                        min_score=0.3
                    )
                )

                if not results:
                    result = "暂无相关旅游攻略参考。"
                    span.set_tool_data(
                        tool_name="search_guides_rag",
                        parameters={"city": city, "preferences": preferences},
                        result=result,
                    )
                    return result

                # 格式化结果
                output_parts = ["【旅游攻略参考】\n"]

                for i, result in enumerate(results, 1):
                    title = result.get("title", "无标题")
                    content = result.get("content", "")
                    tags = result.get("metadata", {}).get("tags", [])

                    output_parts.append(f"\n攻略{i}: {title}")
                    if tags:
                        output_parts.append(f"标签: {', '.join(tags)}")
                    if content:
                        output_parts.append(f"摘要: {content[:300]}")

                result = "\n".join(output_parts)
                span.set_tool_data(
                    tool_name="search_guides_rag",
                    parameters={"city": city, "preferences": preferences},
                    result={"result_count": len(results)},
                )
                return result

            except Exception as e:
                logger.warning(f"搜索攻略失败: {e}")
                span.set_error(e)
                return "攻略搜索暂时不可用。"

    async def _search_guides_async(self, rag_query: str, city: str) -> Tuple[List[dict], str]:
        """
        异步搜索旅游攻略（阶段式编排版本）

        Args:
            rag_query: 完整 RAG 查询
            city: 城市

        Returns:
            (rag_results, rag_context) — 原始结果列表 + 格式化文本
        """
        with trace_span(
            name="search_guides_rag_async",
            level="TOOL",
        ) as span:
            span.set_tool_data(
                tool_name="search_guides_rag",
                parameters={"city": city, "query": rag_query[:200]},
            )

            try:
                search_guides_rag = _get_guide_rag_service()

                # 直接 await 异步搜索，不需要在线程中运行
                results = await search_guides_rag(
                    query=rag_query,
                    city=city,
                    limit=5,
                    min_score=0.3
                )

                if not results:
                    rag_context = "暂无相关旅游攻略参考。"
                    log_msg = f"[RAG→Planner] 搜索结果为空 | city={city} | query={rag_query[:120]}"
                    logger.info(log_msg)
                    span.set_tool_data(
                        tool_name="search_guides_rag",
                        parameters={"city": city, "query": rag_query[:200]},
                        result="no_results",
                    )
                    return [], rag_context

                # 格式化结果
                logger.info(f"[RAG→Planner] ====== 共返回 {len(results)} 条结果 ======")
                output_parts = ["【旅游攻略参考】\n"]

                for i, result in enumerate(results, 1):
                    title = result.get("title", "无标题")
                    content = result.get("content", "")
                    tags = result.get("metadata", {}).get("tags", [])
                    score = result.get("score", 0)
                    section_type = result.get("section_type") or result.get("metadata", {}).get("section_type", "")
                    heading = result.get("heading_path") or result.get("metadata", {}).get("heading_path", "")

                    # 每条结果完整日志
                    logger.info(
                        f"[RAG→Planner] 结果#{i}: title={title} | "
                        f"score={score:.4f} | section={section_type} | "
                        f"heading={heading[:60] if heading else '-'} | "
                        f"tags={tags} | content_len={len(content)}"
                    )
                    logger.info(f"[RAG→Planner] 结果#{i} content[0:300]: {content[:300]}")

                    output_parts.append(f"\n攻略{i}: {title}")
                    if tags:
                        output_parts.append(f"标签: {', '.join(tags)}")
                    if section_type:
                        output_parts.append(f"章节类型: {section_type}")
                    if heading:
                        output_parts.append(f"章节路径: {heading}")
                    if content:
                        output_parts.append(f"摘要: {content[:300]}")

                rag_context = "\n".join(output_parts)
                logger.info(
                    f"[RAG→Planner] rag_context 总长度: {len(rag_context)} 字符, "
                    f"将送入 Planner prompt【攻略检索依据】区域"
                )
                span.set_tool_data(
                    tool_name="search_guides_rag",
                    parameters={"city": city, "query": rag_query[:200]},
                    result={"result_count": len(results)},
                )
                return results, rag_context

            except Exception as e:
                logger.warning(f"搜索攻略失败: {e}")
                span.set_error(e)
                return [], "攻略搜索暂时不可用。"

    def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        使用多智能体协作生成旅行计划（同步版本，向后兼容）

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        import asyncio

        # ============ AGENT 层级 Trace - 整个规划流程 ============
        with trace_span(
            name="TripPlanner.plan_trip",
            level="AGENT",
            agent_type="TripPlannerAgent",
        ) as span:
            span.set_input({
                "city": request.city,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "travel_days": request.travel_days,
                "preferences": request.preferences,
            })

            try:
                # 设置 AGENT 输入
                span.set_input({
                    "city": request.city,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "travel_days": request.travel_days,
                    "preferences": request.preferences,
                })

                # 步骤0: 攻略专家搜索相关攻略
                with trace_span(
                    name="search_guides",
                    level="STEP",
                ) as step_span:
                    step_span.set_metadata("city", request.city)
                    guide_response = self._search_guides_sync(request.city, request.preferences)
                    step_span.set_output({"guide_length": len(guide_response), "guide_result": guide_response})

                # 步骤1: 景点搜索Agent搜索景点
                with trace_span(
                    name="search_attractions",
                    level="STEP",
                ) as step_span:
                    step_span.set_metadata("city", request.city)
                    attraction_query = self._build_attraction_query(request)
                    step_span.set_input({"query": attraction_query})
                    attraction_response = self.attraction_agent.run(attraction_query)
                    step_span.set_output({"response_length": len(attraction_response), "result": attraction_response})

                # 步骤2: 天气查询Agent查询天气
                with trace_span(
                    name="search_weather",
                    level="STEP",
                ) as step_span:
                    step_span.set_metadata("city", request.city)
                    weather_query = f"请查询{request.city}的天气信息"
                    step_span.set_input({"query": weather_query})
                    weather_response = self.weather_agent.run(weather_query)
                    step_span.set_output({"response_length": len(weather_response), "result": weather_response})

                # 步骤3: 酒店推荐Agent搜索酒店
                with trace_span(
                    name="search_hotels",
                    level="STEP",
                ) as step_span:
                    step_span.set_metadata("city", request.city)
                    hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
                    step_span.set_input({"query": hotel_query})
                    hotel_response = self.hotel_agent.run(hotel_query)
                    step_span.set_output({"response_length": len(hotel_response), "result": hotel_response})

                # 步骤4: 行程规划Agent整合信息生成计划
                with trace_span(
                    name="generate_plan",
                    level="STEP",
                ) as step_span:
                    planner_query = self._build_planner_query(
                        request, attraction_response, weather_response, hotel_response, guide_response
                    )
                    step_span.set_input({"query_length": len(planner_query)})
                    planner_response = self.planner_agent.run(planner_query)
                    step_span.set_output({"response_length": len(planner_response), "result": planner_response})

                # 解析最终计划
                trip_plan = self._parse_response(planner_response, request)

                span.set_output({"city": request.city, "days": len(trip_plan.days)})
                return trip_plan

            except Exception as e:
                logger.error(f"生成旅行计划失败: {str(e)}", exc_info=True)
                span.set_error(e)
                raise

    # Deprecated: 阶段式编排中景点查询逻辑合并到 _collect_external_info()
    def _build_attraction_query(self, request: TripRequest) -> str:
        """[Deprecated] 构建景点搜索查询 — 保留仅供旧 plan_trip() 同步路径参考。"""
        keywords = []
        if request.preferences:
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        # 如果有MCP工具，直接返回工具调用格式
        if self.amap_tool:
            query = f"请使用amap_maps_text_search工具搜索{request.city}的{keywords}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={keywords},city={request.city}]"
        else:
            query = f"请根据你的知识，推荐{request.city}的{keywords}相关景点，包含名称、地址、经纬度坐标、游览时间等信息。"
        return query

    def _build_planner_query(
        self, request: TripRequest, attractions: str, weather: str, hotels: str = "", guides: str = ""
    ) -> str:
        """构建行程规划查询（优化版本：限制各部分长度，避免token超限）"""

        def truncate(text: str, max_len: int, name: str = "") -> str:
            """截断文本并记录日志"""
            if len(text) <= max_len:
                return text
            logger.warning(f"[Planner] {name} 长度超限({len(text)}>{max_len})，将进行截断")
            return text[:max_len] + "\n...[内容已截断]"

        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**旅游攻略参考:**
{truncate(guides if guides else '暂无攻略参考', 2000, '旅游攻略')}

**景点信息:**
{truncate(attractions, 4000, '景点信息')}

**天气信息:**
{truncate(weather, 1500, '天气信息')}

**酒店信息:**
{truncate(hotels, 2000, '酒店信息')}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店
4. 考虑景点之间的距离和交通方式
5. 返回完整的JSON格式数据
6. 景点的经纬度坐标要真实准确
7. 必须包含预算信息
8. 如果有旅游攻略参考，请优先参考攻略中的建议
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        total_len = len(query)
        logger.info(f"[Planner] 查询总长度: {total_len} 字符")
        if total_len > 12000:
            logger.warning(f"[Planner] 查询总长度超过12000字符，可能触发token限制")

        return query

    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        """解析Agent响应（使用RobustJSONParser增强容错）"""
        try:
            logger.info(f"[Planner] 开始解析响应，长度: {len(response)} 字符")

            # 使用鲁棒JSON解析器
            parse_result = RobustJSONParser.parse(response)

            if not parse_result.success:
                raise ValueError("行程规划结果不是有效JSON，无法生成可用行程")

            logger.info(f"[Planner] JSON解析成功，使用方法: {parse_result.parse_method}")
            data = parse_result.data

            # 尝试构建TripPlan
            try:
                trip_plan = TripPlan(**data)
                self._validate_trip_plan_quality(trip_plan, request)
                logger.info(f"[Planner] TripPlan构建成功，天数: {len(trip_plan.days)}")
                return trip_plan
            except Exception as e:
                logger.warning(f"[Planner] TripPlan构建失败，尝试修复数据: {e}")
                # 尝试修复数据并重新构建
                fixed_data = self._fix_trip_plan_data(data, request)
                trip_plan = TripPlan(**fixed_data)
                self._validate_trip_plan_quality(trip_plan, request)
                logger.info(f"[Planner] 修复后TripPlan构建成功，天数: {len(trip_plan.days)}")
                return trip_plan

        except Exception as e:
            logger.error(f"[Planner] 解析响应最终失败: {str(e)}", exc_info=True)
            raise

    def _validate_trip_plan_quality(self, trip_plan: TripPlan, request: TripRequest) -> None:
        """校验生成结果是否达到可保存的最低业务质量。"""
        if len(trip_plan.days) != request.travel_days:
            raise ValueError(
                f"行程天数不匹配，期望{request.travel_days}天，实际{len(trip_plan.days)}天"
            )

        empty_days = [
            day.day_index + 1
            for day in trip_plan.days
            if not day.attractions
        ]
        if empty_days:
            raise ValueError(f"第{empty_days}天缺少景点安排，行程不可用")

    def _fix_trip_plan_data(self, data: Dict, request: TripRequest) -> Dict:
        """
        修复TripPlan数据，确保必填字段存在

        Args:
            data: 原始解析数据
            request: 原始请求

        Returns:
            修复后的数据
        """
        from datetime import datetime, timedelta

        logger.info(f"[Planner] 开始修复TripPlan数据")

        # 确保基础字段
        data.setdefault("city", request.city)
        data.setdefault("start_date", request.start_date)
        data.setdefault("end_date", request.end_date)
        data.setdefault("overall_suggestions", f"这是为您规划的{request.city}{request.travel_days}日游行程。")
        data.setdefault("weather_info", [])
        data.setdefault("budget", {
            "total_attractions": 0,
            "total_hotels": 0,
            "total_meals": 0,
            "total_transportation": 0,
            "total": 0
        })

        # 确保days字段存在且有效
        if "days" not in data or not isinstance(data["days"], list):
            raise ValueError("行程结果缺少有效的days字段")

        # 填充或修复每一天
        try:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            start_date = datetime.now() + timedelta(days=1)

        expected_days = request.travel_days
        actual_days = len(data["days"])

        if actual_days < expected_days:
            raise ValueError(f"行程天数不足，期望{expected_days}天，实际{actual_days}天")
        elif actual_days > expected_days:
            logger.warning(f"[Planner] 天数过多，期望{expected_days}天，实际{actual_days}天，将截断")
            data["days"] = data["days"][:expected_days]

        # 修复每一天的数据
        for i in range(expected_days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")

            if i < len(data["days"]):
                day = data["days"][i]
                # 修复现有天
                day.setdefault("date", date_str)
                day.setdefault("day_index", i)
                day.setdefault("description", f"第{i+1}天行程")
                day.setdefault("transportation", request.transportation)
                day.setdefault("accommodation", request.accommodation)
                day.setdefault("attractions", [])
                day.setdefault("meals", [])
            else:
                # 补充缺失的天
                data["days"].append({
                    "date": date_str,
                    "day_index": i,
                    "description": f"第{i+1}天行程",
                    "transportation": request.transportation,
                    "accommodation": request.accommodation,
                    "attractions": [],
                    "meals": []
                })

        logger.info(f"[Planner] TripPlan数据修复完成")
        return data

    def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
        """创建备用计划"""
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")

        days = []
        for i in range(request.travel_days):
            current_date = start_date + timedelta(days=i)

            day_plan = DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i+1}天行程",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=[
                    Attraction(
                        name=f"{request.city}景点{j+1}",
                        address=f"{request.city}市",
                        location=Location(longitude=116.4 + i*0.01 + j*0.005, latitude=39.9 + i*0.01 + j*0.005),
                        visit_duration=120,
                        description=f"这是{request.city}的著名景点",
                        category="景点"
                    )
                    for j in range(2)
                ],
                meals=[
                    Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐", estimated_cost=30),
                    Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐", estimated_cost=50),
                    Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐", estimated_cost=80)
                ]
            )
            days.append(day_plan)

        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=[],
            overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程,建议提前查看各景点的开放时间。"
        )

    async def aplan_trip(self, request: TripRequest) -> TripPlan:
        """
        阶段式编排生成旅行计划（异步版本）

        流程：需求理解 → 攻略检索 → 候选抽取 → 信息补全 → 初始规划 → 标准化 → 风险占位 → 最终化
        """
        import asyncio
        self.timing = TimingCollector()
        self.last_timing_report = {}

        with trace_span(
            name="TripPlanner.aplan_trip",
            level="AGENT",
            agent_type="TripPlannerAgent",
        ) as span:
            span.set_input({
                "city": request.city,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "travel_days": request.travel_days,
                "preferences": request.preferences,
            })

            try:
                # 阶段1: 需求理解
                context = self._collect_user_context(request)

                # 阶段2: 攻略检索（先执行，其他阶段依赖其结果）
                context = await self._retrieve_travel_guides(context)

                # 阶段3: 候选景点/区域抽取（同步，纯规则）
                context = self._extract_candidates(context)

                # 阶段4: 外部信息补全（阶段内并行）
                context = await self._collect_external_info(context)

                # 阶段5: 初始行程生成
                context = await self._generate_initial_plan(context)

                # 阶段6: 标准化与坐标修正
                context = await self._normalize_plan(context)

                # 阶段7: 风险识别占位
                context = self._evaluate_and_repair_plan(context)

                # 阶段8: 最终化
                result = self._finalize_plan(context)

                span.set_output({"city": request.city, "days": len(result.days)})
                self.last_planning_context = context
                self.last_timing_report = self.timing.report()
                return result

            except Exception as e:
                logger.error(f"[异步] 生成旅行计划失败: {str(e)}", exc_info=True)
                span.set_error(e)
                try:
                    self.last_planning_context = context
                except NameError:
                    self.last_planning_context = None
                self.last_timing_report = self.timing.report()
                raise

    # ========== 阶段式编排：各阶段实现 ==========

    def _collect_user_context(self, request: TripRequest) -> TripPlanningContext:
        """阶段1: 需求理解 — 构建 TripPlanningContext"""
        context = TripPlanningContext(
            request=request,
            city=request.city,
            travel_days=request.travel_days,
            preferences=request.preferences or [],
        )
        logger.info(
            f"[阶段1] 用户上下文收集完成: "
            f"city={context.city}, days={context.travel_days}, "
            f"preferences={context.preferences}, "
            f"transportation={request.transportation}, "
            f"accommodation={request.accommodation}, "
            f"free_text={request.free_text_input[:50] if request.free_text_input else ''}"
        )
        return context

    async def _retrieve_travel_guides(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段2: 攻略检索 — M5 Adaptive TCR-RAG（先于景点/酒店搜索执行）"""
        with trace_span(name="retrieve_travel_guides", level="STEP") as step_span:
            with self.timing.measure("guide_rag_search", "agent_search"):
                rag_query = build_rag_query(context)
                logger.info(f"[阶段2] RAG 查询: {rag_query}")

                rag_results, rag_context = await self._search_guides_async(rag_query, context.city)

                context.rag_query = rag_query
                context.rag_results = rag_results
                context.rag_context = rag_context

            step_span.set_output({
                "rag_query": rag_query[:200],
                "result_count": len(rag_results),
                "context_length": len(rag_context),
            })
            logger.info(f"[阶段2] RAG 返回数量: {len(rag_results)}, "
                        f"context长度={len(rag_context)}")
        return context

    def _extract_candidates(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段3: 候选景点/区域抽取 — 纯规则，不调用 LLM"""
        with trace_span(name="extract_candidates", level="STEP"):
            with self.timing.measure("extract_candidates", "agent_rule"):
                extract_candidates_from_guides(context)

            logger.info(
                f"[阶段3] 候选抽取: attractions={context.candidate_attractions}, "
                f"areas={context.candidate_areas}"
            )
        return context

    async def _collect_external_info(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段4: 外部信息补全 — 阶段内并行（景点+天气+酒店）"""
        with trace_span(name="collect_external_info", level="STEP") as step_span:
            all_start = perf_counter()
            logger.info("[阶段4] ========== 开始外部信息补全（阶段内并行） ==========")

            async def _collect_attractions():
                """景点搜索：优先使用候选景点，fallback 到旧城市级搜索"""
                start = perf_counter()
                if context.candidate_attractions and self.amap_tool:
                    logger.info(f"[阶段4.1] 使用候选景点搜索: {context.candidate_attractions}")
                    context.used_candidate_attractions = True
                    parts = []
                    for attraction in context.candidate_attractions:
                        query = f"请搜索{context.city}的{attraction}的具体信息。\n[TOOL_CALL:amap_maps_text_search:keywords={attraction},city={context.city}]"
                        try:
                            resp = await self.attraction_agent.arun(query)
                            parts.append(f"【{attraction}】\n{resp}")
                        except Exception as e:
                            logger.warning(f"[阶段4.1] 搜索候选景点{attraction}失败: {e}")
                            parts.append(f"【{attraction}】\n搜索失败: {str(e)}")
                    result = "\n\n".join(parts)
                else:
                    context.used_candidate_attractions = False
                    logger.info("[阶段4.1] Fallback 到旧城市级景点搜索")
                    attraction_query = f"请使用amap_maps_text_search工具搜索{context.city}的{context.preferences[0] if context.preferences else '景点'}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={context.preferences[0] if context.preferences else '景点'},city={context.city}]"
                    result = await self.attraction_agent.arun(attraction_query)

                elapsed = perf_counter() - start
                self.timing.add("attraction_search", elapsed, category="agent_search")
                context.attraction_info = result
                return result

            async def _collect_weather():
                """天气查询：只依赖 city，可与景点搜索并行"""
                start = perf_counter()
                weather_query = f"请查询{context.city}的天气信息"
                result = await self.weather_agent.arun(weather_query)
                elapsed = perf_counter() - start
                self.timing.add("weather_query", elapsed, category="agent_search")
                context.weather_info = result
                return result

            async def _collect_hotels():
                """酒店搜索：优先使用候选区域，fallback 到城市级搜索"""
                start = perf_counter()
                if context.candidate_areas:
                    logger.info(f"[阶段4.3] 使用候选区域搜索酒店: {context.candidate_areas}")
                    context.used_candidate_areas = True
                    parts = []
                    for area in context.candidate_areas:
                        # 关键修复: keywords 中必须包含区域名称，否则只是城市级搜索
                        query = (
                            f"请搜索{context.city}{area}附近的酒店。\n"
                            f"[TOOL_CALL:amap_maps_text_search:keywords={area} 酒店,city={context.city}]"
                        )
                        try:
                            resp = await self.hotel_agent.arun(query)
                            parts.append(f"【{area}】\n{resp}")
                        except Exception as e:
                            logger.warning(f"[阶段4.3] 搜索{area}酒店失败: {e}")
                    result = "\n\n".join(parts) if parts else ""
                    # 如果区域搜索全部失败，fallback
                    if not result.strip():
                        logger.info("[阶段4.3] 区域搜索全部失败，fallback 到城市级搜索")
                        context.used_candidate_areas = False
                        acc = context.request.accommodation or "舒适型"
                        hotel_query = (
                            f"请搜索{context.city}的{acc}酒店。\n"
                            f"[TOOL_CALL:amap_maps_text_search:keywords={acc} 酒店,city={context.city}]"
                        )
                        result = await self.hotel_agent.arun(hotel_query)
                else:
                    context.used_candidate_areas = False
                    logger.info("[阶段4.3] Fallback 到城市级酒店搜索")
                    acc = context.request.accommodation or "舒适型"
                    hotel_query = (
                        f"请搜索{context.city}的{acc}酒店。\n"
                        f"[TOOL_CALL:amap_maps_text_search:keywords={acc} 酒店,city={context.city}]"
                    )
                    result = await self.hotel_agent.arun(hotel_query)

                elapsed = perf_counter() - start
                self.timing.add("hotel_search", elapsed, category="agent_search")
                context.hotel_info = result
                return result

            # 阶段内并行
            await asyncio.gather(
                _collect_attractions(),
                _collect_weather(),
                _collect_hotels(),
            )

            all_elapsed = perf_counter() - all_start
            self.timing.add("external_info_wall_time", all_elapsed, category="agent_wall_time")
            logger.info(
                f"[阶段4] 外部信息补全完成，总耗时: {all_elapsed:.2f}秒 | "
                f"景点搜索使用候选景点: {context.used_candidate_attractions} | "
                f"酒店搜索使用候选区域: {context.used_candidate_areas} | "
                f"景点 fallback 到旧搜索: {not context.used_candidate_attractions} | "
                f"酒店 fallback 到旧搜索: {not context.used_candidate_areas}"
            )

            step_span.set_output({
                "used_candidate_attractions": context.used_candidate_attractions,
                "used_candidate_areas": context.used_candidate_areas,
                "attraction_info_length": len(context.attraction_info),
                "weather_info_length": len(context.weather_info),
                "hotel_info_length": len(context.hotel_info),
            })
        return context

    async def _generate_initial_plan(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段5: 初始行程生成 — LLM 生成结构化 TripPlan"""
        with trace_span(name="generate_initial_plan", level="STEP") as step_span:
            with self.timing.measure("planner_prompt_build", "agent_prepare"):
                planner_query = self._build_planner_query_v2(context)

            query_length = len(planner_query)
            logger.info(f"[阶段5] 初始行程生成开始, 查询长度: {query_length} 字符")
            step_span.set_input({"query_length": query_length})

            try:
                start_time = perf_counter()

                planner_response = await asyncio.wait_for(
                    self.planner_agent.arun(planner_query),
                    timeout=300
                )

                total_elapsed = perf_counter() - start_time
                self.timing.add(
                    "planner_generation_agent",
                    total_elapsed,
                    category="agent_llm",
                    metadata={
                        "query_length": query_length,
                        "response_length": len(planner_response),
                    }
                )
                logger.info(f"[阶段5] 规划专家响应完成，耗时: {total_elapsed:.2f}秒，"
                            f"raw_planner_response 长度: {len(planner_response)} 字符")

                context.raw_planner_response = planner_response

            except asyncio.TimeoutError:
                total_elapsed = perf_counter() - start_time
                self.timing.add("planner_generation_agent", total_elapsed, category="agent_llm",
                                metadata={"query_length": query_length, "error": "timeout"})
                raise TimeoutError(f"行程规划专家响应超时（已等待{total_elapsed:.0f}秒），请重试")
            except Exception as e:
                total_elapsed = perf_counter() - start_time
                self.timing.add("planner_generation_agent", total_elapsed, category="agent_llm",
                                metadata={"query_length": query_length, "error": str(e)})
                # Fallback: 使用已有 fallback 生成基础行程，仍走后续 normalize 阶段
                logger.warning(f"[阶段5] 初始行程生成失败，尝试 fallback: {e}")
                context.initial_plan = self._create_fallback_plan(context.request)
                context.raw_planner_response = ""
                logger.info("[阶段5] Fallback 行程已生成，继续走 normalize 流程")

            step_span.set_output({"response_length": len(context.raw_planner_response)})
        return context

    async def _normalize_plan(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段6: 标准化 — JSON 解析 + 坐标修正 + 字段补齐"""
        with trace_span(name="normalize_plan", level="STEP"):
            logger.info("[阶段6] normalize_plan 开始")

            # 如果 fallback 已在阶段5生成了 initial_plan，跳过 JSON 解析
            if context.initial_plan is None and context.raw_planner_response:
                with self.timing.measure("planner_response_parse", "agent_parse"):
                    trip_plan = self._parse_response(context.raw_planner_response, context.request)
                    context.initial_plan = trip_plan
            elif context.initial_plan is None:
                # 既没有 raw_planner_response 也没有 fallback，报错
                raise ValueError("阶段6: 无法标准化，既无 LLM 响应也无 fallback 行程")

            trip_plan = context.initial_plan

            # 坐标修正（从 router 移入此阶段，统一执行一次）
            with self.timing.measure("location_fix", "agent_fix"):
                logger.info("[阶段6] 开始修正景点坐标...")
                try:
                    trip_plan = await asyncio.to_thread(fix_trip_plan_locations, trip_plan)
                    context.location_fix_applied = True
                except Exception as e:
                    logger.warning(f"[阶段6] 坐标修正失败，使用原始坐标: {e}")
                    context.location_fix_applied = False
                logger.info(f"[阶段6] 坐标修正执行: {context.location_fix_applied}")

            context.normalized_plan = trip_plan
            logger.info(f"[阶段6] 标准化完成: {len(trip_plan.days)} 天, "
                        f"坐标修正={context.location_fix_applied}")
        return context

    def _evaluate_and_repair_plan(self, context: TripPlanningContext) -> TripPlanningContext:
        """阶段7: 行程风险识别与局部调整（RC-LRA）"""
        import os

        # 支持通过环境变量禁用风险模块（评估生成 baseline 时使用）
        if os.getenv("TRIP_RISK_REPAIR_ENABLED", "true").lower() != "true":
            logger.info("[阶段7] 风险识别模块已禁用 (TRIP_RISK_REPAIR_ENABLED=false)")
            context.risk_evaluation_enabled = False
            context.risks = []
            context.repair_log = []
            return context

        logger.info("[阶段7] 行程风险识别与局部调整开始")
        try:
            from core.trip_risk_repair import TripRiskRepairEngine
            engine = TripRiskRepairEngine()
            context = engine.evaluate_and_repair(context)
            logger.info(
                f"[阶段7] 风险识别与局部调整完成: "
                f"risks={len(context.risks)}, repairs={len(context.repair_log)}"
            )
            return context
        except Exception as e:
            logger.warning(f"[阶段7] 风险识别与局部调整失败，保留原始行程: {e}", exc_info=True)
            context.risks = []
            context.repair_log = []
            context.risk_evaluation_enabled = False
            return context

    def _finalize_plan(self, context: TripPlanningContext) -> TripPlan:
        """阶段8: 最终化 — 设置风险字段，返回最终 TripPlan"""
        plan = context.normalized_plan
        if plan is None:
            raise ValueError("标准化后的行程为空，无法最终化")

        # 用 risk_evaluation_enabled 判断，不是 risks 是否为空
        if context.risk_evaluation_enabled:
            plan.identified_risks = context.risks
            plan.risk_summary = {
                "enabled": True,
                "risk_count": len(context.risks),
                "high_count": sum(1 for r in context.risks if r.get("level") == "high"),
                "medium_count": sum(1 for r in context.risks if r.get("level") == "medium"),
                "low_count": sum(1 for r in context.risks if r.get("level") == "low"),
                "repaired_count": sum(1 for r in context.risks if r.get("repaired") is True),
                "unrepaired_count": sum(1 for r in context.risks if r.get("repaired") is not True),
                "score_before": context.risk_score_before.get("total_score"),
                "score_after": context.risk_score_after.get("total_score"),
                "message": ("已完成行程风险识别与局部调整。"
                            if context.risks
                            else "已完成行程风险识别，未发现明显风险。"),
            }
        else:
            plan.identified_risks = []
            plan.risk_summary = {"enabled": False, "message": "风险识别模块未启用或执行失败。"}

        # 阶段日志汇总
        logger.info(
            f"[阶段8] 行程最终化完成: "
            f"rag_query={context.rag_query[:100]}, "
            f"candidate_attractions={context.candidate_attractions}, "
            f"candidate_areas={context.candidate_areas}, "
            f"used_candidate_attractions={context.used_candidate_attractions}, "
            f"used_candidate_areas={context.used_candidate_areas}, "
            f"location_fix_applied={context.location_fix_applied}, "
            f"risk_enabled={context.risk_evaluation_enabled}, "
            f"risk_count={len(context.risks)}"
        )

        context.final_plan = plan
        return plan

    def _build_planner_query_v2(self, context: TripPlanningContext) -> str:
        """构建阶段式编排的 Planner prompt（分区结构，可配置上限 + 关键事实注入）"""

        def smart_truncate(text: str, max_len: int, name: str = "") -> str:
            """智能截断：尽量在句号/换行处断开，避免截断在半句话中间。"""
            if len(text) <= max_len:
                return text
            logger.warning(f"[Planner] {name} 长度超限({len(text)}>{max_len})，智能截断")
            # 在 max_len 附近找最近的句号或换行
            candidate = text[:max_len]
            for sep in ["\n", "。", "；", "，"]:
                idx = candidate.rfind(sep)
                if idx > max_len * 0.7:  # 至少保留70%
                    return candidate[: idx + 1] + f"\n...[{name}已截断，剩余{len(text) - idx}字符]"
            return candidate + f"\n...[{name}已截断]"

        req = context.request
        preferences_str = ', '.join(context.preferences) if context.preferences else '无'

        # 候选景点/区域（紧凑一行）
        candidate_section = ""
        if context.candidate_attractions:
            candidate_section = f"\n推荐候选景点: {', '.join(context.candidate_attractions)}"
        if context.candidate_areas:
            candidate_section += f"\n推荐住宿区域: {', '.join(context.candidate_areas)}"

        # 关键事实（从 RAG 提取的票价/免费/避坑，最优先展示）
        key_facts_text = build_key_facts_text(context)

        query = f"""请根据以下信息生成{req.city}的{req.travel_days}天旅行计划:

【用户需求】
- 城市: {req.city}
- 日期: {req.start_date} 至 {req.end_date}
- 天数: {req.travel_days}天
- 交通方式: {req.transportation}
- 住宿: {req.accommodation}
- 偏好: {preferences_str}
{f'- 额外要求: {req.free_text_input}' if req.free_text_input else ''}{candidate_section}

【关键事实 — 来自攻略，优先采用】
{smart_truncate(key_facts_text, settings.PLANNER_KEY_FACTS_MAX_CHARS, '关键事实')}

【攻略检索依据】
{smart_truncate(context.rag_context if context.rag_context else '暂无攻略参考', settings.PLANNER_RAG_MAX_CHARS, '攻略检索')}

【候选景点信息】
{smart_truncate(context.attraction_info, settings.PLANNER_ATTRACTION_MAX_CHARS, '景点信息')}

【候选住宿区域/酒店】
{smart_truncate(context.hotel_info, settings.PLANNER_HOTEL_MAX_CHARS, '酒店信息')}

【天气信息】
{smart_truncate(context.weather_info, settings.PLANNER_WEATHER_MAX_CHARS, '天气信息')}

【规划要求】
1. 优先使用候选景点和攻略中出现的景点，不要随意添加未检索到的景点
2. 酒店区域应尽量靠近主要游玩区域
3. 如果天气不佳（下雨/高温/寒冷），应减少户外景点或增加室内备选
4. 行程不要过度密集，考虑景点间交通时间
5. 返回完整的JSON格式数据，不要输出Markdown，不要输出解释
6. 景点的经纬度坐标要真实准确，来自候选景点信息中的坐标
7. 必须包含预算信息
8. 每天安排2-3个景点，每天必须包含早中晚三餐
9. 每天推荐一个具体的酒店
10. 门票价格以【关键事实】中的信息为准。关键事实中有"免费/不收费"标示的景点 ticket_price 必须为0。关键事实中未提及票价的景点才可从候选景点信息推断，无法确定的设为0
"""
        total_len = len(query)
        logger.info(f"[Planner] 查询总长度: {total_len} 字符")
        # 各区域实际长度明细
        logger.info(
            f"[Planner] 各区域实际长度: "
            f"关键事实={len(key_facts_text)} | "
            f"攻略依据={len(context.rag_context)} | "
            f"景点信息={len(context.attraction_info)} | "
            f"酒店信息={len(context.hotel_info)} | "
            f"天气信息={len(context.weather_info)}"
        )
        if total_len > 12000:
            logger.warning(f"[Planner] 查询总长度超过12000字符，可能触发token限制")

        return query



# ========== 兼容层（保留旧接口，但标记废弃） ==========

import warnings


def get_trip_planner_agent() -> TripPlannerAgent:
    """
    获取多智能体旅行规划系统实例（已废弃，建议直接实例化TripPlannerAgent）

    注意：此函数保留用于向后兼容，但不再返回单例，每次都返回新实例。
    """
    warnings.warn(
        "get_trip_planner_agent() 已废弃，请直接实例化 TripPlannerAgent(mcp_tool=...)",
        DeprecationWarning,
        stacklevel=2
    )

    # 获取MCP工具单例
    try:
        mcp_tool = get_amap_mcp_tool()
    except Exception:
        mcp_tool = None

    # 返回新实例（不再是单例）
    return TripPlannerAgent(mcp_tool=mcp_tool)

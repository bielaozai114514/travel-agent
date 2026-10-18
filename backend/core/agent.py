import json
from typing import List, AsyncGenerator, Optional, Dict, Any, Tuple

from settings import settings
from core.logger import logger
from schemas.llm import Message
from core.EsAgent import EsAgentLLM, SimpleAgent, ToolRegistry
from core.EsAgent.tools import TimeTool, MCPTool
from core.EsAgent.tools.builtin import GuideSearchTool
from core.context_manager import get_context_manager


class EsAgentService:
    def __init__(self):
        self.llm = self._create_esagent_llm()
        self.tool_registry = self._create_tool_registry()
        self.base_system_prompt = self._get_base_system_prompt()
        self.agent = self._create_simple_agent()
        # 初始化上下文管理器
        self.context_manager = get_context_manager(
            max_tokens=settings.CONTEXT_MAX_TOKENS if hasattr(settings, 'CONTEXT_MAX_TOKENS') else None
        )

    def _get_base_system_prompt(self) -> str:
        """获取基础系统提示词（不含行程上下文）"""
        return """你是一个专业的旅游助手。

【核心工作规则 - 必须严格遵守】
1. 收到用户的旅游相关问题后，**第一步必须调用对应工具**，绝对不能直接回答！
2. 天气查询 → [TOOL_CALL:amap_maps_weather:city=城市名]
3. 景点/美食/酒店/交通等旅游信息查询 → **必须先调用攻略搜索**：[TOOL_CALL:guide_search:query=搜索关键词]
4. 如果 guide_search 未找到相关攻略，再用高德地图工具补充：[TOOL_CALL:amap_maps_text_search:keywords=关键词,city=城市名]
5. **严禁编造信息，所有回答必须基于工具返回的真实数据**

【工具调用格式】
- 攻略搜索：[TOOL_CALL:guide_search:query=搜索关键词]
- 景点搜索：[TOOL_CALL:amap_maps_text_search:keywords=景点,city=城市名]
- 美食搜索：[TOOL_CALL:amap_maps_text_search:keywords=美食,city=城市名]
- 酒店搜索：[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]
- 天气查询：[TOOL_CALL:amap_maps_weather:city=城市名]

【示例】
用户：杭州这几天天气怎么样
你的回答：[TOOL_CALL:amap_maps_weather:city=杭州]

用户：告诉我一些关于六和塔公园的信息
你的回答（只有这一行，不要其他内容）：[TOOL_CALL:guide_search:query=六和塔公园]

用户：杭州有什么好玩的地方
你的回答（只有这一行，不要其他内容）：[TOOL_CALL:guide_search:query=杭州旅游攻略]

现在开始工作！记住：先调用工具，不要直接回答！"""

    def _build_trip_context(self, trip_plan: Optional[Dict[str, Any]]) -> str:
        """
        构建行程上下文摘要

        Args:
            trip_plan: 行程计划数据

        Returns:
            行程摘要字符串，如果没有行程则返回空字符串
        """
        if not trip_plan:
            return ""

        try:
            city = trip_plan.get("city", "未知城市")
            start_date = trip_plan.get("start_date", "")
            end_date = trip_plan.get("end_date", "")
            days = trip_plan.get("days", [])

            # 构建每日摘要
            day_summaries = []
            for i, day in enumerate(days[:5]):  # 最多显示5天
                day_index = day.get("day_index", i)
                attractions = day.get("attractions", [])
                attr_names = [a.get("name", "") for a in attractions[:3] if a.get("name")]
                if attr_names:
                    day_summaries.append(f"- 第{day_index + 1}天：{' → '.join(attr_names)}")

            # 预算摘要
            budget = trip_plan.get("budget", {})
            budget_summary = ""
            if budget and budget.get("total"):
                budget_summary = f"预算概要：约¥{budget['total']}/人"

            # 组合完整摘要
            context_parts = [
                "【当前关联行程】",
                f"城市：{city}",
            ]

            if start_date and end_date:
                context_parts.append(f"日期：{start_date} 至 {end_date}")
            if days:
                context_parts.append(f"天数：{len(days)}天")
            if day_summaries:
                context_parts.append("每日概要：")
                context_parts.extend(day_summaries)
            if budget_summary:
                context_parts.append(budget_summary)

            context_parts.append("")  # 空行分隔

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"构建行程摘要失败: {e}")
            return ""

    def _create_simple_agent_with_trip(self, trip_plan: Optional[Dict[str, Any]] = None) -> SimpleAgent:
        """
        创建带行程上下文的 SimpleAgent

        Args:
            trip_plan: 行程计划数据（可选）
        """
        # 构建完整的 system prompt
        trip_context = self._build_trip_context(trip_plan)
        full_system_prompt = trip_context + self.base_system_prompt

        logger.debug("创建带行程上下文的 Agent，行程上下文长度: %d", len(trip_context))

        agent = SimpleAgent(
            name="TravelAssistant",
            llm=self.llm,
            system_prompt=full_system_prompt,
            tool_registry=self.tool_registry,
            enable_tool_calling=True
        )

        # 添加工具（与原方法相同）
        self._add_tools_to_agent(agent)

        return agent

    def _add_tools_to_agent(self, agent: SimpleAgent):
        """给 Agent 添加工具"""
        # 添加时间工具
        logger.info("正在添加时间工具...")
        time_tool = TimeTool()
        agent.add_tool(time_tool)
        logger.info("时间工具已添加")

        # 添加高德地图MCP工具
        try:
            logger.info("正在初始化高德地图MCP工具...")
            if settings.AMAP_API_KEY:
                logger.debug("AMAP_API_KEY 已配置")
                amap_tool = MCPTool.get_or_create(
                    name="amap",
                    description="高德地图服务，支持POI搜索、天气查询、路线规划、地理编码等功能",
                    server_command=["uvx", "amap-mcp-server"],
                    env={"AMAP_MAPS_API_KEY": settings.AMAP_API_KEY},
                    auto_expand=True
                )
                logger.debug("MCPTool 单例获取完成，正在添加到 agent...")
                agent.add_tool(amap_tool)
                logger.info("高德地图MCP工具已添加到对话Agent")
            else:
                logger.warning("未配置高德地图API Key，高德地图工具不可用")
        except Exception as e:
            logger.warning(f"高德地图MCP工具初始化失败: {e}", exc_info=True)

        # 添加攻略搜索工具
        try:
            logger.info("正在添加攻略搜索工具...")
            guide_search_tool = GuideSearchTool()
            agent.add_tool(guide_search_tool)
            logger.info("攻略搜索工具已添加到对话Agent")
        except Exception as e:
            logger.warning(f"攻略搜索工具初始化失败: {e}", exc_info=True)

        # 列出所有已注册的工具
        if agent.tool_registry:
            all_tools = agent.tool_registry.list_tools()
            logger.info(f"所有已注册的工具 ({len(all_tools)} 个): {', '.join(all_tools)}")

        logger.info("Agent 初始化完成!")

    def _create_esagent_llm(self) -> EsAgentLLM:
        """使用分层配置创建 LLM"""
        config = settings.get_agent_config("chat")
        return EsAgentLLM(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=config.timeout,
        )

    def _create_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        return registry

    def _create_simple_agent(self) -> SimpleAgent:
        """创建基础 SimpleAgent（不带行程上下文）"""
        logger.info("开始创建 SimpleAgent...")
        agent = SimpleAgent(
            name="TravelAssistant",
            llm=self.llm,
            system_prompt=self.base_system_prompt,
            tool_registry=self.tool_registry,
            enable_tool_calling=True
        )
        logger.info("SimpleAgent 创建完成")

        # 添加工具
        self._add_tools_to_agent(agent)
        return agent
    
    def convert_messages(self, messages: List[Message]) -> List[dict]:
        esagent_messages = []

        for msg in messages:
            esagent_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return esagent_messages

    def _split_history_and_current(self, messages: List[Message]) -> Tuple[List[Message], str]:
        """
        分离历史消息和当前用户输入

        Returns:
            (历史消息列表, 当前用户输入)
        """
        if not messages:
            return [], ""

        # 找到最后一条用户消息作为当前输入
        last_user_idx = -1
        for i, msg in enumerate(reversed(messages)):
            if msg.role == "user":
                last_user_idx = len(messages) - 1 - i
                break

        if last_user_idx == -1:
            # 没有用户消息，全部作为历史
            return messages, ""

        current_input = messages[last_user_idx].content
        history_messages = messages[:last_user_idx]

        return history_messages, current_input

    def _truncate_history_safely(
        self,
        messages: List[dict],
        trip_context_str: Optional[str]
    ) -> List[dict]:
        """
        安全地截断历史消息（基于Token估算）

        Args:
            messages: 历史消息列表
            trip_context_str: 行程上下文字符串

        Returns:
            截断后的消息列表
        """
        if not messages:
            return []

        # 估算基础Token使用量
        base_tokens = self.context_manager._estimate_tokens(self.base_system_prompt)
        if trip_context_str:
            base_tokens += self.context_manager._estimate_tokens(trip_context_str)

        # 预留给当前输入和工具的Token
        reserved_tokens = 2000
        max_history_tokens = self.context_manager.max_tokens - base_tokens - reserved_tokens

        if max_history_tokens < 500:
            max_history_tokens = 500

        # 从后往前累加
        selected = []
        total_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.context_manager._estimate_tokens(msg.get("content", ""))
            if total_tokens + msg_tokens > max_history_tokens:
                if not selected:
                    # 至少保留最后一条消息，截断内容
                    truncated_content = self.context_manager._truncate_content(
                        msg.get("content", ""),
                        max_history_tokens
                    )
                    selected.append({
                        "role": msg.get("role", "user"),
                        "content": truncated_content
                    })
                logger.info(f"历史消息已截断: 保留{len(selected)}/{len(messages)}条")
                break
            selected.append(msg)
            total_tokens += msg_tokens

        # 恢复原始顺序
        selected.reverse()
        return selected
    
    async def generate_stream(
        self,
        messages: List[Message],
        trip_plan: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        流式生成回复（使用上下文管理器确保稳定性）

        Args:
            messages: 消息列表
            trip_plan: 可选的行程计划数据，用于注入上下文
        """
        try:
            # 分离历史消息和当前输入
            history_messages, current_input = self._split_history_and_current(messages)

            # 构建行程上下文字符串
            trip_context_str = None
            if trip_plan:
                trip_context_str = self._build_trip_context(trip_plan)

            # 使用上下文管理器构建安全的上下文
            # 注意：SimpleAgent 内部会自己构建消息列表，这里我们做预处理验证
            validation_result = self.context_manager._validate_and_clean_messages(history_messages)

            if validation_result.issues:
                logger.warning(f"历史消息存在问题: {validation_result.issues}")

            if validation_result.warnings:
                logger.debug(f"历史消息警告: {validation_result.warnings}")

            # 转换为 esagent 格式的消息
            if validation_result.fixed_messages:
                esagent_messages = validation_result.fixed_messages
            else:
                esagent_messages = self.convert_messages(history_messages)

            # 估算并截断历史消息（如果需要）
            esagent_messages = self._truncate_history_safely(
                esagent_messages,
                trip_context_str
            )

            # 根据是否有行程数据选择使用哪个 agent
            if trip_plan:
                agent = self._create_simple_agent_with_trip(trip_plan)
            else:
                agent = self.agent

            if current_input:
                full_response = ""
                for chunk in agent.stream_run(
                    current_input,
                    external_history=esagent_messages,
                    save_to_history=False,
                    max_tool_iterations=5
                ):
                    if isinstance(chunk, dict):
                        line = json.dumps(chunk, ensure_ascii=False) + "\n"
                        yield line.encode("utf-8")

                        if chunk.get("type") == "thinking_content":
                            full_response += chunk.get("data", "")
                        elif chunk.get("type") == "content":
                            full_response += chunk.get("data", "")
                    else:
                        full_response += chunk
                        line = json.dumps({"type": "content", "data": chunk}, ensure_ascii=False) + "\n"
                        yield line.encode("utf-8")
            else:
                # 构建完整的消息列表用于直接 LLM 调用
                full_system_prompt = self.context_manager._build_full_system_prompt(
                    self.base_system_prompt,
                    trip_context_str
                )
                direct_messages = [{"role": "system", "content": full_system_prompt}]
                direct_messages.extend(esagent_messages)

                for chunk in self.llm.stream_invoke(direct_messages):
                    line = json.dumps({"type": "content", "data": chunk}, ensure_ascii=False) + "\n"
                    yield line.encode("utf-8")

            done_line = json.dumps({"type": "done"}, ensure_ascii=False) + "\n"
            yield done_line.encode("utf-8")
        except Exception as e:
            logger.error(f"生成出错: {str(e)}", exc_info=True)
            error_line = json.dumps({"type": "error", "data": f"生成出错: {str(e)}"}, ensure_ascii=False) + "\n"
            yield error_line.encode("utf-8")
    
    async def generate_non_stream(
        self,
        messages: List[Message],
        trip_plan: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        非流式生成回复（使用上下文管理器确保稳定性）

        Args:
            messages: 消息列表
            trip_plan: 可选的行程计划数据，用于注入上下文
        """
        try:
            # 分离历史消息和当前输入
            history_messages, current_input = self._split_history_and_current(messages)

            # 构建行程上下文字符串
            trip_context_str = None
            if trip_plan:
                trip_context_str = self._build_trip_context(trip_plan)

            # 使用上下文管理器验证和清洗消息
            validation_result = self.context_manager._validate_and_clean_messages(history_messages)

            if validation_result.issues:
                logger.warning(f"历史消息存在问题: {validation_result.issues}")

            # 转换为 esagent 格式的消息
            if validation_result.fixed_messages:
                esagent_messages = validation_result.fixed_messages
            else:
                esagent_messages = self.convert_messages(history_messages)

            # 安全截断
            esagent_messages = self._truncate_history_safely(esagent_messages, trip_context_str)

            # 根据是否有行程数据选择使用哪个 agent
            if trip_plan:
                agent = self._create_simple_agent_with_trip(trip_plan)
            else:
                agent = self.agent

            if current_input:
                return agent.run(
                    current_input,
                    external_history=esagent_messages,
                    save_to_history=False,
                    max_tool_iterations=5
                )
            else:
                # 构建完整的消息列表用于直接 LLM 调用
                full_system_prompt = self.context_manager._build_full_system_prompt(
                    self.base_system_prompt,
                    trip_context_str
                )
                direct_messages = [{"role": "system", "content": full_system_prompt}]
                direct_messages.extend(esagent_messages)
                return self.llm.invoke(direct_messages)
        except Exception as e:
            logger.error(f"非流式生成出错: {e}", exc_info=True)
            raise e


_esagent_service_instance: Optional[EsAgentService] = None


def get_esagent_service() -> EsAgentService:
    global _esagent_service_instance
    if _esagent_service_instance is None:
        _esagent_service_instance = EsAgentService()
    return _esagent_service_instance

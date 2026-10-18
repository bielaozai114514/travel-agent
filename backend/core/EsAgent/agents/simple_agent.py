"""简单Agent实现 - 基于OpenAI原生API"""

import asyncio
from typing import Optional, Iterator, List, Union
import re

from ..core.agent import Agent
from ..core.llm import EsAgentLLM
from ..core.config import Config
from ..core.message import Message
from ..tools.registry import ToolRegistry
from ..tools.base import Tool

from core.logger import logger


class SimpleAgent(Agent):
    """简单的对话Agent，支持工具调用"""

    def __init__(
        self,
        name: str,
        llm: EsAgentLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional[ToolRegistry] = None,
        enable_tool_calling: bool = True,
    ):
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling or tool_registry is not None
        if self.enable_tool_calling:
            logger.info(f"{name} 初始化完成，工具调用: 启用")

    def _has_available_tools(self) -> bool:
        """检查当前 Agent 是否真的有可调用工具。"""
        return bool(
            self.enable_tool_calling
            and self.tool_registry
            and len(self.tool_registry.list_tools()) > 0
        )

    def _build_user_content(self, input_text: str) -> str:
        """仅在有工具时追加工具使用提醒，避免干扰纯 JSON/分类任务。"""
        if not self._has_available_tools():
            return input_text

        reminder_text = "\n\n【重要提醒】：如果这是旅游相关问题，必须先调用 guide_search 工具搜索攻略，不要直接回答！"
        return input_text + reminder_text

    def run(
        self,
        input_text: str,
        external_history: Optional[List[Union[Message, dict]]] = None,
        save_to_history: bool = False,
        max_tool_iterations: int = 5,
        **kwargs
    ) -> str:
        """
        运行简单Agent（无状态化）

        Args:
            input_text: 用户输入
            external_history: 外部传入的历史记录，可以是Message对象列表或字典列表
            save_to_history: 是否保存到内部历史记录（已废弃，Agent无状态化）
            max_tool_iterations: 最大工具调用次数，默认3次
            **kwargs: 其他参数

        Returns:
            Agent响应
        """
        messages = []

        if self.system_prompt:
            enhanced_prompt = self._get_enhanced_system_prompt()
            messages.append({"role": "system", "content": enhanced_prompt})

        history_messages = self._merge_history(external_history)
        messages.extend(history_messages)

        has_tools = self._has_available_tools()
        messages.append({"role": "user", "content": self._build_user_content(input_text)})

        if not has_tools:
            response = self.llm.invoke(messages, **kwargs)
            # save_to_history 已废弃，不再保存到内部历史
            return response

        return self._run_with_tools(messages, input_text, save_to_history, max_tool_iterations, **kwargs)

    def _run_with_tools(
        self,
        messages: list,
        input_text: str,
        save_to_history: bool,
        max_tool_iterations: int,
        **kwargs
    ) -> str:
        """
        运行代理，处理输入文本并返回响应(带工具调用)
        """
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            logger.debug(f"第 {current_iteration + 1}/{max_tool_iterations} 轮迭代开始")
            response = self.llm.invoke(messages, **kwargs)

            logger.debug(f"{self.name} 第{current_iteration+1}轮调用响应完成，响应长度: {len(response)}")
            logger.debug(f"LLM 响应内容:\n{response}")

            tool_calls = self._parse_tool_call(response)
            if tool_calls:
                logger.debug(f"检测到 {len(tool_calls)} 个工具调用")
                for i, call in enumerate(tool_calls):
                    logger.debug(f"   工具 {i+1}: name={call['tool_name']}, params={call['parameters']}")

                tool_results = []
                clean_response = response

                for call in tool_calls:
                    logger.debug(f"正在执行工具: {call['tool_name']}")
                    try:
                        result = self._execute_tool_call(call['tool_name'], call['parameters'])
                        logger.debug(f"工具执行完成，结果长度: {len(result)}")
                        logger.debug(f"工具执行结果:\n{result}")
                        tool_results.append(result)
                    except Exception as e:
                        error_msg = f"工具执行失败: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        tool_results.append(error_msg)

                    clean_response = clean_response.replace(call['original'], "")

                logger.debug(f"清理后的响应: '{clean_response}'")
                messages.append({"role": "assistant", "content": clean_response})

                tool_results_text = "\n\n".join(tool_results)
                user_msg = f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"
                logger.debug(f"添加用户消息（工具结果），长度: {len(user_msg)}")
                messages.append({"role": "user", "content": user_msg})

                current_iteration += 1
                logger.debug(f"进入下一轮迭代，current_iteration={current_iteration}")
                continue

            logger.debug("未检测到工具调用，使用此响应作为最终回答")
            final_response = response
            break

        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm.invoke(messages, **kwargs)

        # save_to_history 已废弃，不再保存到内部历史
        logger.info(f"{self.name} 响应完成")
        return final_response

    def _get_enhanced_system_prompt(self) -> str:
        """获取增强系统提示（工具说明按需构建，节省token）"""
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        if not self.enable_tool_calling or self.tool_registry is None:
            return base_prompt

        tools = self.tool_registry.list_tools()
        if not tools:
            return base_prompt

        # 如果基础提示已经包含了工具说明（比如 EsAgentService 的提示），就不再重复添加
        if "TOOL_CALL" in base_prompt or "工具调用" in base_prompt:
            return base_prompt

        # 简化的工具说明，只列工具名和简要描述
        tools_description = self._get_short_tools_description()

        tools_section = "\n\n## 工具使用说明\n"
        tools_section += "优先使用工具获取实时信息或执行操作。\n\n"
        tools_section += "## 可用工具\n"
        tools_section += tools_description + "\n"
        tools_section += "\n## 调用格式\n"
        tools_section += "`[TOOL_CALL:tool_name:parameters]` 或 `[TOOL_CALL:tool_name]`\n"
        tools_section += "参数示例: `[TOOL_CALL:search:query=杭州景点]`\n"

        return base_prompt + tools_section

    def _get_short_tools_description(self) -> str:
        """简化的工具说明，节省token"""
        tools = self.tool_registry.list_tools()
        if not tools:
            return "暂无可用工具"

        parts = []
        for tool_name in tools:
            tool = self.tool_registry.get_tool(tool_name)
            if tool:
                desc = tool.description[:60] if tool.description else "无描述"
                if len(tool.description) > 60:
                    desc += "..."
                parts.append(f"- {tool_name}: {desc}")

        return "\n".join(parts)

    def _parse_tool_call(self, text: str) -> List[dict]:
        """
        健壮的工具调用解析器
        支持多种格式变体：
        - [TOOL_CALL:tool_name:params]
        - [TOOL_CALL: tool_name : params] (带空格)
        - [TOOL_CALL:tool_name] (无参数)
        - [ToolCall:tool_name:params] (大小写不同)
        - 【TOOL_CALL:tool_name:params】(中文括号)
        - `[TOOL_CALL:tool_name:params]` (markdown代码)
        """
        tool_calls = []
        if not text or not text.strip():
            return tool_calls

        # 获取可用工具列表用于验证（如果有）
        available_tools = set()
        if self.tool_registry:
            available_tools = set(self.tool_registry.list_tools())

        # 阶段1: 归一化文本
        normalized = text
        # 替换中文括号
        normalized = normalized.replace('【', '[').replace('】', ']')
        # 移除 markdown 代码标记
        normalized = re.sub(r'`([^`]+)`', r'\1', normalized)
        # 移除可能的 markdown 加粗
        normalized = re.sub(r'\*\*([^*]+)\*\*', r'\1', normalized)

        # 阶段2: 尝试多种解析策略（从严格到宽松）
        parse_strategies = [
            # 策略1: 严格标准格式 [TOOL_CALL:name:params]
            (r'\[TOOL_CALL:([^:\]]+?):([^\]]+?)\]', True),
            # 策略2: 标准格式但允许空格 [TOOL_CALL: name : params ]
            (r'\[TOOL_CALL\s*:\s*([^:\]]+?)\s*:\s*([^\]]+?)\s*\]', True),
            # 策略3: 无参数格式 [TOOL_CALL:name]
            (r'\[TOOL_CALL\s*:\s*([^:\]]+?)\s*\]', False),
            # 策略4: 大小写不敏感格式 [ToolCall:name:params]
            (r'\[(?:TOOL_CALL|ToolCall|tool_call)\s*:\s*([^:\]]+?)\s*:\s*([^\]]+?)\s*\]', True),
            # 策略5: 大小写不敏感无参数
            (r'\[(?:TOOL_CALL|ToolCall|tool_call)\s*:\s*([^:\]]+?)\s*\]', False),
        ]

        # 记录已匹配的原始字符串，避免重复
        matched_originals = set()

        for pattern, has_params in parse_strategies:
            matches = re.finditer(pattern, normalized, re.IGNORECASE)
            for match in matches:
                original = match.group(0)

                # 避免重复匹配
                if original in matched_originals:
                    continue

                tool_name = match.group(1).strip()
                parameters = match.group(2).strip() if has_params and len(match.groups()) > 1 else ''

                # 如果有可用工具列表，验证工具名是否存在
                if available_tools and tool_name not in available_tools:
                    # 尝试模糊匹配工具名
                    matched_tool = self._fuzzy_match_tool(tool_name, available_tools)
                    if matched_tool:
                        logger.debug(f"工具名模糊匹配: '{tool_name}' -> '{matched_tool}'")
                        tool_name = matched_tool
                    else:
                        logger.debug(f"跳过未知工具: {tool_name}")
                        continue

                tool_calls.append({
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'original': original
                })
                matched_originals.add(original)

        # 阶段3: 如果还没找到，尝试更宽松的策略
        if not tool_calls and ('tool' in normalized.lower() or '调用' in normalized):
            tool_calls = self._parse_fallback(normalized, available_tools)

        # 去重（基于工具名和参数）
        seen = set()
        unique_calls = []
        for call in tool_calls:
            key = (call['tool_name'], call['parameters'])
            if key not in seen:
                seen.add(key)
                unique_calls.append(call)

        if unique_calls:
            logger.debug(f"成功解析 {len(unique_calls)} 个工具调用")
            for i, call in enumerate(unique_calls):
                logger.debug(f"  工具 {i+1}: {call['tool_name']}, params={call['parameters'][:50]}...")

        return unique_calls

    def _fuzzy_match_tool(self, tool_name: str, available_tools: set) -> Optional[str]:
        """模糊匹配工具名称"""
        if not tool_name or not available_tools:
            return None

        tool_name_lower = tool_name.lower()

        # 策略1: 精确匹配（大小写不敏感）
        for available in available_tools:
            if available.lower() == tool_name_lower:
                return available

        # 策略2: 包含匹配 - 收集所有匹配，选择最长的（最精确）
        candidates = []
        for available in available_tools:
            avail_lower = available.lower()
            if tool_name_lower in avail_lower or avail_lower in tool_name_lower:
                candidates.append(available)

        if candidates:
            # 按长度从长到短排序，优先选择更长、更精确的匹配
            candidates.sort(key=lambda x: len(x), reverse=True)
            return candidates[0]

        # 策略3: 编辑距离匹配（简单实现）
        best_match = None
        best_score = 0.0
        for available in available_tools:
            score = self._string_similarity(tool_name_lower, available.lower())
            if score > best_score and score > 0.5:
                best_score = score
                best_match = available

        return best_match

    def _string_similarity(self, s1: str, s2: str) -> float:
        """简单的字符串相似度计算（基于共同字符）"""
        if not s1 or not s2:
            return 0.0

        set1 = set(s1)
        set2 = set(s2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _parse_fallback(self, text: str, available_tools: set) -> List[dict]:
        """兜底解析策略：尝试从自然语言描述中提取工具调用"""
        tool_calls = []

        # 尝试提取工具名和可能的参数
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()

            # 检查是否有可用工具被提及
            for tool_name in available_tools:
                if tool_name.lower() in line_lower:
                    # 尝试提取参数
                    params = ''
                    # 查找引号中的内容作为参数
                    quote_matches = re.findall(r'["\']([^"\']+)["\']', line)
                    if quote_matches:
                        params = quote_matches[-1]
                    else:
                        # 尝试提取冒号或等号后的内容
                        param_match = re.search(r'[:=]\s*(.+?)(?:\s|$)', line)
                        if param_match:
                            params = param_match.group(1).strip()

                    # 构造一个原始标记（用于后续清理）
                    original = f"[TOOL_CALL:{tool_name}:{params}]" if params else f"[TOOL_CALL:{tool_name}]"

                    tool_calls.append({
                        'tool_name': tool_name,
                        'parameters': params,
                        'original': original
                    })
                    logger.debug(f"兜底解析找到工具调用: {tool_name}")
                    break

        return tool_calls

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
        """智能解析工具参数"""
        import json
        param_dict = {}

        if parameters.strip().startswith('{'):
            try:
                param_dict = json.loads(parameters)
                param_dict = self._convert_parameter_types(tool_name, param_dict)
                return param_dict
            except json.JSONDecodeError:
                pass

        if '=' in parameters:
            if ',' in parameters:
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                key, value = parameters.split('=', 1)
                param_dict[key.strip()] = value.strip()

            param_dict = self._convert_parameter_types(tool_name, param_dict)

            if 'action' not in param_dict:
                param_dict = self._infer_action(tool_name, param_dict)
        elif parameters.strip():
            param_dict = self._infer_simple_parameters(tool_name, parameters)
        else:
            param_dict = {}

        return param_dict

    def _convert_parameter_types(self, tool_name: str, param_dict: dict) -> dict:
        """根据工具的参数定义转换参数类型"""
        if not self.tool_registry:
            return param_dict

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return param_dict

        try:
            tool_params = tool.get_parameters()
        except:
            return param_dict

        param_types = {}
        for param in tool_params:
            param_types[param.name] = param.type

        converted_dict = {}
        for key, value in param_dict.items():
            if key in param_types:
                param_type = param_types[key]
                try:
                    if param_type == 'number' or param_type == 'integer':
                        if isinstance(value, str):
                            converted_dict[key] = float(value) if param_type == 'number' else int(value)
                        else:
                            converted_dict[key] = value
                    elif param_type == 'boolean':
                        if isinstance(value, str):
                            converted_dict[key] = value.lower() in ('true', '1', 'yes')
                        else:
                            converted_dict[key] = bool(value)
                    else:
                        converted_dict[key] = value
                except (ValueError, TypeError):
                    converted_dict[key] = value
            else:
                converted_dict[key] = value

        return converted_dict

    def _infer_action(self, tool_name: str, param_dict: dict) -> dict:
        """根据工具类型和参数推断action"""
        if tool_name == 'memory':
            if 'recall' in param_dict:
                param_dict['action'] = 'search'
                param_dict['query'] = param_dict.pop('recall')
            elif 'store' in param_dict:
                param_dict['action'] = 'add'
                param_dict['content'] = param_dict.pop('store')
            elif 'query' in param_dict:
                param_dict['action'] = 'search'
            elif 'content' in param_dict:
                param_dict['action'] = 'add'
        elif tool_name == 'rag':
            if 'search' in param_dict:
                param_dict['action'] = 'search'
                param_dict['query'] = param_dict.pop('search')
            elif 'query' in param_dict:
                param_dict['action'] = 'search'
            elif 'text' in param_dict:
                param_dict['action'] = 'add_text'

        return param_dict

    def _infer_simple_parameters(self, tool_name: str, parameters: str) -> dict:
        """为简单参数推断完整的参数字典"""
        tool_registry = self.tool_registry
        if tool_registry:
            tool = tool_registry.get_tool(tool_name)
            if tool:
                try:
                    tool_params = tool.get_parameters()
                    if len(tool_params) == 1:
                        param_name = tool_params[0].name
                        return {param_name: parameters}
                except:
                    pass

        if tool_name == 'rag':
            return {'action': 'search', 'query': parameters}
        elif tool_name == 'memory':
            return {'action': 'search', 'query': parameters}
        elif tool_name == 'search':
            return {'query': parameters}
        else:
            return {'input': parameters}

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用"""
        logger.debug(f"[_execute_tool_call] 开始执行，tool_name={tool_name}, raw_params={parameters}")

        if not self.tool_registry:
            logger.error("[_execute_tool_call] 错误: 未配置工具注册表")
            return f"❌ 错误:未配置工具注册表"

        logger.debug(f"[_execute_tool_call] 正在解析参数...")
        param_dict = self._parse_tool_parameters(tool_name, parameters)
        logger.debug(f"[_execute_tool_call] 解析后的参数: {param_dict}")

        logger.debug(f"[_execute_tool_call] 正在从注册表获取工具 '{tool_name}'...")
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            available_tools = self.tool_registry.list_tools()
            logger.error(f"[_execute_tool_call] 错误: 未找到工具 '{tool_name}'，可用工具: {available_tools}")
            return f"❌ 错误:未找到工具 '{tool_name}'，可用工具: {available_tools}"

        logger.debug(f"[_execute_tool_call] 找到工具: {tool.name}，正在运行...")
        try:
            result = tool.run(param_dict)
            logger.debug(f"[_execute_tool_call] 工具运行成功，结果长度: {len(result)}")
            return result
        except Exception as e:
            logger.error(f"[_execute_tool_call] 工具运行异常: {e}", exc_info=True)
            return f"❌ 工具 {tool_name} 执行异常: {str(e)}"

    async def _aexecute_tool_call(self, tool_name: str, parameters: str) -> str:
        """异步执行工具调用（优先使用工具的 arun() 方法，否则在线程池中运行同步工具）"""
        import asyncio

        logger.debug(f"[_aexecute_tool_call] 开始执行，tool_name={tool_name}, raw_params={parameters}")

        if not self.tool_registry:
            logger.error("[_aexecute_tool_call] 错误: 未配置工具注册表")
            return f"❌ 错误:未配置工具注册表"

        logger.debug(f"[_aexecute_tool_call] 正在解析参数...")
        param_dict = self._parse_tool_parameters(tool_name, parameters)
        logger.debug(f"[_aexecute_tool_call] 解析后的参数: {param_dict}")

        logger.debug(f"[_aexecute_tool_call] 正在从注册表获取工具 '{tool_name}'...")
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            available_tools = self.tool_registry.list_tools()
            logger.error(f"[_aexecute_tool_call] 错误: 未找到工具 '{tool_name}'，可用工具: {available_tools}")
            return f"❌ 错误:未找到工具 '{tool_name}'，可用工具: {available_tools}"

        logger.debug(f"[_aexecute_tool_call] 找到工具: {tool.name}")

        # 优先使用异步方法 arun()
        if hasattr(tool, 'arun') and callable(getattr(tool, 'arun')):
            logger.debug(f"[_aexecute_tool_call] 使用异步方法 arun()")
            try:
                result = await tool.arun(param_dict)
                logger.debug(f"[_aexecute_tool_call] 异步工具运行成功，结果长度: {len(result)}")
                return result
            except Exception as e:
                logger.error(f"[_aexecute_tool_call] 异步工具运行异常: {e}", exc_info=True)
                return f"❌ 工具 {tool_name} 执行异常: {str(e)}"
        else:
            # 降级到线程池运行同步方法
            logger.debug(f"[_aexecute_tool_call] 工具无 arun() 方法，使用线程池运行同步 run()")
            return await asyncio.to_thread(self._execute_tool_call, tool_name, parameters)

    async def _arun_with_tools(
        self,
        messages: list,
        input_text: str,
        save_to_history: bool,
        max_tool_iterations: int,
        **kwargs
    ) -> str:
        """
        异步运行代理，处理输入文本并返回响应(带工具调用)
        """
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            logger.debug(f"[异步] 第 {current_iteration + 1}/{max_tool_iterations} 轮迭代开始")
            response = await self.llm.ainvoke(messages, **kwargs)

            logger.debug(f"[异步] {self.name} 第{current_iteration+1}轮调用响应完成，响应长度: {len(response)}")
            logger.debug(f"[异步] LLM 响应内容:\n{response}")

            tool_calls = self._parse_tool_call(response)
            if tool_calls:
                logger.debug(f"[异步] 检测到 {len(tool_calls)} 个工具调用")
                for i, call in enumerate(tool_calls):
                    logger.debug(f"   工具 {i+1}: name={call['tool_name']}, params={call['parameters']}")

                tool_results = []
                clean_response = response

                # 并发执行所有工具调用
                logger.debug(f"[异步] 并发执行 {len(tool_calls)} 个工具...")

                async def execute_single_tool(call):
                    """执行单个工具的辅助函数"""
                    logger.debug(f"   启动工具: {call['tool_name']}")
                    try:
                        result = await self._aexecute_tool_call(call['tool_name'], call['parameters'])
                        logger.debug(f"   工具 {call['tool_name']} 完成，结果长度: {len(result)}")
                        return result, call
                    except Exception as e:
                        error_msg = f"[异步] 工具 {call['tool_name']} 执行失败: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        return error_msg, call

                # 使用 asyncio.gather 并发执行所有工具
                tool_task_results = await asyncio.gather(
                    *[execute_single_tool(call) for call in tool_calls]
                )

                # 处理结果并清理响应
                for result, call in tool_task_results:
                    tool_results.append(result)
                    clean_response = clean_response.replace(call['original'], "")
                    logger.debug(f"[异步] 工具 {call['tool_name']} 结果:\n{result}")

                logger.debug(f"[异步] 清理后的响应: '{clean_response}'")
                messages.append({"role": "assistant", "content": clean_response})

                tool_results_text = "\n\n".join(tool_results)
                user_msg = f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"
                logger.debug(f"[异步] 添加用户消息（工具结果），长度: {len(user_msg)}")
                messages.append({"role": "user", "content": user_msg})

                current_iteration += 1
                logger.debug(f"[异步] 进入下一轮迭代，current_iteration={current_iteration}")
                continue

            logger.debug("[异步] 未检测到工具调用，使用此响应作为最终回答")
            final_response = response
            break

        if current_iteration >= max_tool_iterations and not final_response:
            final_response = await self.llm.ainvoke(messages, **kwargs)

        # save_to_history 已废弃，不再保存到内部历史
        logger.info(f"[异步] {self.name} 响应完成")
        return final_response

    async def arun(
        self,
        input_text: str,
        external_history: Optional[List[Union[Message, dict]]] = None,
        save_to_history: bool = False,
        max_tool_iterations: int = 5,
        **kwargs
    ) -> str:
        """
        异步运行简单Agent

        Args:
            input_text: 用户输入
            external_history: 外部传入的历史记录，可以是Message对象列表或字典列表
            save_to_history: 是否保存到内部历史记录
            max_tool_iterations: 最大工具调用次数，默认3次
            **kwargs: 其他参数

        Returns:
            Agent响应
        """
        messages = []

        if self.system_prompt:
            enhanced_prompt = self._get_enhanced_system_prompt()
            messages.append({"role": "system", "content": enhanced_prompt})

        history_messages = self._merge_history(external_history)
        messages.extend(history_messages)

        has_tools = self._has_available_tools()
        messages.append({"role": "user", "content": self._build_user_content(input_text)})

        if not has_tools:
            response = await self.llm.ainvoke(messages, **kwargs)
            # save_to_history 已废弃，不再保存到内部历史
            return response

        return await self._arun_with_tools(messages, input_text, save_to_history, max_tool_iterations, **kwargs)

    def add_tool(self, tool: Tool) -> None:
        """添加一个工具到代理中"""
        if not self.tool_registry:
            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        # 检查是否是MCP工具且需要展开
        if hasattr(tool, 'auto_expand') and tool.auto_expand:
            # 获取展开的工具列表
            expanded_tools = tool.get_expanded_tools()
            if expanded_tools:
                # 注册所有展开的工具
                for expanded_tool in expanded_tools:
                    self.tool_registry.register_tool(expanded_tool)
                logger.info(f"MCP工具 '{tool.name}' 已展开为 {len(expanded_tools)} 个独立工具")
                return

        self.tool_registry.register_tool(tool)
        logger.info(f"工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查是否有可用工具"""
        return self.enable_tool_calling and self.tool_registry is not None

    def remove_tool(self, tool_name: str) -> bool:
        """从代理中移除一个工具"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> List[str]:
        """列出所有已注册的工具名称"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []

    def stream_run(
        self,
        input_text: str,
        external_history: Optional[List[Union[Message, dict]]] = None,
        save_to_history: bool = False,
        max_tool_iterations: int = 3,
        **kwargs
    ):
        """
        流式运行Agent（支持工具调用）
        动态策略：
        - 有工具 → 稳妥模式（先收集再检测，避免内容重叠）
        - 无工具 → 丝滑模式（直接流式输出）

        Args:
            input_text: 用户输入
            external_history: 外部传入的历史记录，可以是Message对象列表或字典列表
            save_to_history: 是否保存到内部历史记录
            max_tool_iterations: 最大工具调用次数，默认3次
            **kwargs: 其他参数

        Yields:
            Agent响应片段
        """
        messages = []

        if self.system_prompt:
            enhanced_prompt = self._get_enhanced_system_prompt()
            messages.append({"role": "system", "content": enhanced_prompt})

        history_messages = self._merge_history(external_history)
        messages.extend(history_messages)

        messages.append({"role": "user", "content": self._build_user_content(input_text)})

        # 检查是否有可用工具
        has_tools = self._has_available_tools()

        if not has_tools:
            # 无工具：丝滑模式，直接流式输出
            logger.debug("无可用工具，使用丝滑流式模式")
            for chunk in self.llm.stream_invoke(messages, **kwargs):
                yield {"type": "content", "data": chunk}
            # save_to_history 已废弃，不再保存到内部历史
            return

        # 有工具：稳妥模式
        logger.debug("有可用工具，使用稳妥模式")
        yield from self._stream_run_with_tools(messages, input_text, save_to_history, max_tool_iterations, **kwargs)

    def _stream_run_with_tools(
        self,
        messages: list,
        input_text: str,
        save_to_history: bool,
        max_tool_iterations: int,
        **kwargs
    ):
        """
        流式运行代理，处理输入文本并返回响应(带工具调用)
        稳妥策略：
        1. 先完整收集响应和所有 chunks，检测是否有工具调用
        2. 如果有工具调用：不输出内容，只发送工具调用事件
        3. 如果没有工具调用：直接用已收集的 chunks 流式输出（避免二次调用）

        Args:
            messages: 消息队列，包含系统消息、历史消息和当前用户消息
            input_text: 输入的文本
            save_to_history: 是否保存到内部历史记录
            max_tool_iterations: 最大工具调用次数
            **kwargs: 其他参数

        Yields:
            包含type和data的字典，type可以是'thinking', 'tool_call', 'content'
        """
        current_iteration = 0

        logger.debug(f"开始流式工具调用循环，max_tool_iterations={max_tool_iterations}")

        while current_iteration < max_tool_iterations:
            logger.debug(f"流式迭代 {current_iteration + 1}/{max_tool_iterations} 开始")

            # 阶段1：收集完整响应和所有 chunks，检测是否有工具调用
            logger.debug("阶段1：收集完整响应以检测工具调用")
            response_chunks = []
            for chunk in self.llm.stream_invoke(messages, **kwargs):
                response_chunks.append(chunk)

            response = "".join(response_chunks)
            logger.info(f"{self.name} 第{current_iteration+1}轮调用响应完成，响应长度: {len(response)}")
            logger.info(f"LLM 响应内容:\n{response}")

            # 解析工具调用
            tool_calls = self._parse_tool_call(response)
            if tool_calls:
                logger.info(f"✅ 成功检测到 {len(tool_calls)} 个工具调用！")
            else:
                logger.warning(f"⚠️ 未检测到工具调用，LLM 直接给出了回答")

            if tool_calls:
                logger.debug(f"检测到 {len(tool_calls)} 个工具调用，进入工具处理模式")
                for i, call in enumerate(tool_calls):
                    logger.debug(f"   工具 {i+1}: name={call['tool_name']}, params={call['parameters']}")

                # 发送思考过程事件（包含完整响应）
                yield {"type": "thinking_start", "data": {"iteration": current_iteration + 1}}
                yield {"type": "thinking_content", "data": response}
                yield {"type": "thinking_end", "data": {"iteration": current_iteration + 1}}

                tool_results = []
                clean_response = response

                for call in tool_calls:
                    logger.debug(f"正在执行工具: {call['tool_name']}")
                    yield {"type": "tool_call_start", "data": {
                        "tool_name": call['tool_name'],
                        "parameters": call['parameters']
                    }}

                    try:
                        result = self._execute_tool_call(call['tool_name'], call['parameters'])
                        logger.debug(f"工具执行完成，结果长度: {len(result)}")
                        logger.debug(f"工具执行结果:\n{result}")
                    except Exception as e:
                        error_msg = f"工具执行异常: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        result = error_msg

                    tool_results.append(result)
                    clean_response = clean_response.replace(call['original'], "")

                    yield {"type": "tool_call_end", "data": {
                        "tool_name": call['tool_name'],
                        "result": result
                    }}

                logger.debug(f"清理后的响应: '{clean_response}'")
                messages.append({"role": "assistant", "content": clean_response})

                tool_results_text = "\n\n".join(tool_results)
                user_msg = f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"
                logger.debug(f"添加用户消息（工具结果），长度: {len(user_msg)}")
                messages.append({"role": "user", "content": user_msg})

                current_iteration += 1
                logger.debug(f"进入下一轮迭代，current_iteration={current_iteration}")
                continue

            # 没有工具调用，直接用已收集的 chunks 流式输出
            logger.debug("未检测到工具调用，直接流式输出已收集的内容")
            for chunk in response_chunks:
                yield {"type": "content", "data": chunk}

            break

        # 如果达到最大迭代次数，进行最终生成
        if current_iteration >= max_tool_iterations:
            logger.debug(f"达到最大迭代次数 {max_tool_iterations}，进行最终生成")
            for chunk in self.llm.stream_invoke(messages, **kwargs):
                yield {"type": "content", "data": chunk}

        # save_to_history 已废弃，不再保存到内部历史
        logger.info(f"{self.name} 响应完成")

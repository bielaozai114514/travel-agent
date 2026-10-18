from typing import Optional, List
import re

from ..core.llm import EsAgentLLM
from ..core.config import Config
from .simple_agent import SimpleAgent
from ..tools.registry import ToolRegistry
from ..tools.base import Tool
from ..core.message import Message

class SimpleToolAgent(SimpleAgent):
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
        print(f"✅ {name} 初始化完成，工具调用: {'启用' if self.enable_tool_calling else '禁用'}")

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs):
        """
        运行代理，处理输入文本并返回响应(非流式)。

        Args:
            input_text: 输入的文本
            max_tool_iterations: 最大工具调用次数，默认3次

        Returns:
            模型的响应文本
        """

        # 构建消息队列
        messages = []

        # 添加系统信息
        enhanced_prompt = self._get_enhanced_system_prompt()
        messages.append({"role": "system", "content": enhanced_prompt})
        
        # 添加历史信息
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        # 添加当前用户信息
        messages.append({"role": "user", "content": input_text})

        # 无工具
        if not self.enable_tool_calling:
            response =self.llm.invoke(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            print(f"✅ {self.name} 响应完成")
            return response

        # 调用工具
        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    def _run_with_tools(self, messages: list, input_text: str, max_tool_iterations: int, **kwargs) -> str:
        """
        运行代理，处理输入文本并返回响应(非流式)。

        Args:
            messages: 消息队列，包含系统消息、历史消息和当前用户消息.
            input_text: 输入的文本
            max_tool_iterations: 最大工具调用次数，默认3次

        Returns:
            模型的响应文本
        """

        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            # 调用LLM
            response = self.llm.invoke(messages, **kwargs)
            
            print(f"✅ {self.name} 第{current_iteration+1}轮调用响应完成: {response}")
            print("-------------------------------")

            # 检查是否有工具调用
            tool_calls = self._parse_tool_call(response)
            if tool_calls:
                print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                # 执行所有工具调用并收集结果
                tool_results = []
                clean_response = response

                for call in tool_calls:
                    result = self._execute_tool_call(call['tool_name'], call['parameters'])
                    tool_results.append(result)
                    # 从响应中移除工具调用标记
                    clean_response = clean_response.replace(call['original'], "")

                # 构建包含工具结果的消息
                messages.append({"role": "assistant", "content": clean_response})

                # 添加工具结果
                tool_results_text = "\n\n".join(tool_results)
                messages.append({"role": "user", "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"})

                current_iteration += 1
                continue

            # 没有工具调用，这是最终回答
            final_response = response
            break

        # 如果超过最大迭代次数，获取最后一次回答
        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm.invoke(messages, **kwargs)

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.name} 响应完成")

        return final_response

    def _get_enhanced_system_prompt(self) -> str:
        """
        获取包含所有工具信息的增强系统提示。
        在基础系统提示词上直接添加工具描述。
        Returns:
            包含所有工具信息的系统提示字符串
        """
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        if not self.enable_tool_calling or self.tool_registry is None:
            return base_prompt

        # 获取工具描述
        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"

        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式:\n"
        tools_section += "1. 有参数的工具: `[TOOL_CALL:{tool_name}:{parameters}]`\n"
        tools_section += "2. 无参数的工具: `[TOOL_CALL:{tool_name}]`\n"
        tools_section += "例如:`[TOOL_CALL:search:Python编程]` 或 `[TOOL_CALL:time]`\n\n"
        tools_section += "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"

        return base_prompt + tools_section

    def _parse_tool_call(self, text: str) -> Optional[dict]:
        """
        解析工具调用字符串，提取工具名称和参数。

        Args:
            text: 工具调用字符串，格式如 "[TOOL_CALL:search:Python编程]" 或 "[TOOL_CALL:time]"

        Returns:
            包含工具名称和参数的字典，如 {"name": "search", "parameters": "Python编程"}
        """
        tool_calls = []
        
        # 先尝试匹配有参数的格式：[TOOL_CALL:tool_name:parameters]
        pattern_with_params = r'\[TOOL_CALL:([^:]+):([^\]]+)\]'
        matches_with_params = re.findall(pattern_with_params, text)
        
        for tool_name, parameters in matches_with_params:
            tool_calls.append({
                'tool_name': tool_name.strip(),
                'parameters': parameters.strip(),
                'original': f'[TOOL_CALL:{tool_name}:{parameters}]'
            })
        
        # 再尝试匹配无参数的格式：[TOOL_CALL:tool_name]
        pattern_no_params = r'\[TOOL_CALL:([^\]:]+)\]'
        matches_no_params = re.findall(pattern_no_params, text)
        
        for tool_name in matches_no_params:
            # 检查是否已经在有参数的匹配中存在（避免重复）
            if not any(call['tool_name'] == tool_name.strip() for call in tool_calls):
                tool_calls.append({
                    'tool_name': tool_name.strip(),
                    'parameters': '',
                    'original': f'[TOOL_CALL:{tool_name}]'
                })

        return tool_calls
    
    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
        """智能解析工具参数"""
        param_dict = {}

        if '=' in parameters:
            # 格式: key=value 或 action=search,query=Python
            if ',' in parameters:
                # 多个参数:action=search,query=Python,limit=3
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                # 单个参数:key=value
                key, value = parameters.split('=', 1)
                param_dict[key.strip()] = value.strip()
        else:
            # 直接传入参数，根据工具类型智能推断
            if tool_name == 'search':
                param_dict = {'query': parameters}
            elif tool_name == 'memory':
                param_dict = {'action': 'search', 'query': parameters}
            else:
                param_dict = {'input': parameters}

        return param_dict
    

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """
        执行工具调用。

        Args:
            tool_name: 要调用的工具名称
            parameters: 工具调用的参数

        Returns:
            工具执行结果的字符串
        """
        
        if not self.tool_registry:
            return f"❌ 错误:未配置工具注册表"

        param_dict = self._parse_tool_parameters(tool_name, parameters)
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return f"❌ 错误:未找到工具 '{tool_name}'"
        result = tool.run(param_dict)
        return f"🔧 工具 {tool_name} 执行结果:\n{result}"

    def add_tool(self, tool: Tool) -> None:
        """
        添加一个工具到代理中。

        Args:
            tool: 要添加的工具实例
        """
        # 在没有的情况下自动生成
        if not self.tool_registry:
            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        self.tool_registry.register_tool(tool)
        print(f"🔧 工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查是否有可用工具"""
        return self.enable_tool_calling and self.tool_registry is not None

    def remove_tool(self, tool_name: str) -> bool:
        """
        从代理中移除一个工具。

        Args:
            tool_name: 要移除的工具名称

        Returns:
            如果成功移除则返回True，否则返回False
        """
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> List[str]:
        """列出所有已注册的工具名称"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []
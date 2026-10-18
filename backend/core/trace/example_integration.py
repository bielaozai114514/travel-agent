"""
Trace 埋点示例 - 展示如何在 SimpleAgent 中使用 Trace

这是一个示例文件，展示如何在你的 Agent 中集成 trace。
你可以参考这个文件来修改你实际的 SimpleAgent 代码。
"""

from typing import Optional, List, Union

# 导入 Trace 模块
from core.trace import trace_span, trace, get_current_trace_id

# 假设这是你的 SimpleAgent 类
# from ..core.agent import Agent
# from ..core.llm import EsAgentLLM
# from ..core.config import Config
# from ..core.message import Message
# from ..tools.registry import ToolRegistry


class SimpleAgentWithTrace:
    """
    带 Trace 的 SimpleAgent 示例

    这个类展示如何在 SimpleAgent 中添加 trace 埋点。
    主要改动：
    1. 在 run() 方法外层加 trace_span (AGENT 层级)
    2. 在每轮迭代加 trace_span (STEP 层级)
    3. 在工具调用处加 trace_span (TOOL 层级)
    4. 在 LLM 调用处加 trace_span (LLM 层级)
    """

    def run(
        self,
        input_text: str,
        external_history: Optional[List[Union[Message, dict]]] = None,
        save_to_history: bool = False,
        max_tool_iterations: int = 3,
        **kwargs
    ) -> str:
        """
        运行 Agent（带 Trace 埋点）
        """
        # ============ AGENT 层级 Trace ============
        with trace_span(
            name=f"{self.name}.run",
            level="AGENT",
            agent_type=self.__class__.__name__,
        ) as span:
            span.set_input(input_text)
            span.set_metadata("max_tool_iterations", max_tool_iterations)
            span.set_metadata("save_to_history", save_to_history)

            # 原有逻辑...
            messages = []

            if self.system_prompt:
                enhanced_prompt = self._get_enhanced_system_prompt()
                messages.append({"role": "system", "content": enhanced_prompt})

            history_messages = self._merge_history(external_history)
            messages.extend(history_messages)

            reminder_text = "\n\n【重要提醒】：如果需要获取实时信息、执行特定操作或不确定答案时，请优先使用可用的工具！"
            messages.append({"role": "user", "content": input_text + reminder_text})

            if not self.enable_tool_calling or not self.tool_registry:
                # ============ LLM 层级 Trace（无工具路径） ============
                with trace_span(
                    name="llm_invoke",
                    level="LLM",
                ) as llm_span:
                    llm_span.set_llm_data(
                        prompt=messages,
                    )
                    response = self.llm.invoke(messages, **kwargs)
                    llm_span.set_llm_data(
                        response=response,
                    )

                if save_to_history:
                    self.add_message(Message(input_text, "user"))
                    self.add_message(Message(response, "assistant"))

                span.set_output(response)
                return response

            result = self._run_with_tools(messages, input_text, save_to_history, max_tool_iterations, **kwargs)
            span.set_output(result)
            return result

    def _run_with_tools(
        self,
        messages: list,
        input_text: str,
        save_to_history: bool,
        max_tool_iterations: int,
        **kwargs
    ) -> str:
        """
        带工具调用的运行（带 Trace 埋点）
        """
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            # ============ STEP 层级 Trace（每轮迭代） ============
            with trace_span(
                name=f"iteration_{current_iteration + 1}",
                level="STEP",
            ) as step_span:
                step_span.set_metadata("iteration", current_iteration + 1)

                print(f"\n🔄 第 {current_iteration + 1}/{max_tool_iterations} 轮迭代开始")

                # ============ LLM 层级 Trace ============
                with trace_span(
                    name="llm_invoke",
                    level="LLM",
                ) as llm_span:
                    llm_span.set_llm_data(prompt=messages)
                    response = self.llm.invoke(messages, **kwargs)
                    llm_span.set_llm_data(response=response)

                print(f"✅ {self.name} 第{current_iteration+1}轮调用响应完成，响应长度: {len(response)}")
                print(f"📝 LLM 响应内容:\n{response}\n")

                tool_calls = self._parse_tool_call(response)

                # 设置 STEP 的数据
                step_span.set_agent_data(thought=response, tool_calls=tool_calls)

                if tool_calls:
                    print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                    for i, call in enumerate(tool_calls):
                        print(f"   工具 {i+1}: name={call['tool_name']}, params={call['parameters']}")

                    tool_results = []
                    clean_response = response

                    for call in tool_calls:
                        # ============ TOOL 层级 Trace ============
                        with trace_span(
                            name=f"tool_{call['tool_name']}",
                            level="TOOL",
                        ) as tool_span:
                            tool_span.set_tool_data(
                                tool_name=call['tool_name'],
                                parameters=call['parameters'],
                            )

                            print(f"\n⚙️  正在执行工具: {call['tool_name']}")
                            try:
                                result = self._execute_tool_call(call['tool_name'], call['parameters'])
                                print(f"✅ 工具执行完成，结果长度: {len(result)}")
                                print(f"📦 工具执行结果:\n{result}\n")

                                tool_span.set_tool_data(
                                    tool_name=call['tool_name'],
                                    parameters=call['parameters'],
                                    result=result,
                                )
                                tool_results.append(result)
                            except Exception as e:
                                error_msg = f"❌ 工具执行失败: {str(e)}"
                                print(error_msg)
                                import traceback
                                traceback.print_exc()

                                tool_span.set_error(e)
                                tool_results.append(error_msg)

                        clean_response = clean_response.replace(call['original'], "")

                    print(f"🧹 清理后的响应: '{clean_response}'")
                    messages.append({"role": "assistant", "content": clean_response})

                    tool_results_text = "\n\n".join(tool_results)
                    user_msg = f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"
                    print(f"📨 添加用户消息（工具结果），长度: {len(user_msg)}")
                    messages.append({"role": "user", "content": user_msg})

                    current_iteration += 1
                    print(f"➡️  进入下一轮迭代，current_iteration={current_iteration}")
                    continue

                print("❌ 未检测到工具调用，使用此响应作为最终回答")
                final_response = response
                break

        if current_iteration >= max_tool_iterations and not final_response:
            with trace_span(name="llm_final", level="LLM") as llm_span:
                llm_span.set_llm_data(prompt=messages)
                final_response = self.llm.invoke(messages, **kwargs)
                llm_span.set_llm_data(response=final_response)

        if save_to_history:
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(final_response, "assistant"))

        print(f"✅ {self.name} 响应完成")
        return final_response


# ============ 使用装饰器的示例 ============

class ToolExample:
    """工具类示例，展示如何使用 @trace 装饰器"""

    @trace(level="TOOL", name="search_weather")
    def search_weather(self, location: str) -> str:
        """搜索天气（装饰器自动记录）"""
        # 你的工具逻辑...
        return f"{location} 的天气是晴天"

    @trace(level="TOOL", name="search_attraction")
    def search_attraction(self, city: str, keyword: str) -> str:
        """搜索景点（装饰器自动记录）"""
        # 你的工具逻辑...
        return f"{city} 的 {keyword} 相关景点: ..."


# ============ 快速使用指南 ============

"""
## 快速使用指南

### 1. 在函数开头获取 trace_id（用于关联）
```python
from core.trace import get_current_trace_id

def my_function():
    trace_id = get_current_trace_id()
    # 可以把 trace_id 返回给前端，方便后续查询
    return {"result": "...", "trace_id": trace_id}
```

### 2. 使用 context manager（推荐，最灵活）
```python
from core.trace import trace_span

with trace_span("my_operation", level="AGENT", agent_type="MyAgent") as span:
    span.set_input(input_data)
    # ... do work ...
    span.set_output(output_data)
```

### 3. 使用装饰器（适合简单函数）
```python
from core.trace import trace

@trace(level="TOOL", name="my_tool")
def my_tool(param1, param2):
    # ... do work ...
    return result
```

### 4. 设置各层级专属数据
```python
# STEP 层级
span.set_agent_data(thought=llm_thought, tool_calls=parsed_calls)

# TOOL 层级
span.set_tool_data(tool_name="search", parameters={"q": "xxx"}, result="...")

# LLM 层级
span.set_llm_data(provider="openai", model="gpt-4", prompt=..., response=...)

# 通用 metadata
span.set_metadata("key", "value")
```
"""

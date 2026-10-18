"""EsAgent 模块 - 智能代理系统

这个模块提供了完整的智能代理系统，包括：
- 多种类型的Agent实现
- 工具系统和工具注册表
- LLM客户端
- 消息系统
- MCP协议支持
"""

# 核心模块
try:
    from .core.llm import EsAgentLLM
    from .core.agent import Agent
    from .core.config import Config
    from .core.message import Message, MessageRole
    from .core.exceptions import EsAgentException, LLMException, AgentException, ConfigException, ToolException
except ImportError as e:
    print(f"警告: 核心模块导入失败: {e}")

# 代理模块
try:
    from .agents.simple_agent import SimpleAgent
    from .agents.simple_tool_agent import SimpleToolAgent
    from .agents.react_agent import ReActAgent
    from .agents.plan_solve_agent import PlanAndSolveAgent
    from .agents.reflection_agent import ReflectionAgent
except ImportError as e:
    print(f"警告: 代理模块导入失败: {e}")

# 工具模块
try:
    from .tools.registry import ToolRegistry, global_registry
    from .tools.base import Tool, ToolParameter
    from .tools.chain import ToolChain, ToolChainManager
    from .tools.async_executor import AsyncToolExecutor, run_parallel_tools, run_batch_tool
except ImportError as e:
    print(f"警告: 工具模块导入失败: {e}")

# 内置工具
try:
    from .tools.builtin.calculator import CalculatorTool, calculate
    from .tools.builtin.time import TimeTool, get_time
except ImportError as e:
    print(f"警告: 内置工具导入失败: {e}")

# MCP协议
try:
    from .protocols import Protocol, MCPClient, MCPServer, create_context, parse_context
except ImportError as e:
    print(f"警告: MCP协议导入失败: {e}")

__all__ = [
    # 核心模块
    "EsAgentLLM",
    "Agent",
    "Config",
    "Message",
    "MessageRole",
    "EsAgentException",
    "LLMException",
    "AgentException",
    "ConfigException",
    "ToolException",
    
    # 代理模块
    "SimpleAgent",
    "SimpleToolAgent",
    "ReActAgent",
    "PlanAndSolveAgent",
    "ReflectionAgent",
    
    # 工具模块
    "ToolRegistry",
    "global_registry",
    "Tool",
    "ToolParameter",
    "ToolChain",
    "ToolChainManager",
    "AsyncToolExecutor",
    "run_parallel_tools",
    "run_batch_tool",
    
    # 内置工具
    "CalculatorTool",
    "calculate",
    "TimeTool",
    "get_time",
    
    # MCP协议
    "Protocol",
    "MCPClient",
    "MCPServer",
    "create_context",
    "parse_context",
]

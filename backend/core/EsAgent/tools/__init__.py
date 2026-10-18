"""工具模块"""

from .registry import ToolRegistry, global_registry
from .base import Tool, ToolParameter
from .chain import ToolChain, ToolChainManager
from .async_executor import AsyncToolExecutor, run_parallel_tools, run_batch_tool

# 内置工具
from .builtin.calculator import CalculatorTool, calculate
from .builtin.time import TimeTool, get_time
try:
    from .builtin.protocol_tools import MCPTool
except Exception as e:
    import traceback
    print(f"警告: 导入MCPTool失败: {e}")
    print(traceback.format_exc())
    MCPTool = None

__all__ = [
    "ToolRegistry",
    "global_registry",
    "Tool",
    "ToolParameter",
    "ToolChain",
    "ToolChainManager",
    "AsyncToolExecutor",
    "run_parallel_tools",
    "run_batch_tool",
    "CalculatorTool",
    "calculate",
    "TimeTool",
    "get_time",
    "MCPTool",
]

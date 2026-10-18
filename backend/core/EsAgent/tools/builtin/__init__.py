"""内置工具模块"""

from .calculator import CalculatorTool, calculate
from .time import TimeTool, get_time

# 旅游攻略搜索工具
try:
    from .guide_search import GuideSearchTool, search_guides
except ImportError:
    pass

# RAG工具（可选）
try:
    from .rag import RAGTool
except ImportError:
    pass

# MCP工具（可选）
try:
    from .mcp_wrapper_tool import MCPWrappedTool
except ImportError:
    pass

try:
    from .protocol_tools import ProtocolTool
except ImportError:
    pass

__all__ = [
    "CalculatorTool",
    "calculate",
    "TimeTool",
    "get_time",
    "GuideSearchTool",
    "search_guides",
    "RAGTool",
    "MCPWrappedTool",
    "ProtocolTool",
]

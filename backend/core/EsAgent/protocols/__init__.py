"""智能体通信协议模块

本模块提供的智能体通信协议：
- MCP (Model Context Protocol): 模型上下文协议
"""

from .base import Protocol

# MCP 协议 - 导出所有常用类（可选，需要 fastmcp）
try:
    from .mcp import (
        MCPClient,
        MCPServer,
        create_context,
        parse_context,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # 提供占位符
    class MCPClient:
        def __init__(self, *args, **kwargs):
            raise ImportError("MCP requires fastmcp: pip install fastmcp")
    class MCPServer:
        def __init__(self, *args, **kwargs):
            raise ImportError("MCP requires fastmcp: pip install fastmcp")
    def create_context(*args, **kwargs):
        raise ImportError("MCP requires fastmcp: pip install fastmcp")
    def parse_context(*args, **kwargs):
        raise ImportError("MCP requires fastmcp: pip install fastmcp")



__all__ = [
    # 基础协议
    "Protocol",

    # MCP 协议（可选）
    "MCPClient",
    "MCPServer",
    "create_context",
    "parse_context",
]


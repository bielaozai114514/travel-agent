"""
Agent Trace 追踪系统

用于追踪 Agent 执行过程，方便调试和问题定位。

使用方式：
1. 显式埋点 - 使用 context manager:
    from core.trace import tracer, trace_span

    with trace_span("my_agent", level="AGENT", agent_type="SimpleAgent") as span:
        span.set_input(user_input)
        # ... 执行逻辑 ...
        span.set_output(result)

2. 使用装饰器:
    from core.trace import trace

    @trace(level="TOOL", name="search_weather")
    def search_weather(location):
        ...

3. 获取当前 Trace ID:
    from core.trace import get_current_trace_id

    trace_id = get_current_trace_id()
"""

from core.trace.span import Span, TraceLevel, TraceStatus
from core.trace.tracer import (
    Tracer,
    tracer,
    trace_span,
    trace,
    get_current_trace_id,
    get_current_span,
    set_current_trace_id,
)
from core.trace.logger import setup_trace_logger

__all__ = [
    "Span",
    "TraceLevel",
    "TraceStatus",
    "Tracer",
    "tracer",
    "trace_span",
    "trace",
    "get_current_trace_id",
    "get_current_span",
    "set_current_trace_id",
    "setup_trace_logger",
]

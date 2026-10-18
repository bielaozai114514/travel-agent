"""
Tracer - Trace 管理器（单例）
提供装饰器、context manager 和显式 API
"""

import contextvars
import inspect
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, Union, Callable, TypeVar, cast, List, Tuple
from functools import wraps

from core.trace.span import Span, TraceLevel, TraceStatus
from core.logger import LoggerManager

# 全局上下文变量
_current_trace_id = contextvars.ContextVar("current_trace_id", default=None)
_current_span_stack = contextvars.ContextVar("current_span_stack", default=())


def _truncate_str(s: Any, max_len: int = 200) -> str:
    """智能截断字符串"""
    if s is None:
        return "None"
    if isinstance(s, (dict, list, tuple)):
        s = json.dumps(s, ensure_ascii=False)
    s = str(s)
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def _format_span_data_for_console(span: Span) -> List[str]:
    """格式化 Span 的数据用于终端输出"""
    lines = []
    indent = "    "

    # 根据层级选择 emoji
    level_emojis = {
        TraceLevel.AGENT: "📋",
        TraceLevel.STEP: "🔍",
        TraceLevel.TOOL: "🛠️",
        TraceLevel.LLM: "🤖",
    }
    emoji = level_emojis.get(span.level, "•")

    # 状态 emoji
    status_emoji = "✅" if span.status == TraceStatus.COMPLETED else "❌"

    # 基础信息行
    duration_str = f"{span.duration_ms:.2f}ms" if span.duration_ms else ""
    base_line = f"{emoji} [{span.level.value}] {span.name}"
    if duration_str:
        base_line += f" ({duration_str})"
    if span.status == TraceStatus.FAILED and span.error_message:
        base_line += f" - {span.error_message}"
    lines.append(base_line)

    # AGENT 层级：显示 input/output
    if span.level == TraceLevel.AGENT:
        if span.input:
            lines.append(f"{indent}↪️ 输入: {_truncate_str(span.input, 200)}")
        if span.output:
            lines.append(f"{indent}↪️ 输出: {_truncate_str(span.output, 200)}")

    # STEP 层级：显示 thought、input/output
    elif span.level == TraceLevel.STEP:
        if span.thought:
            lines.append(f"{indent}💭 思考: {_truncate_str(span.thought, 100)}")
        if span.input:
            lines.append(f"{indent}↪️ 输入: {_truncate_str(span.input, 200)}")
        if span.output:
            lines.append(f"{indent}↪️ 输出: {_truncate_str(span.output, 200)}")

    # TOOL 层级：显示工具名、参数、结果
    elif span.level == TraceLevel.TOOL:
        if span.tool_name:
            lines.append(f"{indent}🔧 工具: {span.tool_name}")
        if span.tool_parameters:
            lines.append(f"{indent}📥 参数: {_truncate_str(span.tool_parameters, 150)}")
        if span.tool_result:
            lines.append(f"{indent}📤 结果: {_truncate_str(span.tool_result, 150)}")
        elif span.output:
            lines.append(f"{indent}📤 结果: {_truncate_str(span.output, 150)}")

    # LLM 层级：显示模型名（不显示 prompt/response，太长）
    elif span.level == TraceLevel.LLM:
        if span.llm_model:
            lines.append(f"{indent}🧠 模型: {span.llm_model}")
        if span.llm_provider:
            lines.append(f"{indent}🏭 提供商: {span.llm_provider}")
        if span.llm_prompt_tokens or span.llm_completion_tokens:
            token_info = []
            if span.llm_prompt_tokens:
                token_info.append(f"Prompt: {span.llm_prompt_tokens}")
            if span.llm_completion_tokens:
                token_info.append(f"Completion: {span.llm_completion_tokens}")
            if token_info:
                lines.append(f"{indent}📊 Tokens: {', '.join(token_info)}")

    # 元数据（如果有的话，选择性显示）
    if span.metadata and isinstance(span.metadata, dict):
        # 只显示一些关键的元数据
        meta_to_show = {}
        for k, v in span.metadata.items():
            if k in ["city", "days", "model", "tool_name"]:
                meta_to_show[k] = v
        if meta_to_show:
            lines.append(f"{indent}📌 元数据: {_truncate_str(meta_to_show, 100)}")

    return lines


class Tracer:
    """
    Trace 管理器（单例）
    负责创建 Span、记录日志、持久化到数据库
    """

    _instance: Optional["Tracer"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.enabled: bool = True
        self.log_dir: Path = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self.logger = LoggerManager.get_logger(
            name="trace",
            level=LoggerManager.DEBUG if __debug__ else LoggerManager.INFO,
        )

        self._jsonl_logger = LoggerManager.get_logger(
            name="trace_jsonl",
            level=LoggerManager.INFO,
            console_output=False,
        )

        # 数据库持久化（延迟导入避免循环依赖）
        self._db_service = None

    def _get_db_service(self):
        """延迟获取数据库服务"""
        if self._db_service is None:
            try:
                from services.trace_service import trace_service
                self._db_service = trace_service
            except ImportError:
                pass
        return self._db_service

    def create_span(
        self,
        name: str,
        level: Union[TraceLevel, str],
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """
        创建一个新的 Span

        如果不提供 trace_id，会自动从当前上下文获取或生成新的
        如果不提供 parent_span_id，会自动使用当前栈顶的 span
        """
        if not self.enabled:
            return Span(name, level, trace_id, parent_span_id, agent_type, metadata)

        if trace_id is None:
            trace_id = _current_trace_id.get()

        if parent_span_id is None:
            stack = _current_span_stack.get()
            if stack:
                parent_span_id = stack[-1].span_id
                if trace_id is None:
                    trace_id = stack[-1].trace_id

        # 避免外部传入的 metadata 被后续原地修改影响
        span_metadata = dict(metadata) if metadata else None

        span = Span(name, level, trace_id, parent_span_id, agent_type, span_metadata)
        self._log_span_started(span)
        return span

    def start_span(self, span: Span) -> None:
        """开始一个 Span，将其压入上下文栈"""
        if not self.enabled:
            return

        _current_trace_id.set(span.trace_id)

        stack = _current_span_stack.get()
        _current_span_stack.set(stack + (span,))

    def end_span(self, span: Span) -> None:
        """结束一个 Span，从上下文栈弹出并记录"""
        if not self.enabled:
            return

        span.finish()
        self._log_span_finished(span)
        self._persist_span(span)

        stack = _current_span_stack.get()

        if stack and stack[-1].span_id == span.span_id:
            new_stack = stack[:-1]
        else:
            # 容错：如果不是栈顶，也尽量移除，避免上下文残留
            new_stack = tuple(s for s in stack if s.span_id != span.span_id)

        _current_span_stack.set(new_stack)

        if new_stack:
            _current_trace_id.set(new_stack[-1].trace_id)
        else:
            _current_trace_id.set(None)

    def _log_span_started(self, span: Span) -> None:
        """记录 Span 开始（简化，只在 DEBUG 级别显示）"""
        # 只有 TOOL/LLM 级别才在开始时输出，AGENT/STEP 只在结束时输出
        if span.level in (TraceLevel.TOOL, TraceLevel.LLM):
            self.logger.debug(
                f"🚀 [{span.level.value}] {span.name} starting... "
                f"(trace_id={span.trace_id[:8]}...)"
            )

    def _log_span_finished(self, span: Span) -> None:
        """记录 Span 结束（树形输出）"""
        # 根据层级决定日志级别
        if span.level in (TraceLevel.AGENT, TraceLevel.STEP):
            log_func = self.logger.info
        else:
            log_func = self.logger.debug

        # 格式化输出
        data_lines = _format_span_data_for_console(span)

        # 根据层级确定缩进深度
        level_order = {
            TraceLevel.AGENT: 0,
            TraceLevel.STEP: 1,
            TraceLevel.TOOL: 2,
            TraceLevel.LLM: 3,
        }
        depth = level_order.get(span.level, 0)

        # 输出每一行
        for i, line in enumerate(data_lines):
            if i == 0:
                # 第一行带树形前缀
                if depth == 0:
                    prefix = ""
                else:
                    prefix = "│   " * (depth - 1) + "├── "
                full_line = prefix + line
            else:
                # 后续行用对齐缩进
                full_line = "│   " * depth + line

            if span.status == TraceStatus.FAILED and i == 0:
                # 错误用 error 级别
                self.logger.error(full_line)
            else:
                log_func(full_line)

        # 记录完整 JSON 到 JSONL logger（始终记录完整数据）
        try:
            json_data = json.dumps(span.to_dict(), ensure_ascii=False)
            self._jsonl_logger.info(json_data)
        except Exception as e:
            self.logger.warning(f"Failed to log span to JSONL: {e}")

    def _persist_span(self, span: Span) -> None:
        """持久化 Span 到数据库"""
        try:
            db_service = self._get_db_service()
            if db_service:
                import asyncio
                try:
                    asyncio.get_running_loop()
                    asyncio.create_task(db_service.save_span(span))
                except RuntimeError:
                    # 没有运行中的事件循环，跳过异步持久化
                    pass
        except Exception as e:
            self.logger.warning(f"Failed to persist span to database: {e}")

    def get_current_trace_id(self) -> Optional[str]:
        """获取当前 trace_id"""
        return _current_trace_id.get()

    def get_current_span(self) -> Optional[Span]:
        """获取当前栈顶的 span"""
        stack = _current_span_stack.get()
        return stack[-1] if stack else None

    def set_current_trace_id(self, trace_id: str) -> None:
        """手动设置当前 trace_id（用于关联已有 trace）"""
        _current_trace_id.set(trace_id)


# 全局单例
tracer = Tracer()


# ============ Context Manager ============

@contextmanager
def trace_span(
    name: str,
    level: Union[TraceLevel, str] = TraceLevel.STEP,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Trace Context Manager - 用于显式埋点

    使用方式:
        with trace_span("my_operation", level="AGENT") as span:
            span.set_input(input_data)
            ...
            span.set_output(output_data)
    """
    span = tracer.create_span(
        name=name,
        level=level,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        agent_type=agent_type,
        metadata=metadata,
    )
    tracer.start_span(span)

    try:
        yield span
        if span.status == TraceStatus.STARTED:
            span.set_success()
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        tracer.end_span(span)


# ============ Decorator ============

T = TypeVar("T")


def trace(
    name: Optional[str] = None,
    level: Union[TraceLevel, str] = TraceLevel.TOOL,
    agent_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    include_args: bool = True,
    include_return: bool = True,
):
    """
    Trace Decorator - 同时支持 sync / async 函数

    使用方式:
        @trace(level="TOOL", name="search_weather")
        def search_weather(location):
            ...

        @trace(level="LLM")
        async def call_llm(prompt):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        span_name = name or func.__name__

        # 判断是否是异步函数
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 异步函数的包装器
                with trace_span(
                    name=span_name,
                    level=level,
                    agent_type=agent_type,
                    metadata=dict(metadata) if metadata else None,
                ) as span:
                    # 记录参数
                    if include_args:
                        span.set_metadata("args", _safe_repr(args))
                        span.set_metadata("kwargs", _safe_repr(kwargs))

                    try:
                        # 执行异步函数
                        result = await func(*args, **kwargs)
                        # 记录返回值
                        if include_return:
                            span.set_output(_safe_repr(result))
                        return result
                    except Exception as e:
                        # 记录异常
                        span.set_error(e)
                        raise

            return cast(Callable[..., T], async_wrapper)

        # 同步函数的包装器
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with trace_span(
                name=span_name,
                level=level,
                agent_type=agent_type,
                metadata=dict(metadata) if metadata else None,
            ) as span:
                # 记录参数
                if include_args:
                    span.set_metadata("args", _safe_repr(args))
                    span.set_metadata("kwargs", _safe_repr(kwargs))

                try:
                    # 执行同步函数
                    result = func(*args, **kwargs)
                    # 记录返回值
                    if include_return:
                        span.set_output(_safe_repr(result))
                    return result
                except Exception as e:
                    # 记录异常
                    span.set_error(e)
                    raise

        return cast(Callable[..., T], sync_wrapper)

    return decorator


def _safe_repr(obj: Any) -> Any:
    """
    安全的 repr，避免大对象导致日志过大

    对大对象进行截断，只保留部分内容
    """
    try:
        # 基本类型直接返回
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj

        # 列表/元组，超过10个元素只显示长度
        if isinstance(obj, (list, tuple)):
            if len(obj) > 10:
                return f"{type(obj).__name__}(length={len(obj)})"
            return [_safe_repr(item) for item in obj]

        # 字典，超过20个key只显示前10个
        if isinstance(obj, dict):
            if len(obj) > 20:
                return f"dict(keys={list(obj.keys())[:10]}...)"
            return {k: _safe_repr(v) for k, v in obj.items()}

        # 其他对象，截断到1000字符
        return repr(obj)[:1000]
    except Exception:
        return f"<{type(obj).__name__} object>"


# ============ Convenience Functions ============

def get_current_trace_id() -> Optional[str]:
    """获取当前 trace_id"""
    return tracer.get_current_trace_id()


def get_current_span() -> Optional[Span]:
    """获取当前 span"""
    return tracer.get_current_span()


def set_current_trace_id(trace_id: str) -> None:
    """设置当前 trace_id"""
    tracer.set_current_trace_id(trace_id)

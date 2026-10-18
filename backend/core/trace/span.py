"""
Span - Trace 事件单元
"""

import time
import uuid
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Union
from enum import Enum


class TraceLevel(str, Enum):
    """Trace 层级"""
    AGENT = "AGENT"
    STEP = "STEP"
    TOOL = "TOOL"
    LLM = "LLM"


class TraceStatus(str, Enum):
    """Trace 状态"""
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Span:
    """
    Trace 事件单元，表示一个操作的完整生命周期
    """

    def __init__(
        self,
        name: str,
        level: Union[TraceLevel, str],
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化 Span

        Args:
            name: 事件名称
            level: Trace 层级
            trace_id: 调用链 ID（如果不提供则自动生成）
            parent_span_id: 父 Span ID
            agent_type: Agent 类型（AGENT 层级专用）
            metadata: 元数据
        """
        self.name = name
        self.level = TraceLevel(level) if isinstance(level, str) else level
        self.trace_id = trace_id or self._generate_id()
        self.span_id = self._generate_id()
        self.parent_span_id = parent_span_id
        self.agent_type = agent_type
        self.metadata = metadata or {}

        self.status = TraceStatus.STARTED
        self.timestamp = datetime.now()
        self.start_time_ns = time.perf_counter_ns()
        self.duration_ms: Optional[float] = None

        self.error_message: Optional[str] = None
        self.error_type: Optional[str] = None
        self.error_stack: Optional[str] = None

        # 层级专属数据
        self.input: Optional[Any] = None
        self.output: Optional[Any] = None
        self.thought: Optional[str] = None  # STEP 层级：LLM 思考过程
        self.tool_calls: Optional[Any] = None  # STEP 层级：解析出的工具调用
        self.tool_name: Optional[str] = None  # TOOL 层级：工具名
        self.tool_parameters: Optional[Dict[str, Any]] = None  # TOOL 层级：工具参数
        self.tool_result: Optional[Any] = None  # TOOL 层级：工具结果
        self.llm_provider: Optional[str] = None  # LLM 层级：提供商
        self.llm_model: Optional[str] = None  # LLM 层级：模型名
        self.llm_prompt: Optional[Any] = None  # LLM 层级：Prompt
        self.llm_response: Optional[Any] = None  # LLM 层级：Response
        self.llm_prompt_tokens: Optional[int] = None  # LLM 层级：Prompt Token 数
        self.llm_completion_tokens: Optional[int] = None  # LLM 层级：Completion Token 数
        self.message_history: Optional[Any] = None  # 可选：消息历史

    @staticmethod
    def _generate_id() -> str:
        """生成唯一 ID"""
        return uuid.uuid4().hex[:32]

    def set_input(self, input_data: Any) -> "Span":
        """设置输入数据"""
        self.input = input_data
        return self

    def set_output(self, output_data: Any) -> "Span":
        """设置输出数据"""
        self.output = output_data
        return self

    def set_metadata(self, key_or_dict: Union[str, Dict[str, Any]], value: Any = None) -> "Span":
        """
        设置元数据

        支持两种调用方式：
        1. set_metadata(key, value) - 设置单个键值对
        2. set_metadata(dict) - 批量设置多个键值对
        """
        if isinstance(key_or_dict, dict):
            self.metadata.update(key_or_dict)
        elif value is not None:
            self.metadata[key_or_dict] = value
        return self

    def set_agent_data(self, thought: Optional[str] = None, tool_calls: Optional[Any] = None) -> "Span":
        """设置 STEP 层级数据"""
        if thought is not None:
            self.thought = thought
        if tool_calls is not None:
            self.tool_calls = tool_calls
        return self

    def set_tool_data(self, tool_name: str, parameters: Dict[str, Any], result: Optional[Any] = None) -> "Span":
        """设置 TOOL 层级数据"""
        self.tool_name = tool_name
        self.tool_parameters = parameters
        if result is not None:
            self.tool_result = result
        return self

    def set_llm_data(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt: Optional[Any] = None,
        response: Optional[Any] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> "Span":
        """设置 LLM 层级数据"""
        if provider is not None:
            self.llm_provider = provider
        if model is not None:
            self.llm_model = model
        if prompt is not None:
            self.llm_prompt = prompt
        if response is not None:
            self.llm_response = response
        if prompt_tokens is not None:
            self.llm_prompt_tokens = prompt_tokens
        if completion_tokens is not None:
            self.llm_completion_tokens = completion_tokens
        return self

    def set_message_history(self, history: Any) -> "Span":
        """设置消息历史"""
        self.message_history = history
        return self

    def set_success(self, output: Optional[Any] = None) -> "Span":
        """标记成功"""
        self.status = TraceStatus.COMPLETED
        if output is not None:
            self.output = output
        self._calculate_duration()
        return self

    def set_error(
        self,
        error: Optional[Exception] = None,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> "Span":
        """标记失败"""
        self.status = TraceStatus.FAILED
        if error:
            self.error_message = str(error)
            self.error_type = type(error).__name__
            self.error_stack = traceback.format_exc()
        if error_message:
            self.error_message = error_message
        if error_type:
            self.error_type = error_type
        self._calculate_duration()
        return self

    def finish(self) -> "Span":
        """完成（自动根据是否有错误判断状态）"""
        if self.status == TraceStatus.STARTED:
            self.status = TraceStatus.COMPLETED
        self._calculate_duration()
        return self

    def _calculate_duration(self):
        """计算耗时"""
        if self.duration_ms is None:
            end_time_ns = time.perf_counter_ns()
            self.duration_ms = (end_time_ns - self.start_time_ns) / 1_000_000

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（完整数据）"""
        self._calculate_duration()
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "level": self.level.value if isinstance(self.level, Enum) else self.level,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "agent_type": self.agent_type,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "error_stack": self.error_stack,
            "metadata": self.metadata,
            "input": self.input,
            "output": self.output,
            "thought": self.thought,
            "tool_calls": self.tool_calls,
            "tool_name": self.tool_name,
            "tool_parameters": self.tool_parameters,
            "tool_result": self.tool_result,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_prompt": self.llm_prompt,
            "llm_response": self.llm_response,
            "llm_prompt_tokens": self.llm_prompt_tokens,
            "llm_completion_tokens": self.llm_completion_tokens,
            "message_history": self.message_history,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """转换为摘要字典（用于数据库主表）"""
        self._calculate_duration()
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "level": self.level,
            "name": self.name,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration_ms": int(self.duration_ms) if self.duration_ms else None,
            "agent_type": self.agent_type,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "trace_metadata": self.metadata if self.metadata else None,
        }

    def __repr__(self) -> str:
        return f"<Span(trace_id={self.trace_id}, span_id={self.span_id}, name={self.name}, status={self.status})>"

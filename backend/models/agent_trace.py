"""Agent Trace 追踪系统数据库模型"""

from typing import Optional
from sqlalchemy import (
    String, BigInteger, Integer, DateTime, Text, ForeignKey, JSON,
    Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from models import Base


class TraceLevel(str, Enum):
    """Trace 层级枚举"""
    AGENT = "AGENT"
    STEP = "STEP"
    TOOL = "TOOL"
    LLM = "LLM"


class TraceStatus(str, Enum):
    """Trace 状态枚举"""
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentTrace(Base):
    """Agent Trace 主表（用于查询列表）"""
    __tablename__ = "agent_traces"

    trace_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="调用链唯一ID"
    )
    span_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="当前事件唯一ID"
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="父事件ID"
    )
    level: Mapped[TraceLevel] = mapped_column(
        SQLEnum(TraceLevel),
        nullable=False,
        index=True,
        comment="Trace 层级"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="事件名称"
    )
    status: Mapped[TraceStatus] = mapped_column(
        SQLEnum(TraceStatus),
        nullable=False,
        index=True,
        comment="执行状态"
    )
    timestamp: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="事件时间戳"
    )
    duration_ms: Mapped[Optional[float]] = mapped_column(
        Integer,
        nullable=True,
        comment="耗时（毫秒）"
    )
    agent_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Agent 类型（AGENT 层级专用）"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息（失败时）"
    )
    error_type: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="错误类型"
    )
    trace_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="元数据（JSON）"
    )

    # 关联详情
    detail: Mapped[Optional["AgentTraceDetail"]] = relationship(
        "AgentTraceDetail",
        back_populates="trace",
        cascade="all, delete-orphan",
        uselist=False
    )

    # 索引
    __table_args__ = (
        Index("idx_trace_trace_level", "trace_id", "level"),
        Index("idx_trace_agent_status", "agent_type", "status"),
        Index("idx_trace_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<AgentTrace(id={self.id}, trace_id={self.trace_id}, name={self.name}, status={self.status})>"

    def to_dict(self, include_detail: bool = False) -> dict:
        """转换为字典格式"""
        result = {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "level": self.level.value if self.level else None,
            "name": self.name,
            "status": self.status.value if self.status else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_ms": self.duration_ms,
            "agent_type": self.agent_type,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "trace_metadata": self.trace_metadata,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
        if include_detail and self.detail:
            result["full_data"] = self.detail.full_data
        return result


class AgentTraceDetail(Base):
    """Agent Trace 详情表（存完整 JSON 数据）"""
    __tablename__ = "agent_trace_details"

    trace_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="调用链唯一ID"
    )
    span_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="当前事件唯一ID"
    )
    trace_record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agent_traces.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的主表ID"
    )
    full_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="完整数据（JSON）"
    )

    # 关联主表
    trace: Mapped["AgentTrace"] = relationship(
        "AgentTrace",
        back_populates="detail"
    )

    def __repr__(self):
        return f"<AgentTraceDetail(id={self.id}, trace_id={self.trace_id})>"

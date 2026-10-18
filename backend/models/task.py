"""后台任务模型"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, BigInteger, Integer, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"        # 等待中
    RUNNING = "running"        # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class TaskType:
    """任务类型枚举"""
    TRIP_PLAN = "trip_plan"          # 行程规划
    TRIP_MODIFY = "trip_modify"      # 行程修改
    GUIDE_PARSE = "guide_parse"      # 攻略解析


class Task(Base):
    """后台任务表"""
    __tablename__ = "tasks"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        comment="关联用户ID"
    )

    # 任务类型
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="任务类型：trip_plan/trip_modify/guide_parse等"
    )

    # 关联对象（可选）
    trip_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trip_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的行程ID"
    )
    conversation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的会话ID"
    )

    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="任务状态：pending/running/completed/failed/cancelled"
    )

    # 进度信息
    current_step: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="当前步骤名称"
    )
    step_progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="步骤进度：0-100"
    )
    total_steps: Mapped[int] = mapped_column(
        Integer,
        default=5,
        comment="总步骤数"
    )

    # 输入/输出数据
    input_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="任务输入参数"
    )
    output_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="任务输出结果"
    )

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 时间
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="开始时间"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="结束时间"
    )

    # 控制
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否已取消"
    )

    # 关系
    user: Mapped["User"] = relationship("User")
    trip: Mapped[Optional["TripPlanRecord"]] = relationship("TripPlanRecord")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation")

    def __repr__(self):
        return f"<Task(id={self.id}, type={self.task_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "task_type": self.task_type,
            "trip_id": str(self.trip_id) if self.trip_id else None,
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "status": self.status,
            "current_step": self.current_step,
            "step_progress": self.step_progress,
            "total_steps": self.total_steps,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_cancelled": self.is_cancelled,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

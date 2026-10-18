from datetime import datetime
from typing import List, Optional, Any

from sqlalchemy import String, BigInteger, Integer, DateTime, Text, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Conversation(Base):
    """对话会话模型"""
    __tablename__ = "conversations"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        comment="关联用户ID"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="新对话",
        comment="对话标题"
    )

    # ========== 新增：关联当前行程（1对1） ==========
    current_trip_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trip_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="当前关联的旅行计划ID（1对1）"
    )

    is_deleted: Mapped[bool] = mapped_column(
        Integer,
        default=0,
        comment="是否删除(0=正常,1=已删除)"
    )

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.create_time"
    )
    # ========== 新增：关联行程 ==========
    current_trip: Mapped[Optional["TripPlanRecord"]] = relationship(
        "TripPlanRecord",
        foreign_keys=[current_trip_id]
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title})>"


class Message(Base):
    """对话消息模型"""
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        comment="关联会话ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), 
        comment="消息角色(user/assistant/system)"
    )
    content: Mapped[str] = mapped_column(
        Text, 
        comment="消息内容"
    )
    # 预留字段，用于后续扩展（如token消耗、模型信息等）
    tokens: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        comment="Token消耗数量"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        comment="使用的模型名称"
    )
    thinking_process: Mapped[Optional[List[Any]]] = mapped_column(
        JSON, 
        nullable=True, 
        comment="思考过程，JSON数组格式"
    )

    # 关联关系
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", 
        back_populates="messages"
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.create_time.isoformat() if self.create_time else None,
            "tokens": self.tokens,
            "model": self.model,
            "thinking": self.thinking_process,
        }

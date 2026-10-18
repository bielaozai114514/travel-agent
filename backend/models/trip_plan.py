"""旅行规划数据库模型"""

from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy import String, BigInteger, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class TripPlanRecord(Base):
    """旅行规划记录模型"""
    __tablename__ = "trip_plans"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        comment="关联用户ID"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="旅行计划",
        comment="计划标题"
    )
    city: Mapped[str] = mapped_column(
        String(100),
        comment="目的地城市"
    )
    start_date: Mapped[str] = mapped_column(
        String(20),
        comment="开始日期"
    )
    end_date: Mapped[str] = mapped_column(
        String(20),
        comment="结束日期"
    )
    travel_days: Mapped[int] = mapped_column(
        Integer,
        comment="旅行天数"
    )
    transportation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="交通方式"
    )
    accommodation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="住宿偏好"
    )
    preferences: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="旅行偏好"
    )
    plan_data: Mapped[dict] = mapped_column(
        JSON,
        comment="完整计划数据(JSON格式)"
    )
    is_deleted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="是否删除(0=正常,1=已删除)"
    )

    user: Mapped["User"] = relationship("User", back_populates="trip_plans")

    def __repr__(self):
        return f"<TripPlanRecord(id={self.id}, user_id={self.user_id}, city={self.city})>"

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "city": self.city,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "travel_days": self.travel_days,
            "transportation": self.transportation,
            "accommodation": self.accommodation,
            "preferences": self.preferences,
            "plan_data": self.plan_data,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

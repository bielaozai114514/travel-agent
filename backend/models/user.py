from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, BigInteger, ForeignKey, Table, Column

from models import Base

# 用户-角色 多对多关联表 (中间表, 无额外字段)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(20), comment="用户名")
    hashed_password: Mapped[str] = mapped_column(String(255), comment="加密后的密码")
    email: Mapped[str] = mapped_column(String(255), comment="邮箱")
    # phone: Mapped[str] = mapped_column(String(255), comment="手机号")

    # role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))  # 关联角色 由于是多角色所以不需要
    roles = relationship(
        "Role", secondary="user_roles", back_populates="users", passive_deletes=True
    )
    # 对话会话关联
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    # 旅行规划关联
    trip_plans = relationship(
        "TripPlanRecord", back_populates="user", cascade="all, delete-orphan"
    )
    # 旅游攻略关联
    guides = relationship(
        "TravelGuide", foreign_keys="TravelGuide.author_id", back_populates="author", cascade="all, delete-orphan"
    )

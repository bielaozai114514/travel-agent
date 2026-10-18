from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Table, Column, ForeignKey

from models import Base

# 角色-权限 多对多关联表 中间表 无额外字段
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(255), unique=True, comment="")
    description: Mapped[str] = mapped_column(String(255), comment="权限描述")

    users = relationship("User", secondary="user_roles", back_populates="roles")
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        passive_deletes=True,
    )

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

from models import Base


class Permission(Base):
    __tablename__ = "permissions"

    scope: Mapped[str] = mapped_column(String(255), unique=True, comment="权限范围")
    description: Mapped[str] = mapped_column(
        String(255), unique=True, comment="权限描述"
    )

    # 多对多 角色权限关联（反向关联）
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        passive_deletes=True,
    )
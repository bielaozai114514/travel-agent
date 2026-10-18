"""旅游攻略数据库模型"""

from typing import Optional, List
from sqlalchemy import (
    String, BigInteger, Integer, DateTime, Text, ForeignKey, JSON,
    Boolean, Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from models import Base


class GuideStatus(str, Enum):
    """攻略状态枚举"""
    DRAFT = "draft"  # 草稿
    PENDING = "pending"  # 待审核
    PUBLISHED = "published"  # 已发布
    REJECTED = "rejected"  # 已拒绝
    ARCHIVED = "archived"  # 已归档


class ContentFormat(str, Enum):
    """内容格式枚举"""
    TXT = "txt"
    MARKDOWN = "markdown"
    WORD = "word"
    HTML = "html"
    RICHTEXT = "richtext"


class TravelGuide(Base):
    """旅游攻略主模型"""
    __tablename__ = "travel_guides"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="攻略标题"
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="作者用户ID"
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="相关城市"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="攻略摘要"
    )
    content_format: Mapped[ContentFormat] = mapped_column(
        SQLEnum(ContentFormat),
        nullable=False,
        default=ContentFormat.MARKDOWN,
        comment="内容格式"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="攻略内容（纯文本/Markdown/HTML）"
    )
    content_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="原始文件存储路径（如果上传文件）"
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="标签数组"
    )
    is_official: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否官方攻略"
    )
    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否AI生成"
    )
    status: Mapped[GuideStatus] = mapped_column(
        SQLEnum(GuideStatus),
        nullable=False,
        default=GuideStatus.DRAFT,
        index=True,
        comment="攻略状态"
    )
    review_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="审核意见"
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人用户ID"
    )
    review_time: Mapped[Optional[DateTime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="审核时间"
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="浏览次数"
    )
    like_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="点赞次数"
    )
    comment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="评论次数"
    )
    share_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="分享次数"
    )

    # 关联关系
    author: Mapped["User"] = relationship(
        "User",
        foreign_keys=[author_id],
        back_populates="guides"
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewer_id]
    )
    comments: Mapped[List["GuideComment"]] = relationship(
        "GuideComment",
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="GuideComment.create_time.desc()"
    )
    likes: Mapped[List["GuideLike"]] = relationship(
        "GuideLike",
        back_populates="guide",
        cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_guide_city_status", "city", "status"),
        Index("idx_guide_author_status", "author_id", "status"),
        Index("idx_guide_official", "is_official"),
    )

    def __repr__(self):
        return f"<TravelGuide(id={self.id}, title={self.title}, author_id={self.author_id})>"

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
            "author_name": self.author.username if self.author else None,
            "city": self.city,
            "summary": self.summary,
            "content_format": self.content_format.value if self.content_format else None,
            "content": self.content,
            "content_path": self.content_path,
            "tags": self.tags,
            "is_official": self.is_official,
            "is_ai_generated": self.is_ai_generated,
            "status": self.status.value if self.status else None,
            "review_comment": self.review_comment,
            "reviewer_id": self.reviewer_id,
            "review_time": self.review_time.isoformat() if self.review_time else None,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class GuideComment(Base):
    """攻略评论模型（支持多级回复）"""
    __tablename__ = "guide_comments"

    guide_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("travel_guides.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联攻略ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="评论用户ID"
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("guide_comments.id", ondelete="CASCADE"),
        nullable=True,
        comment="父评论ID（用于多级回复）"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="评论内容"
    )
    like_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="点赞次数"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否删除"
    )

    # 关联关系
    guide: Mapped["TravelGuide"] = relationship(
        "TravelGuide",
        back_populates="comments"
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id]
    )
    parent: Mapped[Optional["GuideComment"]] = relationship(
        "GuideComment",
        remote_side="GuideComment.id",
        backref="replies"
    )

    # 索引
    __table_args__ = (
        Index("idx_comment_guide", "guide_id"),
        Index("idx_comment_parent", "parent_id"),
        Index("idx_comment_user", "user_id"),
    )

    def __repr__(self):
        return f"<GuideComment(id={self.id}, guide_id={self.guide_id}, user_id={self.user_id})>"

    def to_dict(self, include_replies: bool = True) -> dict:
        """转换为字典格式"""
        result = {
            "id": self.id,
            "guide_id": self.guide_id,
            "user_id": self.user_id,
            "user_name": self.user.username if self.user else None,
            "parent_id": self.parent_id,
            "content": self.content,
            "like_count": self.like_count,
            "is_deleted": self.is_deleted,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
        if include_replies and self.replies:
            result["replies"] = [
                reply.to_dict(include_replies=True)
                for reply in self.replies if not reply.is_deleted
            ]
        return result


class GuideLike(Base):
    """攻略点赞模型（防止重复点赞）"""
    __tablename__ = "guide_likes"

    guide_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("travel_guides.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联攻略ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="点赞用户ID"
    )

    # 关联关系
    guide: Mapped["TravelGuide"] = relationship(
        "TravelGuide",
        back_populates="likes"
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id]
    )

    # 唯一约束：一个用户对一篇攻略只能点赞一次
    __table_args__ = (
        UniqueConstraint("guide_id", "user_id", name="uq_guide_user_like"),
        Index("idx_like_guide", "guide_id"),
        Index("idx_like_user", "user_id"),
    )

    def __repr__(self):
        return f"<GuideLike(guide_id={self.guide_id}, user_id={self.user_id})>"

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func, BigInteger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime
import os

from settings import settings
from utils.snowflake_id import generate_snowflake_id


class Base(DeclarativeBase):
    """基类：ID + 创建时间 + 更新时间"""
    
    id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True, 
        default=generate_snowflake_id,
        comment="主键ID(雪花ID)"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, insert_default=func.now(), default=func.now(), comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        insert_default=func.now(),
        default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


# 在连接数据库之前记得先创建对应的数据库
# CREATE DATABASE fastapi_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
# 判断是否为测试环境
if settings.TEST_ENV == True:
    # 测试环境：替换数据库名为 test_travel_agent
    from urllib.parse import urlparse, urlunparse
    url = urlparse(settings.MYSQL_URL)
    # 替换路径部分（数据库名）
    url = url._replace(path="/test_travel_agent")
    ASYNC_DATABASE_URL = urlunparse(url)
else:
    # 生产/开发环境
    ASYNC_DATABASE_URL = settings.MYSQL_URL

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    # echo = True, # 输出数据库日志
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,  # 指定会话类
    expire_on_commit=False,  # 提交会话不过期
    autoflush=True,  # 是否在查找之情进行刷新操作
)


# 开始建表 Fastapi启动的时候调用建表的函数 如果表已经被创建则删除原先的表重新创建一遍
async def create_table():
    # 获取异步引擎创建事物
    async with async_engine.begin() as coon:
        await coon.run_sync(Base.metadata.create_all)  # Base 模型类的元数据创建


# 一次性导入所有模型，确保 Base.metadata 完整，避免漏建表。
from models.user import User, user_roles
from models.role import Role, role_permissions
from models.permission import Permission
from models.conversation import Conversation, Message
from models.trip_plan import TripPlanRecord
from models.guide import TravelGuide, GuideComment, GuideLike
from models.agent_trace import AgentTrace, AgentTraceDetail
from models.task import Task

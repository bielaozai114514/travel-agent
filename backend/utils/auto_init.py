
"""
自动初始化数据库模块
在应用启动时自动初始化权限和管理员
"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import logger
from settings import settings


async def create_database_if_not_exists():
    """异步创建数据库（如果不存在）"""
    try:
        # 解析数据库URL
        if settings.TEST_ENV:
             url = urlparse(settings.MYSQL_TEST_URL)
        else:
            url = urlparse(settings.MYSQL_URL)
        db_name = url.path.lstrip('/')

        # 构建不带数据库名的连接URL
        if url.query:
            base_url = settings.MYSQL_URL.replace(f"/{db_name}?{url.query}", f"/?{url.query}")
        else:
            base_url = settings.MYSQL_URL.replace(f"/{db_name}", "/")

        # 导入需要的模块
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        # 创建临时引擎连接到MySQL服务器（不指定数据库）
        temp_engine = create_async_engine(base_url)

        async with temp_engine.connect() as conn:
            # 检查数据库是否存在
            result = await conn.execute(text(f"SHOW DATABASES LIKE :db_name"), {"db_name": db_name})
            exists = result.fetchone()

            if exists:
                logger.info(f"数据库 '{db_name}' 已存在")
            else:
                # 创建数据库
                await conn.execute(text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                await conn.commit()
                logger.info(f"数据库 '{db_name}' 创建成功")

        await temp_engine.dispose()
        return True
    except Exception as e:
        logger.warning(f"创建数据库失败: {e}")
        return False


async def init_permissions():
    """初始化权限数据"""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from dependencies.db_session import AsyncSessionLocal
        from models.permission import Permission
        from models.role import Role

        async with AsyncSessionLocal() as session:
            # 检查是否已有权限数据
            result = await session.execute(select(Permission).limit(1))
            if result.scalars().first():
                logger.info("权限已经存在跳过初始化")
                return True

        # 如果没有数据，调用初始化函数
        from utils.init_permissions import init_permissions as init_perms_func
        await init_perms_func()
        logger.info("权限初始化成功")
        return True
    except Exception as e:
        logger.warning(f"权限初始化错误: {e}")
        return False


async def init_admin():
    """初始化管理员账号"""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from dependencies.db_session import AsyncSessionLocal
        from models.user import User
        from models.role import Role
        from core.security import get_password_hash

        async with AsyncSessionLocal() as session:
            # 检查管理员是否已存在
            result = await session.execute(select(User).where(User.username == "admin"))
            if result.scalars().first():
                logger.info("管理员账号已经存在，跳过初始化")
                return True

            # 获取 admin 角色
            admin_role = await session.scalar(select(Role).where(Role.name == "admin"))
            if not admin_role:
                logger.warning("管理员role不存在，无法创建管理员user")
                return False

            logger.info("管理员账号不存在，创建管理员账号")

            # 创建管理员
            admin = User(
                username="admin",
                email="admin@test.com",
                hashed_password=get_password_hash("admin123456"),
            )
            admin.roles = [admin_role]

            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            logger.info(f" 管理员账号 {admin.username} 创建成功")
            return True
    except Exception as e:
        logger.warning(f"管理员初始初始化错误: {e}")
        return False


async def auto_init_database(create_db: bool = False):
    """自动初始化数据库
    Args:
        create_db: 是否创建数据库（仅手动执行时设为True）
    """
    logger.info("=" * 50)
    logger.info("检查是否创建数据库...")
    logger.info("=" * 50)

    if settings.TEST_ENV:
            url = urlparse(settings.MYSQL_TEST_URL)
    else:
        url = urlparse(settings.MYSQL_URL)
    db_name = url.path.lstrip('/')

    if create_db:
        # 1. 创建数据库（如果不存在）
        await create_database_if_not_exists()
        await asyncio.sleep(0.5)

        # 2. 创建表结构
        from models import create_table
        await create_table()
        await asyncio.sleep(0.5)
    else:
        logger.info("=" * 50)
        logger.info(f"数据库 '{db_name}' 已存在")
        logger.info("=" * 50)


    # 3. 初始化权限
    logger.info("=" * 50)
    logger.info("开始初始化权限...")
    logger.info("=" * 50)
    await init_permissions()
    await asyncio.sleep(0.5)

    # 4. 初始化管理员
    logger.info("=" * 50)
    logger.info("开始初始化管理员账号...")
    logger.info("=" * 50)
    await init_admin()

    logger.info("=" * 50)
    logger.info("数据库初始化完成!")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(auto_init_database(create_db=True))


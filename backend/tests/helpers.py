
"""
测试辅助模块
"""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


async def clear_all_tables():
    """
    清空所有测试表数据（按依赖顺序）
    注意：这会直接连接数据库，不依赖 FastAPI 应用
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text
    from urllib.parse import urlparse, urlunparse
    import os

    # 构建测试数据库 URL
    from settings import settings
    url = urlparse(settings.MYSQL_URL)
    url = url._replace(path="/test_travel_agent")
    test_db_url = urlunparse(url)

    engine = create_async_engine(test_db_url)

    # 按依赖顺序清空表（先清空关联表，再清空主表）
    tables_to_clear = [
        "user_roles", "role_permissions",
        "users", "roles", "permissions",
        "messages", "conversations",
        "trip_plan_records",
        "guide_comments", "guide_likes", "travel_guides",
        "agent_trace_details", "agent_traces",
        "tasks",
    ]

    async with AsyncSession(bind=engine) as session:
        for table in tables_to_clear:
            try:
                await session.execute(text(f"DELETE FROM `{table}`"))
            except Exception:
                pass  # 表不存在就跳过
        await session.commit()

    await engine.dispose()


async def init_test_database():
    """
    初始化测试数据库（创建库、表、权限、管理员）
    手动运行一次即可
    """
    import os
    os.environ["ENV"] = "test"

    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.auto_init import auto_init_database
    await auto_init_database(create_db=True)


if __name__ == "__main__":
    asyncio.run(init_test_database())


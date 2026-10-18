import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# 导入你的现有配置
from dependencies.db_session import get_db, AsyncSessionLocal
from models import Base
from models.user import User
from models.role import Role
from core.security import get_password_hash


async def init_admin(session: AsyncSession):
    # 获取admin角色
    admin_role = await session.scalar(select(Role).where(Role.name == "admin"))

    admin = User(
        username="admin",
        email="admin@test.com",
        hashed_password=get_password_hash("admin123456"),
    )

    admin.roles = [admin_role]

    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    print(f"🎉 用户 {admin.username} 注册成功")


async def main():
    """主函数：手动管理会话和事件循环"""
    # 手动创建会话
    async with AsyncSessionLocal() as session:
        try:
            await init_admin(session)
        except Exception as e:
            await session.rollback()
            print(f"❌ 初始化失败：{str(e)}")
            raise e

    # 3. 显式延迟，确保连接完全关闭（关键：消除event loop closed警告）
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    # 手动创建事件循环，避免asyncio.run的快速关闭问题
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        # 优雅关闭循环
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

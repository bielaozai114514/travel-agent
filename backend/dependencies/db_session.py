from models import AsyncSessionLocal


# 依赖
async def get_db():
    """
    获取一个异步的数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()

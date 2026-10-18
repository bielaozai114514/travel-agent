import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# 导入你的现有配置
from dependencies.db_session import get_db, AsyncSessionLocal
from models import Base
from models.role import Role, role_permissions
from models.permission import Permission
from settings import settings

# 权限定义
PERMISSIONS = [
    ("users:read", "查看用户信息"),
    ("users:write", "创建/修改用户"),
    ("users:delete", "删除用户"),
    ("roles:read", "查看角色列表"),
    ("roles:write", "管理角色"),
    ("permissions:read", "查看权限列表"),
    ("permissions:write", "管理权限"),
    ("sessions:read", "查看对话历史"),
    ("sessions:write", "创建新对话"),
    ("sessions:delete", "删除对话"),
    ("messages:create", "发送消息"),
    ("messages:read", "查看消息"),
    ("messages:delete", "删除消息"),
    ("admin:settings", "修改系统设置"),
    ("admin:roles", "管理角色权限"),
    ("chat:send", "发送聊天消息"),
    # 旅游攻略相关权限
    ("guides:read", "查看旅游攻略"),
    ("guides:write", "创建/编辑旅游攻略"),
    ("guides:delete", "删除旅游攻略"),
    ("guides:admin", "审核和管理旅游攻略"),
    # 后台任务相关权限
    ("tasks:read", "查看后台任务"),
    ("tasks:write", "管理后台任务"),
]

ROLES = {
    "admin": {
        "scopes": [
            "users:read", "users:write", "users:delete",
            "roles:read", "roles:write",
            "permissions:read", "permissions:write",
            "sessions:read", "sessions:write", "sessions:delete",
            "messages:create", "messages:read", "messages:delete",
            "admin:settings", "admin:roles",
            "chat:send",
            "guides:read", "guides:write", "guides:delete", "guides:admin",
            "tasks:read", "tasks:write",
        ],
        "description": "系统管理员，拥有所有权限"
    },
    "user": {
        "scopes": [
            "sessions:read", "sessions:write", "messages:create", "messages:read",
            "chat:send",
            "guides:read", "guides:write",
            "tasks:read",
        ],
        "description": "普通用户，可查看和创建攻略"
    },
    "moderator": {
        "scopes": [
            "sessions:read", "messages:create", "messages:read", "messages:delete",
            "chat:send",
            "guides:read", "guides:admin",
            "tasks:read",
        ],
        "description": "内容审核员，可审核攻略"
    },
    "guide_admin": {
        "scopes": [
            "chat:send",
            "guides:read", "guides:write", "guides:delete", "guides:admin",
            "tasks:read",
        ],
        "description": "攻略管理员，可管理所有旅游攻略"
    },
}


async def init_permissions():
    # # 1. 创建数据库表（如果不存在）
    # try:
    #     async with AsyncSessionLocal.bind.begin() as conn:
    #         await conn.run_sync(Base.metadata.create_all)
    #     print("✅ 数据库表检查/创建完成")
    # except AttributeError:
    #     # 兼容 AsyncSessionLocal 没有 bind 属性的情况
    #     from db import async_engine
    #     async with async_engine.begin() as conn:
    #         await conn.run_sync(Base.metadata.create_all)
    #     print("✅ 数据库表检查/创建完成")

    # 2. 遍历 get_db 获取会话
    async for session in get_db():
        try:
            # 检查是否已有权限数据，避免重复初始化
            existing_perm = await session.execute(Permission.__table__.select().limit(1))
            if existing_perm.scalars().first():
                print("⚠️  权限数据已存在，跳过初始化！")
                break

            # 3. 创建权限
            permission_map = {}
            for scope, desc in PERMISSIONS:
                perm = Permission(scope=scope, description=desc)
                session.add(perm)
                await session.flush()  # 获取 ID
                permission_map[scope] = perm.id

            # 4. 创建角色并绑定权限（🔥 关键修改：传入 description）
            for role_name, role_info in ROLES.items():
                # 创建角色时补充 description 字段
                role = Role(
                    name=role_name,
                    description=role_info["description"]  # 新增这一行
                )
                session.add(role)
                await session.flush()

                # 插入中间表
                for scope in role_info["scopes"]:
                    stmt = role_permissions.insert().values(
                        role_id=role.id,
                        permission_id=permission_map[scope],
                    )
                    await session.execute(stmt)

            await session.commit()
            print("🎉 权限系统初始化成功！")
            print(f"  角色: {list(ROLES.keys())}")
            print(f"  权限数: {len(PERMISSIONS)}")
            break  # 终止遍历，避免挂起

        except Exception as e:
            await session.rollback()
            print(f"❌ 初始化失败：{str(e)}")
            raise e


if __name__ == "__main__":
    asyncio.run(init_permissions())
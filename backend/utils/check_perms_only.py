"""仅查看现有权限和角色"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from dependencies.db_session import AsyncSessionLocal
from models.permission import Permission
from models.role import Role


async def main():
    async with AsyncSessionLocal() as session:
        # 查看权限
        print('=' * 60)
        print('           现有权限列表')
        print('=' * 60)
        perms = await session.execute(select(Permission).order_by(Permission.scope))
        perm_dict = {}
        for p in perms.scalars().all():
            print(f'  {p.scope:<25} - {p.description}')
            perm_dict[p.scope] = p

        print(f'\n总计: {len(perm_dict)} 个权限\n')

        # 查看角色
        print('=' * 60)
        print('           现有角色及权限')
        print('=' * 60)
        roles = await session.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        )
        for r in roles.scalars().all():
            perms_list = sorted([p.scope for p in r.permissions])
            print(f'\n  【{r.name}】')
            print(f'  描述: {r.description}')
            print(f'  权限: {", ".join(perms_list) if perms_list else "无"}')

        print('\n' + '=' * 60)


if __name__ == '__main__':
    asyncio.run(main())

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any, Optional, Tuple

from models.user import User
from models.role import Role
from core.logger import logger
from core.security import get_password_hash
from core.exceptions import ResourceNotFoundError, ResourceAlreadyExistsError
from schemas.user import UserRegister, UserUpdate
from schemas import PageParams


async def get_user_by_id(
    user_id: int, session: AsyncSession, load_roles: bool = False
) -> User:
    """
    获取用户
    :param user_id: 用户id
    :param session: 异步数据库会话
    :param load_roles: 是否预加载角色和权限
    :return: 有数据返回User对象
    """
    try:
        stmt = select(User).where(User.id == user_id)
        if load_roles:
            stmt = stmt.options(selectinload(User.roles).selectinload(Role.permissions))

        user = await session.scalar(stmt)

        if user is None:
            raise ResourceNotFoundError(f"用户ID={user_id} 不存在")

        logger.info(f"成功查询到用户ID={user_id} 的用户：{user.username}")
        return user
    except SQLAlchemyError as e:
        logger.error(f"查询用户失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def get_users_by_ids(user_ids: List[int], session: AsyncSession) -> List[User]:
    """
    批量查询用户
    :param user_ids: 用户ID列表
    :param session: 异步数据库会话
    :return: 用户列表
    """
    try:
        if not user_ids:
            return []

        stmt = (
            select(User).where(User.id.in_(user_ids)).options(selectinload(User.roles))
        )
        result = await session.scalars(stmt)
        users = result.all()

        # 校验是否有不存在的ID
        existing_ids = {u.id for u in users}
        missing_ids = [uid for uid in user_ids if uid not in existing_ids]
        if missing_ids:
            logger.warning(f"批量查询用户：部分ID不存在，missing_ids={missing_ids}")

        return users
    except SQLAlchemyError as e:
        logger.error(
            f"批量查询用户异常（数据库异常）：user_ids={user_ids}，错误={str(e)}"
        )
        raise


async def get_user_by_email(email: str, session: AsyncSession) -> User:
    """
    通过邮箱获取用户, 同时预加载角色和权限
    :param email: 用户邮箱
    :param session: 异步数据库会话
    :return: 有数据返回User对象，无数据返回None
    """
    try:
        # 无数据返回None，有数据返回User实例
        stmt = (
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        user = await session.scalar(stmt)

        if user is None:
            raise ResourceNotFoundError(f"用户邮箱={email} 不存在")

        logger.debug(f"成功查询到邮箱为 {email} 的用户：{user.username}")

        return user

    except SQLAlchemyError as e:
        logger.error(f"查询用户失败（数据库异常）：邮箱={email}，错误={str(e)}")
        raise


async def get_user_by_username(username: str, session: AsyncSession) -> User:
    """
    通过用户名获取用户
    :param username: 用户名
    :param session: 异步数据库会话
    :return: 有数据返回User对象，无数据返回None
    """
    try:
        # 无数据返回None
        stmt = (
            select(User)
            .where(User.username == username)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )

        user = await session.scalar(stmt)

        if user is None:
            raise ResourceNotFoundError(f"用户名称={username} 不存在")

        logger.info(f"成功查询到用户名称为 {username} 的用户：{user.username}")
        return user

    except SQLAlchemyError as e:
        logger.error(f"查询用户失败（数据库异常）：用户名称={username}，错误={str(e)}")
        raise


async def get_user_by_id_with_roles(user_id: int, session: AsyncSession) -> User:
    """
    获取用户及其角色和权限信息
    :param user_id: 用户ID
    :param session: 异步数据库会话
    :return: 包含角色和权限的用户对象
    """
    try:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        user = await session.scalar(stmt)

        if user is None:
            raise ResourceNotFoundError(f"用户ID={user_id} 不存在")

        return user
    except SQLAlchemyError as e:
        logger.error(f"查询用户失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def get_user_by_email_or_username(
    email: str, username: str, session: AsyncSession
) -> User:
    """
    检查邮箱/用户名是否已存在
    :param email: 用户邮箱
    :param username: 用户名
    :param session: 异步数据库会话
    :return: 有数据返回User对象，无数据返回None
    """
    try:
        user = await session.scalar(
            select(User)
            .where((User.email == email) | (User.username == username))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )

        if user is None:
            raise ResourceNotFoundError(
                f"用户邮箱={email} 或 用户名称={username} 不存在"
            )

        logger.info(
            f"成功查询到邮箱/用户名为 {email} 或 {username} 的用户：{user.username}"
        )
        return user
    except SQLAlchemyError as e:
        logger.error(
            f"查询用户失败（邮箱/用户名）：email={email}, username={username}, 错误={str(e)}"
        )
        raise


async def get_user_list(
    session: AsyncSession,
    load_roles: bool = False,
    page_params: PageParams = None,  # 新增分页参数（默认None兼容旧逻辑）
) -> Tuple[List[User], int]:
    """
    获取所有用户列表（带分页）
    :param session: 异步数据库会话
    :param load_roles: 是否预加载角色（默认False）
    :param page_params: 分页参数（None时返回全部数据）
    :return: 用户列表 + 总条数
    """
    try:
        stmt = select(User)
        if load_roles:
            stmt = stmt.options(selectinload(User.roles))

        # 查询总条数
        count_stmt = select(func.count(User.id))
        total = await session.scalar(count_stmt)

        # 如果有分页参数，添加分页逻辑
        if page_params:
            offset = (page_params.page_num - 1) * page_params.page_size
            stmt = stmt.offset(offset).limit(page_params.page_size)

        # 执行查询
        result = await session.scalars(stmt)
        users: List[User] = result.all()

        if len(users) == 0:
            logger.info(
                f"未查询到用户（分页：{page_params}）"
                if page_params
                else "未查询到用户"
            )
        return users, total
    except SQLAlchemyError as e:
        logger.error(f"查询用户列表失败（数据库异常）：错误={str(e)}")
        raise


async def create_user(user_in: UserRegister, session: AsyncSession) -> User:
    """
    创建用户
    :param user: user注册数据 pydantic模型
    :param session: 异步数据库会话
    :return: 创建成功返回User对象
    """
    try:
        exist_user = await session.scalar(
            select(User).where(
                (User.email == user_in.email) | (User.username == user_in.username)
            )
        )
        if exist_user:
            raise ResourceAlreadyExistsError(
                f"用户已存在：邮箱={user_in.email} 或 用户名={user_in.username}"
            )

        # 检查基础角色
        user_role = await session.scalar(select(Role).where(Role.name == "user"))
        if not user_role:
            logger.error("注册失败：未找到 'user' 角色")
            raise ResourceNotFoundError("系统初始化未完成，缺少基础角色")

        # 密码加密
        hashed_pwd = get_password_hash(user_in.password)

        # 创建User实例
        new_user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hashed_pwd,
            roles=[user_role],
        )

        session.add(new_user)  # 添加到会话
        await session.commit()  # 提交会话
        await session.refresh(new_user)  # 刷新会话

        logger.info(f"成功创建用户：{new_user.username}")
        return new_user

    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"创建用户失败（数据库异常）：用户邮箱={user_in.email}，错误={str(e)}"
        )
        raise  # 全局异常处理器去转化成HTTP异常


async def delete_user(user_id: int, session: AsyncSession) -> None:
    """
    删除用户
    :param user_id: 用户id
    :param session: 异步数据库会话
    :return: 无返回值
    :raises ResourceNotFoundError: 用户不存在时抛出
    """
    try:
        # 先检查用户存在性
        user = await get_user_by_id(user_id, session)
        
        if not user:
            raise ResourceNotFoundError(f"用户ID {user_id} 不存在")
        
        # 禁止删除admin用户
        if user.username == 'admin':
            logger.warning(f"尝试删除系统管理员用户：ID={user_id}，用户名={user.username}")
            raise ValueError("系统管理员账户不可删除")

        await session.delete(user)
        await session.commit()
        logger.info(f"成功删除用户：ID={user_id}，用户名={user.username}")

    except ResourceNotFoundError:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"删除用户失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def batch_delete_users(
    user_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量删除用户
    : param user_ids: 用户ID列表（长度1=单个，长度>1=批量）
    : param session: 异步数据库会话
    : return: 操作结果（成功/失败ID）
    """
    try:
        if not user_ids:
            raise ValueError("user_ids 不能为空列表")

        # 批量查询用户
        users = await get_users_by_ids(user_ids, session)
        existing_ids = {u.id for u in users}

        # 检查是否包含admin用户
        admin_users = [user for user in users if user.username == 'admin']
        if admin_users:
            admin_ids = [user.id for user in admin_users]
            logger.warning(f"尝试批量删除系统管理员用户：IDs={admin_ids}")
            raise ValueError("系统管理员账户不可删除")

        # 执行删除
        for user in users:
            await session.delete(user)
        await session.commit()

        # 整理结果
        success_ids = list(existing_ids)
        failed_ids = [uid for uid in user_ids if uid not in existing_ids]

        logger.info(f"批量删除用户完成：成功ID={success_ids}，失败ID={failed_ids}")
        return {
            "success": True,
            "message": "批量删除用户完成",
            "data": {
                "success_ids": success_ids,
                "failed_ids": failed_ids,
                "failed_reason": "失败ID对应用户不存在" if failed_ids else "",
            },
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量删除用户失败（数据库异常）：user_ids={user_ids}，错误={str(e)}"
        )
        raise


async def update_user(user_id: int, user_in: UserUpdate, session: AsyncSession) -> User:
    """
    更新用户
    :param user_id: 用户id
    :param user_in: user更新数据 pydantic模型
    :param session: 异步数据库会话
    :return: user更新后的对象
    """
    try:
        user = await get_user_by_id(user_id, session)

        user_data = user_in.model_dump(exclude_unset=True)

        if "password" in user_data:
            user_data["hashed_password"] = get_password_hash(user_data.pop("password"))

        for key, value in user_data.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        await session.commit()
        await session.refresh(user)

        logger.info(f"成功更新用户：ID={user_id}，用户名={user.username}")
        return user

    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"更新用户失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def get_user_roles(user_id: int, session: AsyncSession) -> Dict[str, Any]:
    """
    查看指定用户已绑定的所有角色（新增）
    :param user_id: 用户ID
    :param session: 异步数据库会话
    :return: 用户信息 + 角色列表
    """
    try:
        user = await get_user_by_id(user_id, session, load_roles=True)

        # 整理角色数据 - ID转为字符串避免JavaScript精度丢失
        roles = [
            {"id": str(r.id), "name": r.name, "description": r.description}
            for r in user.roles
        ]

        return {
            "success": True,
            "message": "获取用户角色成功",
            "data": {
                "user": {"id": str(user.id), "username": user.username, "email": user.email},
                "roles": roles,
                "role_count": len(roles),
            },
        }
    except SQLAlchemyError as e:
        logger.error(f"获取用户角色失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def bind_roles_to_user(
    user_id: int, role_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    增量绑定角色到用户
    :param user_id: 用户id
    :param role_ids: 角色id列表
    :param session: 异步数据库会话
    :return: 操作结果 + 绑定后的用户
    """
    try:
        # 查询用户并预加载现有角色
        user = await session.scalar(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        if not user:
            raise ResourceNotFoundError(f"用户ID {user_id} 不存在")

        # 筛选出未绑定的角色ID
        existing_role_ids = {r.id for r in user.roles}
        need_bind_ids = list(set(role_ids) - existing_role_ids)

        if not need_bind_ids:
            logger.info(f"用户ID {user_id} 已绑定所有指定角色，无需新增")
            return {
                "success": True,
                "message": "无需新增角色（已绑定所有指定角色）",
                "data": {"user": user, "added_role_ids": []},
            }

        # 查询要绑定的角色
        roles = await session.scalars(select(Role).where(Role.id.in_(need_bind_ids)))
        role_list = roles.all()

        # 检查是否有不存在的角色ID
        found_ids = {r.id for r in role_list}
        missing_ids = [rid for rid in need_bind_ids if rid not in found_ids]
        if missing_ids:
            raise ResourceNotFoundError(f"角色ID不存在：{missing_ids}")

        # 增量添加
        user.roles.extend(role_list)
        await session.commit()
        await session.refresh(user)

        logger.info(
            f"用户增量绑定角色成功：用户ID={user_id}，新增角色ID={need_bind_ids}"
        )
        return {
            "success": True,
            "message": "用户绑定角色成功",
            "data": {"user": user, "added_role_ids": need_bind_ids},
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"用户绑定角色失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def unbind_roles_from_user(
    user_id: int, role_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    解绑用户角色（优化返回值：包含解绑ID）
    :param user_id: 用户id
    :param role_ids: 角色id列表
    :param session: 异步数据库会话
    :return: 操作结果 + 解绑后的用户
    """
    try:
        # 查询用户并预加载现有角色
        user = await session.scalar(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        if not user:
            raise ResourceNotFoundError(f"用户ID {user_id} 不存在")

        # 筛选出已绑定的角色（不存在的ID跳过）
        existing_roles = {r.id: r for r in user.roles}
        need_unbind_roles = [
            existing_roles[rid] for rid in role_ids if rid in existing_roles
        ]

        if not need_unbind_roles:
            logger.info(f"用户ID {user_id} 未绑定任何指定的角色，无需解绑")
            return {
                "success": True,
                "message": "无需解绑角色（未绑定任何指定角色）",
                "data": {"user": user, "unbind_role_ids": []},
            }

        # 批量解绑
        for role in need_unbind_roles:
            user.roles.remove(role)

        await session.commit()
        await session.refresh(user)

        unbind_ids = [r.id for r in need_unbind_roles]
        logger.info(f"用户批量解绑角色成功：用户ID={user_id}，解绑角色ID={unbind_ids}")
        return {
            "success": True,
            "message": "用户解绑角色成功",
            "data": {"user": user, "unbind_role_ids": unbind_ids},
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"用户解绑角色失败（数据库异常）：用户ID={user_id}，错误={str(e)}")
        raise


async def batch_bind_roles_to_users(
    user_ids: List[int], role_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量给多个用户绑定指定角色
    : param user_ids: 用户ID列表（单个/多个）
    : param role_ids: 角色ID列表（单个/多个）
    : param session: 异步数据库会话
    : return: 操作结果（每个用户的绑定状态）
    """
    try:
        if not user_ids:
            raise ValueError("user_ids 不能为空列表")
        if not role_ids:
            raise ValueError("role_ids 不能为空列表")

        # 批量查询所有目标用户 预加载现有角色
        users = await session.scalars(
            select(User).where(User.id.in_(user_ids)).options(selectinload(User.roles))
        )
        user_list = users.all()
        existing_user_ids = {u.id for u in user_list}

        # 批量查询所有目标角色
        roles = await session.scalars(select(Role).where(Role.id.in_(role_ids)))
        role_list = roles.all()
        existing_role_ids = {r.id for r in role_list}

        # 整理缺失的ID
        missing_user_ids = [uid for uid in user_ids if uid not in existing_user_ids]
        missing_role_ids = [rid for rid in role_ids if rid not in existing_role_ids]

        # 逐个用户处理绑定逻辑
        user_bind_results = {}
        for user in user_list:
            # 筛选该用户未绑定的角色
            user_existing_roles = {r.id for r in user.roles}
            need_bind_ids = list(existing_role_ids - user_existing_roles)

            if not need_bind_ids:
                user_bind_results[user.id] = {
                    "status": "success",
                    "message": "已绑定所有指定角色，无需新增",
                    "added_role_ids": [],
                }
                continue

            # 筛选要绑定的角色对象
            need_bind_roles = [r for r in role_list if r.id in need_bind_ids]
            user.roles.extend(need_bind_roles)

            user_bind_results[user.id] = {
                "status": "success",
                "message": "增量绑定角色成功",
                "added_role_ids": need_bind_ids,
            }

        # 提交事务
        await session.commit()

        # 整理最终结果
        result = {
            "success": True,
            "message": "批量绑定用户角色完成",
            "data": {
                "total_user_count": len(user_ids),
                "success_user_count": len(existing_user_ids),
                "failed_user_count": len(missing_user_ids),
                "missing_user_ids": missing_user_ids,
                "missing_role_ids": missing_role_ids,
                "user_bind_details": user_bind_results,
            },
        }

        logger.info(
            f"批量绑定用户角色完成：成功用户数={len(existing_user_ids)}，失败用户数={len(missing_user_ids)}"
        )
        return result
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量绑定用户角色失败（数据库异常）：user_ids={user_ids}，role_ids={role_ids}，错误={str(e)}"
        )
        raise


async def batch_unbind_roles_from_users(
    user_ids: List[int], role_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量给多个用户解绑指定角色
    : param user_ids: 用户ID列表（单个/多个）
    : param role_ids: 角色ID列表（单个/多个）
    : param session: 异步数据库会话
    : return: 操作结果（每个用户的解绑状态）
    """
    try:
        if not user_ids:
            raise ValueError("user_ids 不能为空列表")
        if not role_ids:
            raise ValueError("role_ids 不能为空列表")

        # 批量查询所有目标用户
        users = await session.scalars(
            select(User).where(User.id.in_(user_ids)).options(selectinload(User.roles))
        )
        user_list = users.all()
        existing_user_ids = {u.id for u in user_list}

        # 整理缺失的用户ID
        missing_user_ids = [uid for uid in user_ids if uid not in existing_user_ids]

        # 逐个用户处理解绑逻辑
        user_unbind_results = {}
        for user in user_list:
            # 筛选该用户已绑定的目标角色
            user_roles = {r.id: r for r in user.roles}
            need_unbind_roles = [
                user_roles[rid] for rid in role_ids if rid in user_roles
            ]

            if not need_unbind_roles:
                user_unbind_results[user.id] = {
                    "status": "success",
                    "message": "未绑定任何指定角色，无需解绑",
                    "unbind_role_ids": [],
                }
                continue

            # 执行解绑
            for role in need_unbind_roles:
                user.roles.remove(role)

            unbind_ids = [r.id for r in need_unbind_roles]
            user_unbind_results[user.id] = {
                "status": "success",
                "message": "解绑角色成功",
                "unbind_role_ids": unbind_ids,
            }

        # 提交事务
        await session.commit()

        # 整理最终结果
        result = {
            "success": True,
            "message": "批量解绑用户角色完成",
            "data": {
                "total_user_count": len(user_ids),
                "success_user_count": len(existing_user_ids),
                "failed_user_count": len(missing_user_ids),
                "missing_user_ids": missing_user_ids,
                "user_unbind_details": user_unbind_results,
            },
        }

        logger.info(
            f"批量解绑用户角色完成：成功用户数={len(existing_user_ids)}，失败用户数={len(missing_user_ids)}"
        )
        return result
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量解绑用户角色失败（数据库异常）：user_ids={user_ids}，role_ids={role_ids}，错误={str(e)}"
        )
        raise

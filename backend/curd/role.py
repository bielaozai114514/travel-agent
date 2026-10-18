from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any, Tuple

from models.role import Role
from models.permission import Permission
from schemas.role import RoleCreate, RoleUpdate
from schemas import PageParams
from core.logger import logger
from core.exceptions import ResourceAlreadyExistsError, ResourceNotFoundError


async def get_role_by_id(role_id: int, session: AsyncSession) -> Role:
    """
    通过ID获取角色
    :param role_id: 角色ID
    :param session: 异步数据库会话
    :return: 角色
    """
    try:
        role = await session.scalar(select(Role).where(Role.id == role_id))
        if not role:
            raise ResourceNotFoundError(f"角色不存在：ID={role_id}")
        return role
    except SQLAlchemyError as e:
        logger.error(f"查询角色异常（数据库异常）：ID={role_id}，错误={str(e)}")
        raise


async def get_roles_by_ids(role_ids: List[int], session: AsyncSession) -> List[Role]:
    """
    批量查询角色
    :param role_ids: 角色ID列表
    :param session: 异步数据库会话
    :return: 角色列表
    """
    try:
        if not role_ids:
            return []

        result = await session.scalars(select(Role).where(Role.id.in_(role_ids)))
        roles = result.all()

        existing_ids = {r.id for r in roles}
        missing_ids = [rid for rid in role_ids if rid not in existing_ids]
        if missing_ids:
            logger.warning(f"批量查询角色：部分ID不存在，missing_ids={missing_ids}")

        return roles
    except SQLAlchemyError as e:
        logger.error(
            f"批量查询角色异常（数据库异常）：role_ids={role_ids}，错误={str(e)}"
        )
        raise


async def get_role_by_name(name: str, session: AsyncSession) -> Role:
    """
    通过角色名称获取角色
    :param name: 角色名称
    :param session: 异步数据库会话
    :return: 角色
    """
    try:
        result = await session.scalar(select(Role).where(Role.name == name))

        if not result:
            raise ResourceNotFoundError(f"角色不存在：名称={name}")

        return result
    except SQLAlchemyError as e:
        logger.error(f"查询角色异常（数据库异常）：名称={name}，错误={str(e)}")
        raise


async def get_role_list(
    session: AsyncSession, page_params: PageParams
) -> Tuple[List[Role], int]:
    """
    获取所有角色列表（带分页）
    :param session: 异步数据库会话
    :param page_params: 分页参数（page_num/page_size）
    :return: 角色列表 + 总条数
    """
    try:
        count_stmt = select(func.count(Role.id))
        total = await session.scalar(count_stmt)

        offset = (page_params.page_num - 1) * page_params.page_size

        query_stmt = select(Role).offset(offset).limit(page_params.page_size)
        result = await session.scalars(query_stmt)
        roles: List[Role] = result.all()

        if len(roles) == 0:
            logger.info(
                f"角色列表为空（第{page_params.page_num}页，每页{page_params.page_size}条）"
            )
        return roles, total
    except SQLAlchemyError as e:
        logger.error(f"查询角色列表异常（数据库异常）：错误={str(e)}")
        raise


async def add_role(role_in: RoleCreate, session: AsyncSession) -> Role:
    """
    添加单个角色
    :param role_in: 角色信息 pydantic模型
    :param session: 异步数据库会话
    :return: 添加的角色
    """
    try:
        exist_role = await session.scalar(select(Role).where(Role.name == role_in.name))
        if exist_role:
            raise ResourceAlreadyExistsError(f"角色已存在：名称={role_in.name}")

        new_role = Role(
            name=role_in.name.strip(),
            description=role_in.description.strip(),
        )

        session.add(new_role)
        await session.commit()
        await session.refresh(new_role)

        logger.info(f"添加角色成功：ID={new_role.id}，名称={new_role.name}")
        return new_role
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"添加角色失败（数据库异常）：名称={role_in.name}，错误={str(e)}")
        raise


async def update_role(role_id: int, role_in: RoleUpdate, session: AsyncSession) -> Role:
    """
    更新单个角色
    :param role_id: 角色id
    :param role_in: 角色更新信息
    :param session: 异步数据库会话
    :return: 更新后的角色
    """
    try:
        role = await get_role_by_id(role_id, session)

        if role_in.name is not None and role_in.name.strip():
            exist_role = await session.scalar(
                select(Role).where(Role.name == role_in.name.strip())
            )
            if exist_role and exist_role.id != role_id:
                raise ResourceAlreadyExistsError(
                    f"角色名称已存在：{role_in.name.strip()}"
                )
            role.name = role_in.name.strip()

        if role_in.description is not None:
            role.description = role_in.description.strip()

        await session.commit()
        await session.refresh(role)

        logger.info(f"更新角色成功：ID={role_id}，名称={role.name}")
        return role
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"更新角色失败（数据库异常）：ID={role_id}，错误={str(e)}")
        raise


async def delete_role(role_id: int, session: AsyncSession) -> None:
    """
    删除单个角色
    :param role_id: 角色id
    :param session: 异步数据库会话
    :return: None
    """
    try:
        role = await get_role_by_id(role_id, session)

        if role.name == 'admin':
            logger.warning(f"尝试删除系统管理员角色：ID={role_id}，名称={role.name}")
            raise ValueError("系统管理员角色不可删除")

        await session.delete(role)
        await session.commit()

        logger.info(f"删除角色成功：ID={role_id}，名称={role.name}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"删除角色失败（数据库异常）：ID={role_id}, 错误={str(e)}")
        raise


async def batch_delete_roles(
    role_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量删除角色
    : param role_ids: 角色ID列表（长度1=单个，长度>1=批量）
    : param session: 异步数据库会话
    : return: 操作结果（成功/失败ID）
    """
    try:
        if not role_ids:
            raise ValueError("role_ids 不能为空列表")

        roles = await get_roles_by_ids(role_ids, session)
        existing_ids = {r.id for r in roles}

        admin_roles = [role for role in roles if role.name == 'admin']
        if admin_roles:
            admin_ids = [role.id for role in admin_roles]
            logger.warning(f"尝试批量删除系统管理员角色：IDs={admin_ids}")
            raise ValueError("系统管理员角色不可删除")

        for role in roles:
            await session.delete(role)
        await session.commit()

        success_ids = list(existing_ids)
        failed_ids = [rid for rid in role_ids if rid not in existing_ids]

        logger.info(f"批量删除角色完成：成功ID={success_ids}，失败ID={failed_ids}")
        return {
            "success": True,
            "message": "批量删除角色完成",
            "data": {
                "success_ids": success_ids,
                "failed_ids": failed_ids,
                "failed_reason": "失败ID对应角色不存在" if failed_ids else "",
            },
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量删除角色失败（数据库异常）：role_ids={role_ids}，错误={str(e)}"
        )
        raise


async def bind_permissions_to_role(
    role_id: int, permission_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    增量绑定权限到角色
    : param role_id: 角色id
    : param permission_ids: 权限id列表
    : param session: 异步数据库会话
    : return: 操作结果 + 绑定后的角色
    """
    try:
        role = await session.scalar(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        if not role:
            raise ResourceNotFoundError(f"角色ID {role_id} 不存在")

        existing_permission_ids = {p.id for p in role.permissions}
        need_bind_ids = list(set(permission_ids) - existing_permission_ids)

        if not need_bind_ids:
            logger.info(f"角色ID {role_id} 已绑定所有指定权限，无需新增")
            return {
                "success": True,
                "message": "无需新增权限（已绑定所有指定权限）",
                "data": {"role": role, "added_permission_ids": []},
            }

        permissions = await session.scalars(
            select(Permission).where(Permission.id.in_(need_bind_ids))
        )
        permission_list = permissions.all()

        found_ids = {p.id for p in permission_list}
        missing_ids = [pid for pid in need_bind_ids if pid not in found_ids]
        if missing_ids:
            raise ResourceNotFoundError(f"权限ID不存在：{missing_ids}")

        role.permissions.extend(permission_list)
        await session.commit()
        await session.refresh(role)

        logger.info(
            f"角色增量绑定权限成功：角色ID={role_id}，新增权限ID={need_bind_ids}"
        )
        return {
            "success": True,
            "message": "角色绑定权限成功",
            "data": {"role": role, "added_permission_ids": need_bind_ids},
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"角色绑定权限失败（数据库异常）：角色ID={role_id}，错误={str(e)}")
        raise


async def unbind_permissions_from_role(
    role_id: int, permission_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    解绑角色权限
    :param role_id: 角色id
    :param permission_ids: 权限id列表
    :param session: 异步数据库会话
    :return: 操作结果 + 解绑后的角色
    """
    try:
        role = await session.scalar(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        if not role:
            raise ResourceNotFoundError(f"角色ID {role_id} 不存在")

        existing_permissions = {p.id: p for p in role.permissions}
        need_unbind_permissions = [
            existing_permissions[pid]
            for pid in permission_ids
            if pid in existing_permissions
        ]

        if not need_unbind_permissions:
            logger.info(f"角色ID {role_id} 未绑定任何指定的权限，无需解绑")
            return {
                "success": True,
                "message": "无需解绑权限（未绑定任何指定权限）",
                "data": {"role": role, "unbind_permission_ids": []},
            }

        for permission in need_unbind_permissions:
            role.permissions.remove(permission)

        await session.commit()
        await session.refresh(role)

        unbind_ids = [p.id for p in need_unbind_permissions]
        logger.info(f"角色批量解绑权限成功：角色ID={role_id}，解绑权限ID={unbind_ids}")
        return {
            "success": True,
            "message": "角色解绑权限成功",
            "data": {"role": role, "unbind_permission_ids": unbind_ids},
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"角色解绑权限失败（数据库异常）：角色ID={role_id}，错误={str(e)}")
        raise


async def batch_bind_permissions_to_roles(
    role_ids: List[int], permission_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量给多个角色绑定指定权限
    : param role_ids: 角色ID列表（支持单个/多个）
    : param permission_ids: 权限ID列表（支持单个/多个）
    : param session: 异步数据库会话
    : return: 操作结果（每个角色的绑定状态）
    """
    try:
        if not role_ids:
            raise ValueError("role_ids 不能为空列表")
        if not permission_ids:
            raise ValueError("permission_ids 不能为空列表")

        roles = await session.scalars(
            select(Role)
            .where(Role.id.in_(role_ids))
            .options(selectinload(Role.permissions))
        )
        role_list = roles.all()
        existing_role_ids = {r.id for r in role_list}

        permissions = await session.scalars(
            select(Permission).where(Permission.id.in_(permission_ids))
        )
        permission_list = permissions.all()
        existing_permission_ids = {p.id for p in permission_list}

        missing_role_ids = [rid for rid in role_ids if rid not in existing_role_ids]
        missing_permission_ids = [
            pid for pid in permission_ids if pid not in existing_permission_ids
        ]

        role_bind_results = {}
        for role in role_list:
            role_existing_pids = {p.id for p in role.permissions}
            need_bind_pids = list(existing_permission_ids - role_existing_pids)

            if not need_bind_pids:
                role_bind_results[role.id] = {
                    "status": "success",
                    "message": "已绑定所有指定权限，无需新增",
                    "added_permission_ids": [],
                }
                continue

            need_bind_permissions = [
                p for p in permission_list if p.id in need_bind_pids
            ]
            role.permissions.extend(need_bind_permissions)

            role_bind_results[role.id] = {
                "status": "success",
                "message": "增量绑定权限成功",
                "added_permission_ids": need_bind_pids,
            }

        await session.commit()

        result = {
            "success": True,
            "message": "批量绑定角色权限完成",
            "data": {
                "total_role_count": len(role_ids),
                "success_role_count": len(existing_role_ids),
                "failed_role_count": len(missing_role_ids),
                "missing_role_ids": missing_role_ids,
                "missing_permission_ids": missing_permission_ids,
                "role_bind_details": role_bind_results,
            },
        }

        logger.info(
            f"批量绑定角色权限完成：成功角色数={len(existing_role_ids)}，失败角色数={len(missing_role_ids)}"
        )
        return result
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量绑定角色权限失败（数据库异常）：role_ids={role_ids}，permission_ids={permission_ids}，错误={str(e)}"
        )
        raise


async def batch_unbind_permissions_from_roles(
    role_ids: List[int], permission_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量给多个角色解绑指定权限
    : param role_ids: 角色ID列表（支持单个/多个）
    : param permission_ids: 权限ID列表（支持单个/多个）
    : param session: 异步数据库会话
    : return: 操作结果（每个角色的解绑状态）
    """
    try:
        if not role_ids:
            raise ValueError("role_ids 不能为空列表")
        if not permission_ids:
            raise ValueError("permission_ids 不能为空列表")

        roles = await session.scalars(
            select(Role)
            .where(Role.id.in_(role_ids))
            .options(selectinload(Role.permissions))
        )
        role_list = roles.all()
        existing_role_ids = {r.id for r in role_list}

        missing_role_ids = [rid for rid in role_ids if rid not in existing_role_ids]

        role_unbind_results = {}
        for role in role_list:
            role_permissions = {p.id: p for p in role.permissions}
            need_unbind_permissions = [
                role_permissions[pid]
                for pid in permission_ids
                if pid in role_permissions
            ]

            if not need_unbind_permissions:
                role_unbind_results[role.id] = {
                    "status": "success",
                    "message": "未绑定任何指定权限，无需解绑",
                    "unbind_permission_ids": [],
                }
                continue

            for permission in need_unbind_permissions:
                role.permissions.remove(permission)

            unbind_pids = [p.id for p in need_unbind_permissions]
            role_unbind_results[role.id] = {
                "status": "success",
                "message": "解绑权限成功",
                "unbind_permission_ids": unbind_pids,
            }

        await session.commit()

        result = {
            "success": True,
            "message": "批量解绑角色权限完成",
            "data": {
                "total_role_count": len(role_ids),
                "success_role_count": len(existing_role_ids),
                "failed_role_count": len(missing_role_ids),
                "missing_role_ids": missing_role_ids,
                "role_unbind_details": role_unbind_results,
            },
        }

        logger.info(
            f"批量解绑角色权限完成：成功角色数={len(existing_role_ids)}，失败角色数={len(missing_role_ids)}"
        )
        return result
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量解绑角色权限失败（数据库异常）：role_ids={role_ids}，permission_ids={permission_ids}，错误={str(e)}"
        )
        raise


async def get_role_permissions(role_id: int, session: AsyncSession) -> Dict[str, Any]:
    """
    查看指定角色已绑定的所有权限
    :param role_id: 角色ID
    :param session: 异步数据库会话
    :return: 角色信息 + 权限列表
    """
    try:
        role = await session.scalar(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        if not role:
            raise ResourceNotFoundError(f"角色不存在：ID={role_id}")

        permissions = [
            {
                "id": str(p.id),
                "scope": p.scope,
                "description": p.description,
            }
            for p in role.permissions
        ]

        return {
            "success": True,
            "message": "获取角色权限成功",
            "data": {
                "role": {
                    "id": str(role.id),
                    "name": role.name,
                    "description": role.description,
                },
                "permissions": permissions,
                "permission_count": len(permissions),
            },
        }
    except SQLAlchemyError as e:
        logger.error(f"获取角色权限失败（数据库异常）：角色ID={role_id}，错误={str(e)}")
        raise

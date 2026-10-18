from typing import Any, Dict, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from models.user import User
from models.role import Role
from models.permission import Permission

from schemas.permission import PermissionCreate, PermissionUpdate
from schemas import PageParams, PageResponse

from core.logger import logger
from core.exceptions import ResourceNotFoundError, ResourceAlreadyExistsError


async def get_permission_by_scope(scope: str, session: AsyncSession) -> Permission:
    """
    通过权限范围获取权限
    :param scope: 权限范围
    :param session: 异步数据库会话
    :return: 权限
    """
    try:
        permission = await session.scalar(
            select(Permission).where(Permission.scope == scope)
        )

        if not permission:
            raise ResourceNotFoundError(f"权限不存在：权限={scope}")

        return permission
    except SQLAlchemyError as e:
        logger.error(f"获取权限异常（数据库异常）：错误={str(e)}")
        raise


async def get_permission_by_id(permission_id: int, session: AsyncSession) -> Permission:
    """
    通过ID获取权限
    :param permission_id: 权限ID
    :param session: 异步数据库会话
    :return: 权限
    """
    try:
        permission = await session.scalar(
            select(Permission).where(Permission.id == permission_id)
        )
        if not permission:
            raise ResourceNotFoundError(f"权限不存在：ID={permission_id}")

        return permission
    except SQLAlchemyError as e:
        logger.error(f"获取权限异常（数据库异常）：ID={permission_id}，错误={str(e)}")
        raise


async def get_permissions_by_ids(
    permission_ids: List[int], session: AsyncSession
) -> List[Permission]:
    """
    批量查询权限
    :param permission_ids: 权限ID列表
    :param session: 异步数据库会话
    :return: 权限列表
    """
    try:
        if not permission_ids:
            return []

        result = await session.scalars(
            select(Permission).where(Permission.id.in_(permission_ids))
        )
        permissions = result.all()

        # 校验是否有不存在的ID
        existing_ids = {p.id for p in permissions}
        missing_ids = [pid for pid in permission_ids if pid not in existing_ids]
        if missing_ids:
            logger.warning(f"批量查询权限：部分ID不存在，missing_ids={missing_ids}")

        return permissions
    except SQLAlchemyError as e:
        logger.error(
            f"批量查询权限异常（数据库异常）：permission_ids={permission_ids}，错误={str(e)}"
        )
        raise


async def get_admin_role(session: AsyncSession) -> Role:
    """
    获取名称为admin的角色 用于自动绑定权限
    :param session: 异步数据库会话
    :return: admin角色
    """
    try:
        admin_role = await session.scalar(
            select(Role)
            .where(Role.name == "admin")
            .options(selectinload(Role.permissions))
        )
        if not admin_role:
            raise ResourceNotFoundError("admin角色不存在，无法自动绑定权限")
        return admin_role
    except SQLAlchemyError as e:
        logger.error(f"获取admin角色失败（数据库异常）：错误={str(e)}")
        raise


async def add_permission(
    permission_in: PermissionCreate, session: AsyncSession
) -> Permission | None:
    """
    添加权限  新增后自动绑定到admin角色
    :param permission_in: 权限信息
    :param session: 异步数据库会话
    :return: 添加的权限
    """
    try:
        permission = await session.scalar(
            select(Permission).where(Permission.scope == permission_in.scope)
        )

        if permission:
            raise ResourceAlreadyExistsError(f"权限已存在：scope={permission_in.scope}")

        new_permission = Permission(
            scope=permission_in.scope, description=permission_in.description
        )
        session.add(new_permission)
        await session.flush()  # 刷新权限ID，但是不提交

        admin_role = await get_admin_role(session)
        # 检查admin是否已绑定该权限，避免重复    虽然不可能，但是还是写上去了
        if new_permission not in admin_role.permissions:
            admin_role.permissions.append(new_permission)
            logger.info(
                f"自动绑定权限到admin角色：权限ID={new_permission.id}，scope={new_permission.scope}"
            )

        logger.info(
            f"添加权限成功：ID={new_permission.id}，scope={new_permission.scope}"
        )

        await session.commit()
        await session.refresh(new_permission)

        return new_permission
    except SQLAlchemyError as e:
        logger.error(f"添加权限异常（数据库异常）：错误={str(e)}")
        await session.rollback()
        raise


async def get_permission_list(
    session: AsyncSession,
    page_params: PageParams
) -> Tuple[List[Permission], int]:
    """
    获取权限列表（带分页）
    :param session: 异步数据库会话
    :param page_params: 分页参数（page_num/page_size）
    :return: 权限列表 + 总条数
    """
    try:
        # 查询总条数
        count_stmt = select(func.count(Permission.id))
        total = await session.scalar(count_stmt)
        
        # 计算偏移量，实现分页
        offset = (page_params.page_num - 1) * page_params.page_size
        
        # 查询当前页数据
        query_stmt = select(Permission).offset(offset).limit(page_params.page_size)
        result = await session.scalars(query_stmt)
        permissions = result.all()

        if len(permissions) == 0:
            logger.info(f"权限列表为空（第{page_params.page_num}页，每页{page_params.page_size}条）")

        return permissions, total
    except SQLAlchemyError as e:
        logger.error(f"获取权限列表异常（数据库异常）：错误={str(e)}")
        raise

async def update_permission(
    permission_id: int, permission_in: PermissionUpdate, session: AsyncSession
) -> Permission:
    """
    更新权限
    :param permission_id: 权限id
    :param permission_in: 权限更新信息，仅更新权限描述，不能修改权限范围
    :param session: 异步数据库会话
    :return: 更新的权限
    """
    try:
        permission = await session.scalar(
            select(Permission).where(Permission.id == permission_id)
        )
        if not permission:
            raise ResourceNotFoundError(f"权限ID {permission_id} 不存在")

        if permission_in.description is not None:
            permission.description = permission_in.description

        await session.commit()
        await session.refresh(permission)

        logger.info(f"更新权限成功：ID={permission_id}，scope={permission.scope}")
        return permission
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"更新权限失败（数据库异常）：ID={permission_id}，错误={str(e)}")
        raise


async def delete_permission(permission_id: int, session: AsyncSession) -> None:
    """
    删除权限
    : param permission_id: 权限id
    : param session: 异步数据库会话
    : return: 无返回值
    """
    try:
        permission = await session.scalar(
            select(Permission).where(Permission.id == permission_id)
        )
        if not permission:
            raise ResourceNotFoundError(f"权限ID {permission_id} 不存在")

        await session.delete(permission)
        await session.commit()
        logger.info(f"删除权限成功：ID={permission_id}，scope={permission.scope}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"删除权限失败（数据库异常）：ID={permission_id}，错误={str(e)}")
        raise


async def batch_delete_permissions(
    permission_ids: List[int], session: AsyncSession
) -> Dict[str, Any]:
    """
    批量删除权限
    : param permission_ids: 权限ID列表（长度1=单个，长度>1=批量）
    : param session: 异步数据库会话
    : return: 操作结果（成功/失败ID）
    """
    try:
        if not permission_ids:
            raise ValueError("permission_ids 不能为空列表")

        # 批量查询权限
        permissions = await get_permissions_by_ids(permission_ids, session)
        existing_ids = {p.id for p in permissions}

        # 执行删除
        for permission in permissions:
            await session.delete(permission)
        await session.commit()

        # 整理结果
        success_ids = list(existing_ids)
        failed_ids = [pid for pid in permission_ids if pid not in existing_ids]

        logger.info(f"批量删除权限完成：成功ID={success_ids}，失败ID={failed_ids}")
        return {
            "success": True,
            "message": "批量删除权限完成",
            "data": {
                "success_ids": success_ids,
                "failed_ids": failed_ids,
                "failed_reason": "失败ID对应权限不存在" if failed_ids else "",
            },
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(
            f"批量删除权限失败（数据库异常）：permission_ids={permission_ids}，错误={str(e)}"
        )
        raise

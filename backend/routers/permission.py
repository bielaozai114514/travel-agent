from typing import Annotated

from fastapi import APIRouter, Body, Security, Depends, HTTPException, status
from pydantic import PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import get_db
from dependencies.auth import get_current_user
from models.user import User
from models.role import Role
from models.permission import Permission
from schemas.permission import PermissionCreate, PermissionUpdate, PermissionBase
from schemas import PageParams, PageResponse
from curd import permission as permission_crud
from core.logger import logger

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", summary="获取权限列表（带分页）", response_model=PageResponse)
async def get_permission_list(
    page_params: Annotated[PageParams, Depends()],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    permissions, total = await permission_crud.get_permission_list(session, page_params)

    permission_list = [PermissionBase.model_validate(perm) for perm in permissions]

    return {
        "success": True,
        "message": "获取权限列表成功",
        "data": {
            "list": permission_list,          # 当前页数据列表
            "total": total,              # 总条数
            "page_num": page_params.page_num,  # 当前页码
            "page_size": page_params.page_size, # 每页条数
            "total_pages": (total + page_params.page_size - 1) // page_params.page_size  # 总页数
        }
    }


@router.get("/{permission_id}", summary="通过ID获取权限")
async def get_permission(
    permission_id: PositiveInt,  # 参数校验（正整数）
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    permission = await permission_crud.get_permission_by_id(permission_id, session)
    return {"success": True, "message": "获取权限成功", "data": PermissionBase.model_validate(permission)}


@router.get("/scope/{scope}", summary="通过scope获取权限")
async def get_permission_by_scope(
    scope: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    permission = await permission_crud.get_permission_by_scope(scope, session)
    return {"success": True, "message": "获取权限成功", "data": PermissionBase.model_validate(permission)}


@router.post("", summary="添加单个权限")
async def create_permission(
    permission_in: PermissionCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    permission = await permission_crud.add_permission(permission_in, session)
    return {"success": True, "message": "添加权限成功", "data": PermissionBase.model_validate(permission)}


@router.put("/{permission_id}", summary="更新单个权限")
async def update_permission(
    permission_id: PositiveInt,
    permission_in: PermissionUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    permission = await permission_crud.update_permission(
        permission_id, permission_in, session
    )
    return {"success": True, "message": "更新权限成功", "data": PermissionBase.model_validate(permission)}


@router.delete("/{permission_id}", summary="删除单个权限")
async def delete_permission(
    permission_id: PositiveInt,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    await permission_crud.delete_permission(permission_id, session)
    return {"success": True, "message": f"权限ID {permission_id} 删除成功"}


@router.delete("", summary="批量删除权限（支持单个/多个）")
async def batch_delete_permissions(
    permission_ids: Annotated[
        list[PositiveInt],
        Body(..., description="权限ID列表（长度1=单个，长度>1=批量）"),
    ],
    current_user: Annotated[
        User, Security(get_current_user, scopes=["users:write"])
    ],
    session: AsyncSession = Depends(get_db),
):
    result = await permission_crud.batch_delete_permissions(permission_ids, session)
    return result

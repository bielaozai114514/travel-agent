from typing import Annotated, List
from pydantic import PositiveInt

from fastapi import APIRouter, Security, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.role import RoleCreate, RoleUpdate, RoleBase
from schemas import PageParams, PageResponse
from curd import role as role_crud
from core.exceptions import ResourceAlreadyExistsError, ResourceNotFoundError

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", summary="获取角色列表（带分页）", response_model=PageResponse)
async def list_roles(
    page_params: Annotated[PageParams, Depends()],  # 分页参数
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    roles, total = await role_crud.get_role_list(session, page_params)
    # 转换为 Pydantic 模型列表
    role_list = [RoleBase.model_validate(role) for role in roles]
    
    return {
        "success": True,
        "message": "获取角色列表成功",
        "data": {
            "list": role_list,
            "total": total,
            "page_num": page_params.page_num,
            "page_size": page_params.page_size,
            "total_pages": (total + page_params.page_size - 1) // page_params.page_size
        }
    }

@router.get("/{role_id}", summary="通过ID获取角色")
async def get_role(
    role_id: PositiveInt,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    role = await role_crud.get_role_by_id(role_id, session)
    return {"success": True, "message": "获取角色成功", "data": RoleBase.model_validate(role)}


@router.get("/name/{name}", summary="通过名称获取角色")
async def get_role_by_name(
    name: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    role = await role_crud.get_role_by_name(name, session)
    return {"success": True, "message": "获取角色成功", "data": RoleBase.model_validate(role)}


@router.post("", summary="添加单个角色")
async def create_role(
    role_in: RoleCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    role = await role_crud.add_role(role_in, session)
    return {"success": True, "message": "添加角色成功", "data": RoleBase.model_validate(role)}


@router.put("/{role_id}", summary="更新单个角色")
async def update_role(
    role_id: PositiveInt,
    role_in: RoleUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    role = await role_crud.update_role(role_id, role_in, session)
    return {"success": True, "message": "更新角色成功", "data": RoleBase.model_validate(role)}


@router.delete("/{role_id}", summary="删除单个角色")
async def delete_role(
    role_id: PositiveInt,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    await role_crud.delete_role(role_id, session)
    return {"success": True, "message": f"角色ID {role_id} 删除成功"}


@router.delete("", summary="批量删除角色（支持单个/多个）")
async def batch_delete_roles(
    role_ids: Annotated[
        List[PositiveInt],
        Body(..., description="角色ID列表（长度1=单个，长度>1=批量）"),
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.batch_delete_roles(role_ids, session)
    return result


@router.post("/{role_id}/permissions", summary="角色增量绑定权限")
async def bind_permissions_to_role(
    role_id: PositiveInt,
    permission_ids: Annotated[List[PositiveInt], Body(..., description="权限ID列表")],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.bind_permissions_to_role(role_id, permission_ids, session)
    return result


@router.delete("/{role_id}/permissions", summary="角色解绑权限")
async def unbind_permissions_from_role(
    role_id: PositiveInt,
    permission_ids: Annotated[List[PositiveInt], Body(..., description="权限ID列表")],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.unbind_permissions_from_role(
        role_id, permission_ids, session
    )
    return result


@router.post("/permissions/assign", summary="批量给多个角色绑定指定权限")
async def batch_bind_permissions_to_roles(
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    permission_ids: Annotated[
        List[PositiveInt], Body(..., description="权限ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.batch_bind_permissions_to_roles(
        role_ids, permission_ids, session
    )
    return result


@router.post("/permissions/revoke", summary="批量给多个角色解绑指定权限")
async def batch_unbind_permissions_from_roles(
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    permission_ids: Annotated[
        List[PositiveInt], Body(..., description="权限ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.batch_unbind_permissions_from_roles(
        role_ids, permission_ids, session
    )
    return result


@router.get("/{role_id}/permissions", summary="查看角色已绑定的所有权限")
async def get_role_permissions(
    role_id: PositiveInt,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    result = await role_crud.get_role_permissions(role_id, session)
    return result

from datetime import timedelta
from typing import Annotated, List

from fastapi import APIRouter, Body, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import PositiveInt

from models.user import User
from dependencies.db_session import get_db
from dependencies.auth import get_current_user
from schemas.user import UserRegister, UserResponse, UserUpdate, Token, BaseUser
from schemas import PageParams, PageResponse
from core.logger import logger
from core.security import verify_password, create_access_token
from core.exceptions import ResourceNotFoundError, ResourceAlreadyExistsError
from curd import user as user_crud

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/login", summary="用户登录")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> Token:

    email = form_data.username
    password = form_data.password

    user: User = await user_crud.get_user_by_email(email, session)

    if not verify_password(password, user.hashed_password):
        logger.warning(f"登录失败：用户邮箱 {email} 不存在")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # 获取用户所有 scopes
    scopes: list[str] = []
    for role in user.roles:
        for perm in role.permissions:
            scopes.append(perm.scope)

    # logger.info(f"user 的 scopes：{scopes}")

    # 创建 Token
    access_token = create_access_token(
        data={"sub": user.username, "scopes": scopes}
    )

    logger.info(f"用户 {user.username} 登录成功")
    return Token(access_token=access_token, token_type="bearer")


@router.post("/register", response_model=UserResponse, summary="用户注册")
async def register(user_in: UserRegister, session: AsyncSession = Depends(get_db)):
    new_user = await user_crud.create_user(user_in, session)
    logger.info(f"用户 {user_in.username} 注册成功")
    return UserResponse(
        id=new_user.id, username=new_user.username, email=new_user.email
    )


@router.get("", summary="获取用户列表（带分页）", response_model=PageResponse)
async def get_user_list(
    page_params: Annotated[PageParams, Depends()], 
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
    load_roles: bool = False
):
    users, total = await user_crud.get_user_list(session, load_roles=load_roles, page_params=page_params)
    
    # 转换为 UserResponse 列表
    user_list = [
        UserResponse(id=user.id, username=user.username, email=user.email)
        for user in users
    ]

    return {    
        "success": True,
        "message": "获取用户列表成功",
        "data": {
            "list": user_list,
            "total": total,
            "page_num": page_params.page_num,
            "page_size": page_params.page_size,
            "total_pages": (total + page_params.page_size - 1) // page_params.page_size
        }
    }

@router.get("/current", summary="获取当前登录用户信息")
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
):
    """获取当前登录用户的详细信息，包括角色和权限"""
    # 加载用户角色和权限
    user_with_roles = await user_crud.get_user_by_id_with_roles(current_user.id, session)
    
    # 构建角色信息 - ID转为字符串避免JavaScript精度丢失
    roles = []
    for role in user_with_roles.roles:
        role_info = {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": [
                {
                    "id": str(perm.id),
                    "scope": perm.scope,
                    "description": perm.description
                }
                for perm in role.permissions
            ]
        }
        roles.append(role_info)
    
    return {
        "id": str(user_with_roles.id),
        "username": user_with_roles.username,
        "email": user_with_roles.email,
        "roles": roles
    }


@router.get("/{user_id}", response_model=UserResponse, summary="通过ID获取用户")
async def get_user(
    user_id: PositiveInt,
    user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):

    user = await user_crud.get_user_by_id(user_id, session)
    return UserResponse(id=user.id, username=user.username, email=user.email)


@router.put("/{user_id}", response_model=UserResponse, summary="更新单个用户")
async def update_user(
    user_id: PositiveInt,
    user_in: UserUpdate,
    user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):

    user = await user_crud.update_user(user_id, user_in, session)
    return UserResponse(id=user.id, username=user.username, email=user.email)


@router.delete("/{user_id}", summary="删除单个用户")
async def delete_user(
    user_id: int,
    user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    await user_crud.delete_user(user_id, session)
    return {"success": True, "message": f"用户ID {user_id} 删除成功"}


@router.delete("", summary="批量删除用户（支持单个/多个）")
async def batch_delete_users(
    user_ids: Annotated[
        List[PositiveInt],
        Body(..., description="用户ID列表（长度1=单个，长度>1=批量）"),
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.batch_delete_users(user_ids, session)
    return result


@router.get("/{user_id}/roles", summary="查看用户已绑定的所有角色")
async def get_user_roles(
    user_id: PositiveInt,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.get_user_roles(user_id, session)
    return result


@router.post("/{user_id}/roles", summary="用户增量绑定角色（支持单个/多个）")
async def bind_roles_to_user(
    user_id: PositiveInt,
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.bind_roles_to_user(user_id, role_ids, session)
    return result


@router.delete("/{user_id}/roles", summary="用户解绑角色（支持单个/多个）")
async def unbind_roles_from_user(
    user_id: PositiveInt,
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.unbind_roles_from_user(user_id, role_ids, session)
    return result


@router.post("/roles/assign", summary="批量给多个用户分配角色")
async def batch_assign_roles_to_users(
    user_ids: Annotated[
        List[PositiveInt], Body(..., description="用户ID列表（单个/多个）")
    ],
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.batch_bind_roles_to_users(user_ids, role_ids, session)
    return result


@router.post("/roles/revoke", summary="批量给多个用户撤销角色")
async def batch_revoke_roles_from_users(
    user_ids: Annotated[
        List[PositiveInt], Body(..., description="用户ID列表（单个/多个）")
    ],
    role_ids: Annotated[
        List[PositiveInt], Body(..., description="角色ID列表（单个/多个）")
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["users:write"])],
    session: AsyncSession = Depends(get_db),
):
    result = await user_crud.batch_unbind_roles_from_users(user_ids, role_ids, session)
    return result

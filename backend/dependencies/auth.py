from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from jwt.exceptions import InvalidTokenError

from models.user import User
from schemas.user import TokenData
from dependencies.db_session import get_db
from settings import settings
from core.logger import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


async def get_current_user(
    security_scopes: SecurityScopes,
    session: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    验证 JWT Token, 检查Token有效性和scope范围, 返回当前登录用户：
    """

    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    # 认证失败的异常
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的令牌或令牌已过期",
        headers={"WWW-Authenticate": authenticate_value},
    )

    # 权限不足异常
    insufficient_scope_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="权限不足",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        # 解码 Token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 从 Token 中获取数据（subject 字段 和 scopes 字段）
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_scopes: list[str] = payload.get("scopes", [])

    except (InvalidTokenError, ValidationError):
        raise credentials_exception

    token_data = TokenData(scopes=token_scopes, username=username)
    # 从数据库查询用户，预加载roles关系
    result = await session.execute(
        select(User)
        .where(User.username == token_data.username)
        .options(selectinload(User.roles))  # 立即加载关联角色
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    # 校验权限 如果接口要求了 scope，但 Token 中没有，则拒绝
    if security_scopes.scopes:  # 只有接口要求了 scope 才校验
        for scope in security_scopes.scopes:
            if scope not in token_data.scopes:
                raise insufficient_scope_exception

    # logger.info(
    #     f"接口要求的scopes: {security_scopes.scopes}, Token中的scopes: {token_scopes}"
    # )
    return user

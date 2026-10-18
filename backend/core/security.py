from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from pwdlib import PasswordHash
import jwt

from settings import settings

password_hash = PasswordHash.recommended()


def verify_password(plain_password, hashed_password):
    """验证密码"""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """加密密码"""
    return password_hash.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    创建访问令牌
    data: 令牌数据 包括 username 和 scopes
    expires_delta: 令牌有效期
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

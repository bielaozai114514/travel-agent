from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict, field_serializer
from typing import Annotated, Optional


class BaseUser(BaseModel):
    id: Annotated[int, Field(..., description="用户id")]
    username: Annotated[
        str, Field(..., min_length=3, max_length=20, description="用户名")
    ]
    email: Annotated[EmailStr, Field(..., description="邮箱")]

    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer('id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class UserLogin(BaseModel):
    email: Annotated[EmailStr, Field(..., description="邮箱")]
    password: Annotated[str, Field(..., min_length=6, description="密码")]


class UserRegister(BaseModel):
    username: Annotated[
        str,
        Field(
            min_length=3,
            max_length=20,
            pattern=r"^[a-zA-Z0-9_]+$",
            description="用户名（3-20位，字母数字下划线）",
        ),
    ]
    password: Annotated[str, Field(..., min_length=6, description="密码（至少6位）")]
    email: Annotated[EmailStr, Field(..., description="邮箱")]

    @field_validator("password")
    def password_strength(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        return v


class UserUpdate(BaseModel):
    username: Annotated[
        Optional[str],
        Field(
            None,
            min_length=3,
            max_length=20,
            pattern=r"^[a-zA-Z0-9_]+$",
            description="用户名（3-20位，字母数字下划线）",
        ),
    ] = None
    password: Annotated[
        Optional[str], Field(None, min_length=6, description="密码（至少6位）")
    ] = None
    email: Annotated[Optional[EmailStr], Field(None, description="邮箱")] = None

    @field_validator("password")
    def password_strength(cls, v):
        if v is None:
            return v
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        return v


class UserResponse(BaseUser):
    pass


# JWT Token响应模型
class Token(BaseModel):
    access_token: Annotated[str,Field(
        ...,
        description="JWT访问令牌",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )]
    token_type:Annotated[str, Field(
        "bearer", description="令牌类型（固定为bearer）", examples=["bearer"]
    )]


# Token解码后的数据模型 存储用户标识
class TokenData(BaseModel):
    username: Annotated[Optional[str], Field(
        None, description="令牌中的用户名", examples=["testuser1"]
    )]
    scopes: Annotated[list[str], Field(
        [], description="令牌中的权限范围", examples=["users:read"]
    )]

from typing import Annotated, Optional

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class RoleBase(BaseModel):
    id: Annotated[int, Field(..., description="角色id")]
    name: Annotated[str, Field(..., description="角色名称")]
    description: Annotated[str, Field(..., description="角色描述")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class RoleCreate(BaseModel):
    name: Annotated[str, Field(..., description="角色名称", examples=["user"])]
    description: Annotated[str, Field(..., description="角色描述", examples=["普通用户"])]


class RoleUpdate(BaseModel):
    name: Annotated[
        Optional[str], Field(None, description="角色名称", examples=["user"])
    ] = None
    description: Annotated[
        Optional[str], Field(None, description="角色描述", examples=["普通用户"])
    ] = None

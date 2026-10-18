from typing import Annotated, Optional

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class PermissionBase(BaseModel):
    id: Annotated[int, Field(..., description="权限id")]
    scope: Annotated[str, Field(..., description="权限范围")]
    description: Annotated[str, Field(..., description="权限描述")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class PermissionCreate(BaseModel):
    scope: Annotated[str, Field(..., description="权限范围")]
    description: Annotated[str, Field(..., description="权限描述")]


class PermissionUpdate(BaseModel):
    description: Annotated[Optional[str], Field(None, description="权限描述")] = None

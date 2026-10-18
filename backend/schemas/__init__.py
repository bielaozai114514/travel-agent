from typing import Generic, TypeVar
from pydantic import BaseModel, Field, PositiveInt

# 通用分页参数模型
class PageParams(BaseModel):
    page_num: PositiveInt = Field(1, description="页码，默认1")
    page_size: PositiveInt = Field(10, description="每页条数，默认10")

# 通用分页响应模型
T = TypeVar('T')
class PageResponse(BaseModel, Generic[T]):
    success: bool = Field(True, description="请求是否成功")
    message: str = Field("", description="提示信息")
    data: dict = Field(..., description="数据体，包含列表和分页信息")
    
    class Config:
        from_attributes = True
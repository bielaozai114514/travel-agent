from pydantic import BaseModel, Field
from fastapi import status
from typing import List, Optional, Any, Annotated


class ErrorResponse(BaseModel):
    """全局异常响应模型"""
    status_code: Annotated[int, Field(..., description="HTTP状态码")]
    detail: Annotated[str, Field(..., description="错误详情")]

    class Config:
        json_schema_extra = {
            "example": {
                "status_code": 500,
                "detail": "数据库服务暂时不可用",
            }
        }


class ValidationErrorDetail(BaseModel):
    """字段验证错误详情"""
    field: Annotated[str, Field(..., description="错误字段名称")]
    message: Annotated[str, Field(..., description="错误信息")]
    value: Annotated[Optional[Any], Field(None, description="输入的值")]


class ValidationErrorResponse(BaseModel):
    """参数验证错误响应模型"""
    status_code: Annotated[int, Field(default=422, description="HTTP状态码")]
    message: Annotated[str, Field(default="请求参数验证失败", description="错误概要")]
    errors: Annotated[List[ValidationErrorDetail], Field(default=[], description="字段验证错误列表")]

    class Config:
        json_schema_extra = {
            "example": {
                "status_code": 422,
                "message": "请求参数验证失败",
                "errors": [
                    {
                        "field": "password",
                        "message": "密码必须包含数字",
                        "value": "abcdefgh"
                    },
                    {
                        "field": "username",
                        "message": "用户名长度必须在3到20个字符之间",
                        "value": "ab"
                    }
                ]
            }
        }

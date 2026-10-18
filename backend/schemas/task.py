"""后台任务相关Schema"""

from typing import Optional, List, Dict, Any, Annotated
from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    """任务基础模型"""
    task_type: Annotated[str, Field(..., description="任务类型")]
    trip_id: Annotated[Optional[int], Field(default=None, description="关联行程ID")]
    conversation_id: Annotated[Optional[int], Field(default=None, description="关联会话ID")]


class TaskCreate(TaskBase):
    """创建任务请求"""
    input_data: Annotated[Optional[Dict[str, Any]], Field(default=None, description="输入数据")]
    total_steps: Annotated[int, Field(default=5, description="总步骤数")]


class TaskResponse(BaseModel):
    """任务响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[Optional[Dict[str, Any]], Field(default=None, description="任务数据")]


class TaskListResponse(BaseModel):
    """任务列表响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(default="", description="消息")]
    data: Annotated[Dict[str, Any], Field(..., description="列表数据")]


class TaskProgressUpdate(BaseModel):
    """任务进度更新"""
    current_step: Annotated[Optional[str], Field(default=None, description="当前步骤")]
    step_progress: Annotated[int, Field(default=0, description="进度百分比")]
    status: Annotated[Optional[str], Field(default=None, description="状态")]

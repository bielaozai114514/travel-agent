"""
对话会话相关的Pydantic模型
"""
from datetime import datetime
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, field_serializer


class MessageBase(BaseModel):
    """消息基础模型"""
    role: Annotated[str, Field(..., description="消息角色(user/assistant/system)")]
    content: Annotated[str, Field(..., description="消息内容")]


class MessageCreate(MessageBase):
    """创建消息请求模型"""
    pass


class MessageResponse(MessageBase):
    """消息响应模型"""
    id: Annotated[int, Field(..., description="消息ID")]
    conversation_id: Annotated[int, Field(..., description="会话ID")]
    create_time: Annotated[datetime, Field(..., description="创建时间")]
    tokens: Annotated[Optional[int], Field(default=None, description="token数")]
    model: Annotated[Optional[str], Field(default=None, description="使用的模型")]
    thinking: Annotated[Optional[List[dict]], Field(default=None, description="思考过程")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'conversation_id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class ConversationBase(BaseModel):
    """会话基础模型"""
    title: Annotated[str, Field(default="新对话", description="会话标题")]


class ConversationCreate(ConversationBase):
    """创建会话请求模型"""
    pass


class ConversationUpdate(BaseModel):
    """更新会话请求模型"""
    title: Annotated[str, Field(..., description="新的会话标题")]


class ConversationResponse(ConversationBase):
    """会话响应模型"""
    id: Annotated[int, Field(..., description="会话ID")]
    user_id: Annotated[int, Field(..., description="用户ID")]
    current_trip_id: Annotated[Optional[int], Field(default=None, description="关联的行程ID")]
    create_time: Annotated[datetime, Field(..., description="创建时间")]
    update_time: Annotated[datetime, Field(..., description="更新时间")]
    message_count: Annotated[Optional[int], Field(default=0, description="消息数量")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'user_id', 'current_trip_id')
    def serialize_id(self, value: int) -> str:
        return str(value) if value else None


class ConversationDetailResponse(ConversationResponse):
    """会话详情响应模型（包含消息列表）"""
    messages: Annotated[List[MessageResponse], Field(default=[], description="消息列表")]


class ConversationListResponse(BaseModel):
    """会话列表响应模型"""
    list: Annotated[List[ConversationResponse], Field(..., description="会话列表")]
    total: Annotated[int, Field(..., description="总数")]
    page: Annotated[int, Field(..., description="当前页")]
    page_size: Annotated[int, Field(..., description="每页数量")]


class ChatMessageRequest(BaseModel):
    """聊天消息请求模型"""
    conversation_id: Annotated[Optional[int], Field(None, description="会话ID，为空则创建新会话")]
    content: Annotated[str, Field(..., description="用户消息内容")]
    stream: Annotated[bool, Field(default=True, description="是否流式返回")]


class ChatMessageResponse(BaseModel):
    """聊天消息响应模型（非流式）"""
    conversation_id: Annotated[int, Field(..., description="会话ID")]
    message: Annotated[MessageResponse, Field(..., description="消息内容")]

    @field_serializer('conversation_id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class StreamChatRequest(BaseModel):
    """流式聊天请求模型"""
    conversation_id: Annotated[Optional[int], Field(None, description="会话ID")]
    messages: Annotated[List[MessageBase], Field(..., description="对话历史消息")]
    stream: Annotated[bool, Field(default=True, description="是否流式返回")]

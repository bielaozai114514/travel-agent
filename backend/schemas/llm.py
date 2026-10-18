from pydantic import BaseModel, Field
from typing import Annotated

class Message(BaseModel):
    role: Annotated[str, Field(..., description="角色")]
    content: Annotated[str, Field(..., description="内容")]

class LLMRequest(BaseModel):
    messages: Annotated[list[Message], Field(..., description="对话历史（含当前用户消息）")]
    stream: Annotated[bool, Field(default=False, description="是否流式返回" )]

class LLMResponse(BaseModel):
    content: Annotated[str, Field(..., description="回答")]
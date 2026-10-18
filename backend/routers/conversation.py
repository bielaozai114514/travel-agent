"""
对话会话管理路由
"""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import get_db
from dependencies.auth import get_current_user
from models.user import User
from models.conversation import Conversation, Message
from schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    MessageResponse,
    ChatMessageRequest,
)
from curd.conversation import (
    create_conversation,
    get_conversation_by_id,
    get_conversations_by_user,
    update_conversation,
    delete_conversation,
    create_message,
    get_messages_by_conversation,
    update_conversation_title_by_first_message,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, summary="创建新会话")
async def create_new_conversation(
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
    data: Optional[ConversationCreate] = None,
):
    """创建新的对话会话"""
    title = data.title if data else "新对话"
    conversation = await create_conversation(db, current_user.id, title)
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        create_time=conversation.create_time,
        update_time=conversation.update_time,
        message_count=0,
    )


@router.get("", response_model=ConversationListResponse, summary="获取会话列表")
async def list_conversations(
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
):
    """获取当前用户的会话列表"""
    conversations, total = await get_conversations_by_user(
        db, current_user.id, page, page_size
    )
    
    result = []
    for conv in conversations:
        result.append(ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            current_trip_id=conv.current_trip_id,
            create_time=conv.create_time,
            update_time=conv.update_time,
            message_count=len(conv.messages),
        ))
    
    return ConversationListResponse(
        list=result,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{conversation_id}", summary="获取会话详情")
async def get_conversation_detail(
    conversation_id: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情及消息列表"""
    conversation = await get_conversation_by_id(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )

    messages = await get_messages_by_conversation(db, conversation_id, current_user.id)

    formatted_messages = []
    for m in messages:
        msg_data = {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "role": m.role,
            "content": m.content,
            "create_time": m.create_time,
            "tokens": m.tokens,
            "model": m.model,
            "thinking": m.thinking_process
        }
        formatted_messages.append(MessageResponse(**msg_data))

    conv_detail = ConversationDetailResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        current_trip_id=conversation.current_trip_id,
        create_time=conversation.create_time,
        update_time=conversation.update_time,
        message_count=len(messages),
        messages=formatted_messages,
    )

    return {
        "success": True,
        "data": conv_detail
    }


@router.put("/{conversation_id}", response_model=ConversationResponse, summary="更新会话标题")
async def update_conversation_title(
    conversation_id: str,
    data: ConversationUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
):
    """更新会话标题"""
    conversation = await update_conversation(
        db, conversation_id, current_user.id, data.title
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )
    
    messages = await get_messages_by_conversation(db, conversation_id, current_user.id)
    
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        current_trip_id=conversation.current_trip_id,
        create_time=conversation.create_time,
        update_time=conversation.update_time,
        message_count=len(messages),
    )


@router.delete("/{conversation_id}", summary="删除会话")
async def delete_conversation_endpoint(
    conversation_id: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
):
    """删除会话（软删除）"""
    success = await delete_conversation(db, conversation_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )
    return {"message": "删除成功"}


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse], summary="获取会话消息")
async def get_conversation_messages(
    conversation_id: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
):
    """获取会话的所有消息"""
    # 验证会话存在且属于当前用户
    conversation = await get_conversation_by_id(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )
    
    messages = await get_messages_by_conversation(db, conversation_id, current_user.id)
    
    formatted_messages = []
    for m in messages:
        msg_data = {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "role": m.role,
            "content": m.content,
            "create_time": m.create_time,
            "tokens": m.tokens,
            "model": m.model,
            "thinking": m.thinking_process
        }
        formatted_messages.append(MessageResponse(**msg_data))
    
    return formatted_messages

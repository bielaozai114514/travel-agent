from typing import List, Optional, Dict, Any, Union
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.conversation import Conversation, Message
from models import AsyncSessionLocal
from schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate
from core.logger import logger


async def create_conversation(
    db: AsyncSession,
    user_id_or_data: Union[int, Dict[str, Any]],
    title: str = "新对话"
) -> Conversation:
    """创建新会话（支持关联行程）

    兼容两种调用方式：
    1. create_conversation(db, user_id, title)  - 旧方式
    2. create_conversation(db, {"user_id": ..., "title": ..., ...})  - 新方式
    """
    if isinstance(user_id_or_data, dict):
        # 新方式：传入字典
        conversation_data = user_id_or_data
        logger.info(f"创建新会话：user_id={conversation_data.get('user_id')}, title={conversation_data.get('title')}")
        conversation = Conversation(**conversation_data)
    else:
        # 旧方式：传入 user_id 和 title
        user_id = user_id_or_data
        logger.info(f"创建新会话：user_id={user_id}, title={title}")
        conversation = Conversation(user_id=user_id, title=title)

    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    logger.info(f"会话创建成功：conversation_id={conversation.id}")
    return conversation


async def get_conversation_by_id(
    db: AsyncSession,
    conversation_id: int | str,
    user_id: Optional[int] = None
) -> Optional[Conversation]:
    """根据ID获取会话

    Args:
        conversation_id: 会话ID（支持str或int）
        user_id: 用户ID，如果提供则验证会话属于该用户
    """
    # 转换为int
    conv_id = int(conversation_id)
    logger.debug(f"查询会话：conversation_id={conv_id}, user_id={user_id}")
    query = select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.is_deleted == 0
    )
    if user_id:
        query = query.where(Conversation.user_id == user_id)
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if conversation:
        logger.debug(f"找到会话：id={conversation.id}, title={conversation.title}")
    else:
        logger.warning(f"会话不存在或无权访问：conversation_id={conversation_id}")
    
    return conversation


async def get_conversations_by_user(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20
) -> tuple[List[Conversation], int]:
    """获取用户的会话列表
    
    Returns:
        (会话列表, 总数)
    """
    logger.info(f"获取用户会话列表：user_id={user_id}, page={page}, page_size={page_size}")
    
    # 获取总数
    count_query = select(func.count(Conversation.id)).where(
        Conversation.user_id == user_id,
        Conversation.is_deleted == 0
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 获取列表（预加载messages关系以避免懒加载）
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.user_id == user_id,
            Conversation.is_deleted == 0
        )
        .order_by(desc(Conversation.update_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    logger.info(f"查询到 {len(conversations)} 个会话，总数={total}")
    return list(conversations), total




async def delete_conversation(
    db: AsyncSession,
    conversation_id: int | str,
    user_id: int
) -> bool:
    """软删除会话"""
    conv_id = int(conversation_id)
    logger.info(f"软删除会话：conversation_id={conv_id}, user_id={user_id}")
    conversation = await get_conversation_by_id(db, conv_id, user_id)
    if not conversation:
        logger.warning(f"会话不存在，无法删除：conversation_id={conversation_id}")
        return False
    
    conversation.is_deleted = 1
    await db.commit()
    logger.info(f"会话删除成功：conversation_id={conversation_id}")
    return True


async def create_message(
    db: AsyncSession,
    conversation_id: int | str,
    role: str,
    content: str,
    tokens: Optional[int] = None,
    model: Optional[str] = None,
    thinking_process: Optional[List[dict]] = None
) -> Message:
    """创建消息"""
    conv_id = int(conversation_id)
    logger.info(f"创建消息：conversation_id={conv_id}, role={role}, tokens={tokens}")
    message = Message(
        conversation_id=conv_id,
        role=role,
        content=content,
        tokens=tokens,
        model=model,
        thinking_process=thinking_process
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    logger.debug(f"消息创建成功：message_id={message.id}")
    return message


async def get_messages_by_conversation(
    db: AsyncSession,
    conversation_id: int | str,
    user_id: int
) -> List[Message]:
    """获取会话的所有消息"""
    conv_id = int(conversation_id)
    logger.debug(f"获取会话消息：conversation_id={conv_id}, user_id={user_id}")
    # 先验证会话属于该用户
    conversation = await get_conversation_by_id(db, conv_id, user_id)
    if not conversation:
        logger.warning(f"会话不存在或无权访问，无法获取消息：conversation_id={conversation_id}")
        return []
    
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.create_time)
    )
    result = await db.execute(query)
    messages = list(result.scalars().all())
    
    logger.debug(f"查询到 {len(messages)} 条消息")
    return messages


async def update_conversation_title_by_first_message(
    db: AsyncSession,
    conversation_id: int | str
) -> None:
    """根据第一条用户消息自动更新会话标题"""
    conv_id = int(conversation_id)
    logger.debug(f"自动更新会话标题：conversation_id={conv_id}")
    query = (
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.role == "user"
        )
        .order_by(Message.create_time)
        .limit(1)
    )
    result = await db.execute(query)
    first_message = result.scalar_one_or_none()
    
    if first_message:
        # 取前20个字符作为标题
        title = first_message.content[:20]
        if len(first_message.content) > 20:
            title += "..."
        
        conversation = await get_conversation_by_id(db, conv_id)
        if conversation and conversation.title == "新对话":
            conversation.title = title
            await db.commit()
            logger.info(f"会话标题已自动更新：conversation_id={conv_id}, title={title}")

async def update_conversation(
    db: AsyncSession,
    conversation_id: int | str,
    user_id: int,
    title: str
) -> Optional[Conversation]:
    """更新会话标题"""
    conv_id = int(conversation_id)
    logger.info(f"更新会话标题：conversation_id={conv_id}, user_id={user_id}, new_title={title}")
    conversation = await get_conversation_by_id(db, conv_id, user_id)
    if not conversation:
        logger.warning(f"会话不存在，无法更新：conversation_id={conversation_id}")
        return None

    conversation.title = title
    await db.commit()
    await db.refresh(conversation)
    logger.info(f"会话标题更新成功：conversation_id={conversation.id}")
    return conversation


async def update_conversation_generic(
    db: AsyncSession,
    conversation_id: int | str,
    user_id: int,
    update_data: Dict[str, Any]
) -> Optional[Conversation]:
    """通用更新会话方法（用于更新current_trip_id等字段）"""
    conv_id = int(conversation_id)
    logger.info(f"更新会话：conversation_id={conv_id}, user_id={user_id}, fields={list(update_data.keys())}")

    conversation = await get_conversation_by_id(db, conv_id, user_id)
    if not conversation:
        logger.warning(f"会话不存在，无法更新：conversation_id={conversation_id}")
        return None

    # 更新字段
    for key, value in update_data.items():
        if hasattr(conversation, key):
            setattr(conversation, key, value)

    await db.commit()
    await db.refresh(conversation)
    logger.info(f"会话更新成功：conversation_id={conversation.id}")
    return conversation


async def get_conversations_by_trip_id(
    db: AsyncSession,
    trip_id: int,
    user_id: int
) -> List[Conversation]:
    """获取关联到指定行程的会话列表"""
    logger.info(f"查询行程关联的会话：trip_id={trip_id}, user_id={user_id}")

    query = (
        select(Conversation)
        .where(
            Conversation.current_trip_id == trip_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted == 0
        )
        .order_by(desc(Conversation.update_time))
    )
    result = await db.execute(query)
    records = list(result.scalars().all())

    logger.info(f"查询到 {len(records)} 个关联会话")
    return records


async def save_assistant_message_with_new_session(
    conversation_id: int,
    content: str,
    thinking_process: Optional[List[dict]] = None,
    should_update_title: bool = False
) -> None:
    """使用新的数据库会话保存助手消息（用于流式响应后）

    这个函数会创建自己的数据库会话，避免使用依赖注入中已关闭的会话
    """
    conv_id = int(conversation_id)
    logger.info(f"使用新会话保存助手消息：conversation_id={conv_id}")

    async with AsyncSessionLocal() as db_session:
        # 创建消息
        message = Message(
            conversation_id=conv_id,
            role="assistant",
            content=content,
            thinking_process=thinking_process
        )
        db_session.add(message)

        # 更新标题（如果需要）
        if should_update_title:
            # 查找第一条用户消息
            query = (
                select(Message)
                .where(
                    Message.conversation_id == conv_id,
                    Message.role == "user"
                )
                .order_by(Message.create_time)
                .limit(1)
            )
            result = await db_session.execute(query)
            first_message = result.scalar_one_or_none()

            if first_message:
                # 取前20个字符作为标题
                title = first_message.content[:20]
                if len(first_message.content) > 20:
                    title += "..."

                conversation = await get_conversation_by_id(db_session, conv_id)
                if conversation and conversation.title == "新对话":
                    conversation.title = title

        await db_session.commit()
        logger.info(f"助手消息保存成功：conversation_id={conv_id}")


async def save_clarification_message_with_new_session(
    conversation_id: int,
    clarification_text: str,
    should_update_title: bool = False
) -> None:
    """使用新的数据库会话保存追问消息（用于流式响应后）"""
    await save_assistant_message_with_new_session(
        conversation_id=conversation_id,
        content=clarification_text,
        thinking_process=None,
        should_update_title=should_update_title
    )

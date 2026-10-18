"""后台任务CRUD操作"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.task import Task, TaskStatus
from core.logger import logger


async def create_task(
    db: AsyncSession,
    task_data: Dict[str, Any]
) -> Task:
    """创建任务记录"""
    logger.info(f"创建后台任务：task_type={task_data.get('task_type')}, user_id={task_data.get('user_id')}")

    record = Task(**task_data)

    db.add(record)
    await db.commit()
    await db.refresh(record)

    logger.info(f"后台任务创建成功：id={record.id}")
    return record


async def get_task_by_id(
    db: AsyncSession,
    task_id: int
) -> Optional[Task]:
    """根据ID获取任务"""
    logger.debug(f"查询后台任务：task_id={task_id}")

    query = select(Task).where(Task.id == task_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record:
        logger.debug(f"找到后台任务：id={record.id}, status={record.status}")
    else:
        logger.warning(f"后台任务不存在：task_id={task_id}")

    return record


async def get_tasks_by_user(
    db: AsyncSession,
    user_id: int,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Task], int]:
    """获取用户的任务列表"""
    logger.info(f"获取用户后台任务列表：user_id={user_id}, page={page}, page_size={page_size}")

    # 构建查询条件
    conditions = [Task.user_id == user_id]
    if task_type:
        conditions.append(Task.task_type == task_type)
    if status:
        conditions.append(Task.status == status)

    # 总数查询
    count_query = select(func.count(Task.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # 列表查询
    query = (
        select(Task)
        .where(and_(*conditions))
        .order_by(desc(Task.create_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    records = list(result.scalars().all())

    logger.info(f"查询到 {len(records)} 条后台任务，总数={total}")
    return records, total


async def update_task(
    db: AsyncSession,
    task_id: int,
    update_data: Dict[str, Any]
) -> Optional[Task]:
    """更新任务"""
    logger.debug(f"更新后台任务：task_id={task_id}, fields={list(update_data.keys())}")

    record = await get_task_by_id(db, task_id)
    if not record:
        logger.warning(f"后台任务不存在，无法更新：task_id={task_id}")
        return None

    # 更新字段
    for key, value in update_data.items():
        if hasattr(record, key):
            setattr(record, key, value)

    await db.commit()
    await db.refresh(record)

    logger.debug(f"后台任务更新成功：id={record.id}, status={record.status}")
    return record


async def get_conversations_by_trip_id(
    db: AsyncSession,
    trip_id: int,
    user_id: int
) -> List[Any]:
    """获取关联到指定行程的会话列表"""
    from models.conversation import Conversation

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

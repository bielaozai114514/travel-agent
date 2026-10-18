"""旅行规划CRUD操作"""

from typing import List, Optional, Tuple
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.trip_plan import TripPlanRecord
from schemas.trip import TripPlan
from core.logger import logger


async def create_trip_plan(
    db: AsyncSession,
    user_id: int,
    trip_plan: TripPlan,
    title: Optional[str] = None
) -> TripPlanRecord:
    """创建旅行规划记录"""
    logger.info(f"创建旅行规划：user_id={user_id}, city={trip_plan.city}")
    
    # travel_days = len(trip_plan.days) if trip_plan.days else 0
    
    if not title:
        title = f"{trip_plan.city}{len(trip_plan.days)}日游"
    
    record = TripPlanRecord(
        user_id=user_id,
        title=title,
        city=trip_plan.city,
        start_date=trip_plan.start_date,
        end_date=trip_plan.end_date,
        travel_days=len(trip_plan.days),
        transportation=getattr(trip_plan.days[0], 'transportation', None) if trip_plan.days else None,
        accommodation=getattr(trip_plan.days[0], 'accommodation', None) if trip_plan.days else None,
        preferences=None,
        plan_data=trip_plan.model_dump()
    )
    
    db.add(record)
    await db.commit()
    await db.refresh(record)
    
    logger.info(f"旅行规划创建成功：id={record.id}")
    return record


async def get_trip_plan_by_id(
    db: AsyncSession,
    plan_id: int,
    user_id: Optional[int] = None
) -> Optional[TripPlanRecord]:
    """根据ID获取旅行规划"""
    logger.debug(f"查询旅行规划：plan_id={plan_id}, user_id={user_id}")
    
    query = select(TripPlanRecord).where(
        TripPlanRecord.id == plan_id,
        TripPlanRecord.is_deleted == 0
    )
    
    if user_id:
        query = query.where(TripPlanRecord.user_id == user_id)
    
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if record:
        logger.debug(f"找到旅行规划：id={record.id}, city={record.city}")
    else:
        logger.warning(f"旅行规划不存在或无权访问：plan_id={plan_id}")
    
    return record


async def get_trip_plans_by_user(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[TripPlanRecord], int]:
    """获取用户的旅行规划列表"""
    logger.info(f"获取用户旅行规划列表：user_id={user_id}, page={page}, page_size={page_size}")
    
    count_query = select(func.count(TripPlanRecord.id)).where(
        TripPlanRecord.user_id == user_id,
        TripPlanRecord.is_deleted == 0
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    query = (
        select(TripPlanRecord)
        .where(
            TripPlanRecord.user_id == user_id,
            TripPlanRecord.is_deleted == 0
        )
        .order_by(desc(TripPlanRecord.update_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    records = list(result.scalars().all())
    
    logger.info(f"查询到 {len(records)} 条旅行规划，总数={total}")
    return records, total


async def update_trip_plan(
    db: AsyncSession,
    plan_id: int,
    user_id: int,
    plan_data: dict
) -> Optional[TripPlanRecord]:
    """更新旅行规划"""
    logger.info(f"更新旅行规划：plan_id={plan_id}, user_id={user_id}")
    
    record = await get_trip_plan_by_id(db, plan_id, user_id)
    if not record:
        logger.warning(f"旅行规划不存在，无法更新：plan_id={plan_id}")
        return None
    
    record.plan_data = plan_data
    
    if 'city' in plan_data:
        record.city = plan_data['city']
    if 'start_date' in plan_data:
        record.start_date = plan_data['start_date']
    if 'end_date' in plan_data:
        record.end_date = plan_data['end_date']
    if 'travel_days' in plan_data:
        record.travel_days = plan_data['travel_days']
    
    await db.commit()
    await db.refresh(record)
    
    logger.info(f"旅行规划更新成功：id={record.id}")
    return record


async def delete_trip_plan(
    db: AsyncSession,
    plan_id: int,
    user_id: int
) -> bool:
    """软删除旅行规划"""
    logger.info(f"软删除旅行规划：plan_id={plan_id}, user_id={user_id}")
    
    record = await get_trip_plan_by_id(db, plan_id, user_id)
    if not record:
        logger.warning(f"旅行规划不存在，无法删除：plan_id={plan_id}")
        return False
    
    record.is_deleted = 1
    await db.commit()
    
    logger.info(f"旅行规划删除成功：plan_id={plan_id}")
    return True

"""旅行规划API路由"""

from typing import Annotated, List
from fastapi import APIRouter, HTTPException, Security, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from dependencies.auth import get_current_user
from dependencies.db_session import get_db
from models.user import User
from models.trip_plan import TripPlanRecord
from schemas.trip import TripRequest, TripPlanResponse, TripPlan
from core.trip_planner_agent import TripPlannerAgent
from services.amap_service import get_amap_mcp_tool
from core.logger import logger
from core.timing import TimingCollector
# Note: fix_trip_plan_locations 已移入 TripPlannerAgent._normalize_plan() 阶段，不再在 router 层调用
from curd.trip_plan import (
    create_trip_plan,
    get_trip_plan_by_id,
    get_trip_plans_by_user,
    update_trip_plan,
    delete_trip_plan
)

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划并保存"
)
async def plan_trip(
    request: TripRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    db: AsyncSession = Depends(get_db)
):
    """
    生成旅行计划并保存到数据库
    """
    import asyncio

    try:
        logger.info(f"收到旅行规划请求: 用户={current_user.username}, 城市={request.city}, 天数={request.travel_days}")

        # 获取MCP工具单例
        mcp_tool = get_amap_mcp_tool()
        # 每次请求新建TripPlannerAgent实例
        agent = TripPlannerAgent(mcp_tool=mcp_tool)
        # 使用异步方法生成旅行计划（坐标修正已在 aplan_trip 内部完成）
        trip_plan = await agent.aplan_trip(request)

        # 存入数据库
        record = await create_trip_plan(db, current_user.id, trip_plan)
        logger.info(f"旅行计划生成并保存成功: 城市={request.city}, id={record.id}")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except Exception as e:
        logger.error(f"生成旅行计划失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.get(
    "/plans",
    summary="获取旅行规划列表",
    description="获取当前用户的旅行规划历史记录"
)
async def list_trip_plans(
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20
):
    """获取用户的旅行规划列表"""
    try:
        records, total = await get_trip_plans_by_user(db, current_user.id, page, page_size)
        
        return {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": str(r.id),
                        "title": r.title,
                        "city": r.city,
                        "start_date": r.start_date,
                        "end_date": r.end_date,
                        "travel_days": r.travel_days,
                        "create_time": r.create_time.isoformat() if r.create_time else None,
                        "update_time": r.update_time.isoformat() if r.update_time else None,
                    }
                    for r in records
                ],
                "total": total,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        logger.error(f"获取旅行规划列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/plans/{plan_id}",
    response_model=TripPlanResponse,
    summary="获取旅行规划详情",
    description="根据ID获取旅行规划的详细内容"
)
async def get_trip_plan_detail(
    plan_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db)
):
    """获取旅行规划详情"""
    try:
        record = await get_trip_plan_by_id(db, plan_id, current_user.id)
        if not record:
            raise HTTPException(status_code=404, detail="旅行规划不存在或无权访问")
        
        return TripPlanResponse(
            success=True,
            message="获取成功",
            data=record.plan_data
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取旅行规划详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/plans/{plan_id}",
    response_model=TripPlanResponse,
    summary="更新旅行规划",
    description="更新旅行规划内容"
)
async def update_trip_plan_endpoint(
    plan_id: int,
    plan_data: dict,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db)
):
    """更新旅行规划"""
    try:
        record = await update_trip_plan(db, plan_id, current_user.id, plan_data)
        if not record:
            raise HTTPException(status_code=404, detail="旅行规划不存在或无权访问")
        
        return TripPlanResponse(
            success=True,
            message="更新成功",
            data=record.plan_data
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新旅行规划失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/plans/{plan_id}",
    summary="删除旅行规划",
    description="软删除旅行规划"
)
async def delete_trip_plan_endpoint(
    plan_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    db: AsyncSession = Depends(get_db)
):
    """删除旅行规划"""
    try:
        success = await delete_trip_plan(db, plan_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="旅行规划不存在或无权访问")
        
        return {"success": True, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除旅行规划失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/plan/stream",
    summary="流式生成旅行计划",
    description="根据用户输入的旅行需求,流式生成详细的旅行计划"
)
async def plan_trip_stream(
    request: TripRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])]
):
    """流式生成旅行计划"""
    async def stream_generator():
        try:
            yield json.dumps({
                "type": "status",
                "data": "正在初始化..."
            }, ensure_ascii=False) + "\n"

            await asyncio.sleep(0.1)

            yield json.dumps({
                "type": "status",
                "data": "正在分析需求..."
            }, ensure_ascii=False) + "\n"

            await asyncio.sleep(0.1)

            # 获取MCP工具单例
            mcp_tool = get_amap_mcp_tool()
            # 每次请求新建TripPlannerAgent实例
            agent = TripPlannerAgent(mcp_tool=mcp_tool)

            yield json.dumps({
                "type": "status",
                "data": "正在检索旅游攻略..."
            }, ensure_ascii=False) + "\n"

            # 使用异步方法生成旅行计划（坐标修正已在内部阶段完成）
            trip_plan = await agent.aplan_trip(request)

            yield json.dumps({
                "type": "result",
                "data": trip_plan.model_dump()
            }, ensure_ascii=False) + "\n"

            yield json.dumps({
                "type": "done",
                "data": "旅行计划生成完成"
            }, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.error(f"流式生成旅行计划失败: {str(e)}")
            yield json.dumps({
                "type": "error",
                "data": f"生成失败: {str(e)}"
            }, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/plan/background",
    summary="后台生成旅行计划",
    description="在后台生成旅行计划，返回任务ID，可轮询查询进度"
)
async def plan_trip_background(
    request: TripRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    db: AsyncSession = Depends(get_db)
):
    """后台生成旅行计划"""
    from core.task_manager import TaskManager
    from services.amap_service import get_amap_mcp_tool

    try:
        logger.info(f"收到后台旅行规划请求: 用户={current_user.username}, 城市={request.city}")

        # 定义任务执行函数
        async def trip_plan_task(task_id: int, db_session, progress_callback):
            """行程规划任务执行逻辑"""
            timings = TimingCollector()

            # 步骤1: 初始化
            await progress_callback("初始化中...", 10, 1)

            with timings.measure("init_agent", "task"):
                mcp_tool = get_amap_mcp_tool()
                agent = TripPlannerAgent(mcp_tool=mcp_tool)

            # 步骤2: 检索攻略
            await progress_callback("检索旅游攻略...", 20, 2)

            # 步骤3: 提取候选景点
            await progress_callback("提取候选景点...", 30, 3)

            # 步骤4: 搜索景点和酒店
            await progress_callback("搜索景点和酒店...", 45, 4)

            # 步骤5: 查询天气
            await progress_callback("查询天气信息...", 55, 5)

            # 步骤6: 生成行程（坐标修正已在内部阶段完成）
            await progress_callback("生成行程计划...", 70, 6)
            with timings.measure("agent_plan_trip_total", "task"):
                trip_plan = await agent.aplan_trip(request)
            timings.extend(agent.get_timing_report().get("items", []), prefix="agent.")

            # 步骤7: 保存数据库
            await progress_callback("保存到数据库...", 90, 7)
            with timings.measure("db_save_trip_plan", "task"):
                record = await create_trip_plan(db_session, current_user.id, trip_plan)
                await db_session.commit()

            await progress_callback("完成！", 100, 7)
            timing_report = timings.report()
            ranking_preview = " | ".join(
                f"{idx + 1}.{item['stage']}={item['duration_seconds']}s"
                for idx, item in enumerate(timing_report["rank"][:8])
            )
            logger.info(f"[Timing] 行程规划耗时排名 task_id={task_id}: {ranking_preview}")

            return {
                "trip_id": record.id,
                "trip_plan": trip_plan.model_dump(),
                "timing_report": timing_report,
                "timing_rank": timing_report["rank"],
            }

        # 创建并运行任务
        task = await TaskManager.create_and_run_task(
            db=db,
            user_id=current_user.id,
            task_type="trip_plan",
            coroutine_func=trip_plan_task,
            input_data=request.model_dump(),
            total_steps=7,
        )

        logger.info(f"后台行程规划任务已创建: task_id={task.id}")

        return {
            "success": True,
            "message": "任务已创建，正在后台生成",
            "data": {
                "task_id": str(task.id)
            }
        }

    except Exception as e:
        logger.error(f"创建后台规划任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.post(
    "/plans/{plan_id}/conversation",
    summary="从行程开启会话",
    description="为指定行程创建或关联会话，返回会话ID"
)
async def create_conversation_from_trip(
    plan_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    db: AsyncSession = Depends(get_db)
):
    """从行程创建/关联会话"""
    # 检查行程权限
    trip = await get_trip_plan_by_id(db, plan_id, current_user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="行程不存在或无权访问")

    # 查找是否已有会话关联此行程
    from curd.conversation import get_conversations_by_trip_id
    existing_convs = await get_conversations_by_trip_id(db, plan_id, current_user.id)

    if existing_convs:
        # 返回最新的会话
        conversation = existing_convs[0]
        return {
            "success": True,
            "message": "找到已关联的会话",
            "data": {
                "conversation_id": str(conversation.id),
                "is_new": False
            }
        }

    # 创建新会话
    from curd.conversation import create_conversation
    from utils.snowflake_id import generate_snowflake_id as generate_id

    conversation = await create_conversation(db, {
        "id": generate_id(),
        "user_id": current_user.id,
        "title": f"{trip.city}行程讨论",
        "current_trip_id": plan_id,
    })

    return {
        "success": True,
        "message": "会话已创建",
        "data": {
            "conversation_id": str(conversation.id),
            "is_new": True
        }
    }


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 获取MCP工具单例
        mcp_tool = get_amap_mcp_tool()
        # 新建Agent实例测试
        agent = TripPlannerAgent(mcp_tool=mcp_tool)

        return {
            "status": "healthy",
            "service": "trip-planner",
            "agent_name": agent.planner_agent.name,
            "mcp_available": mcp_tool is not None
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )

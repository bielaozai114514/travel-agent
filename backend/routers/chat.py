"""
聊天路由 - 集成LLM与会话管理 + 意图识别 + 行程规划联动
"""
import json
from typing import Annotated, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import get_db
from dependencies.auth import get_current_user
from dependencies.llm import get_esagent_service_instance
from models.user import User
from schemas.conversation import MessageBase
from schemas.llm import LLMRequest, Message
from curd.conversation import (
    create_conversation,
    get_conversation_by_id,
    create_message,
    get_messages_by_conversation,
    update_conversation_title_by_first_message,
    update_conversation_generic,
    save_assistant_message_with_new_session,
    save_clarification_message_with_new_session,
)
from core.llm import generate_stream, generate_non_stream
from core.logger import logger
from core.timing import TimingCollector

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/send", summary="发送消息并获取回复（非流式）")
async def send_message(
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    content: str,
    conversation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    esagent_service: Annotated[object, Depends(get_esagent_service_instance)] = None,
):
    """发送消息并获取AI回复（非流式）"""
    actual_conv_id = None
    conv_id_for_response = None

    if not conversation_id:
        # 创建新会话
        conversation = await create_conversation(db, current_user.id)
        actual_conv_id = conversation.id
        conv_id_for_response = str(conversation.id)
    else:
        # 验证现有会话
        conversation = await get_conversation_by_id(db, conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或无权访问",
            )
        actual_conv_id = int(conversation_id)
        conv_id_for_response = conversation_id

    # 创建用户消息
    user_message = await create_message(db, actual_conv_id, "user", content)

    # 获取历史消息
    history_messages = await get_messages_by_conversation(db, actual_conv_id, current_user.id)

    messages = [
        Message(role=msg.role, content=msg.content)
        for msg in history_messages
    ]

    # 获取关联的行程
    trip_plan = None
    if conversation.current_trip_id:
        from curd.trip_plan import get_trip_plan_by_id
        trip_record = await get_trip_plan_by_id(db, conversation.current_trip_id, current_user.id)
        if trip_record:
            trip_plan = trip_record.plan_data

    try:
        response_content = await generate_non_stream(messages, trip_plan=trip_plan)

        # 创建AI回复
        assistant_message = await create_message(
            db, actual_conv_id, "assistant", response_content
        )

        # 自动更新标题
        if len(history_messages) <= 1:
            await update_conversation_title_by_first_message(db, actual_conv_id)

        return {
            "conversation_id": conv_id_for_response,
            "user_message": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
                "create_time": user_message.create_time.isoformat(),
            },
            "assistant_message": {
                "id": assistant_message.id,
                "role": assistant_message.role,
                "content": assistant_message.content,
                "create_time": assistant_message.create_time.isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"生成回复失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成回复失败: {str(e)}",
        )


class StreamRequest(BaseModel):
    """流式请求模型"""
    content: str = Field(..., description="用户消息内容")
    conversation_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")


@router.post("/stream", summary="发送消息并获取流式回复")
async def send_message_stream(
    request: StreamRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    db: AsyncSession = Depends(get_db),
    esagent_service: Annotated[object, Depends(get_esagent_service_instance)] = None,
):
    """
    发送消息并获取AI流式回复

    集成意图识别：
    - 如果用户想规划行程 → 走规划流程
    - 如果用户想修改行程 → 走修改流程（第一版重新生成）
    - 否则 → 走正常聊天流程（注入行程上下文）
    """
    content = request.content
    conversation_id = request.conversation_id

    actual_conv_id = None
    conv_id_for_response = None

    logger.info(f"流式消息请求：user_id={current_user.id}, conversation_id={conversation_id}")

    if not conversation_id:
        # 创建新会话
        conversation = await create_conversation(db, current_user.id)
        actual_conv_id = conversation.id
        conv_id_for_response = str(conversation.id)
        logger.info(f"创建新会话：conversation_id={actual_conv_id}")
    else:
        # 验证现有会话
        conversation = await get_conversation_by_id(db, conversation_id, current_user.id)
        if not conversation:
            logger.warning(f"会话不存在或无权访问：conversation_id={conversation_id}, user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或无权访问",
            )
        actual_conv_id = int(conversation_id)
        conv_id_for_response = conversation_id

    # 创建用户消息
    user_message = await create_message(db, actual_conv_id, "user", content)
    logger.debug(f"用户消息已保存：message_id={user_message.id}")

    # 获取历史消息
    history_messages = await get_messages_by_conversation(db, actual_conv_id, current_user.id)

    messages = [
        Message(role=msg.role, content=msg.content)
        for msg in history_messages
    ]

    # 获取关联的行程
    trip_plan = None
    current_trip_id = conversation.current_trip_id
    if current_trip_id:
        from curd.trip_plan import get_trip_plan_by_id
        trip_record = await get_trip_plan_by_id(db, current_trip_id, current_user.id)
        if trip_record:
            trip_plan = trip_record.plan_data

    # 分析用户意图
    from core.trip_intent_agent import get_trip_intent_agent, IntentType
    intent_agent = get_trip_intent_agent()

    # 构建历史消息格式传给 intent agent
    history_for_intent = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages
        if getattr(msg, "id", None) != getattr(user_message, "id", None)
    ]

    intent_result = await intent_agent.analyze_intent(content, history_for_intent)
    logger.info(f"意图分析结果: type={intent_result.intent_type}, "
                f"params={intent_result.parameters}, "
                f"missing={intent_result.missing_params}, "
                f"clarification={intent_result.clarification_question}")

    # 根据意图选择处理流程
    if intent_result.intent_type == IntentType.TRIP_PLANNING:
        # 行程规划意图 - 检查是否真的缺失必要参数
        # 必要参数：city + travel_days；或 city + start_date + end_date
        has_city = bool(intent_result.parameters.get("city"))
        has_start_date = bool(intent_result.parameters.get("start_date"))
        has_end_date = bool(intent_result.parameters.get("end_date"))
        has_days = bool(intent_result.parameters.get("travel_days"))
        has_date_range = has_start_date and has_end_date

        logger.info(
            f"参数检查: has_city={has_city}, has_start_date={has_start_date}, "
            f"has_end_date={has_end_date}, has_days={has_days}"
        )

        # 只有当确实缺少必要参数时才追问
        missing_essential = not has_city or (not has_days and not has_date_range)

        logger.info(f"missing_essential={missing_essential}, intent_result.missing_params={intent_result.missing_params}")

        if missing_essential:
            # 参数不全，返回追问问题
            clarification_q = intent_result.clarification_question or "请提供更多信息。"
            logger.info(f"返回追问: {clarification_q}")
            return _stream_clarification(
                db,
                actual_conv_id,
                conv_id_for_response,
                user_message,
                clarification_q,
                history_messages
            )
        else:
            # 参数完整，启动后台规划
            logger.info(f"参数完整，启动后台规划: {intent_result.parameters}")
            return await _stream_start_trip_planning(
                db=db,
                current_user=current_user,
                conversation_id=actual_conv_id,
                conv_id_for_response=conv_id_for_response,
                user_message=user_message,
                intent_params=intent_result.parameters,
                free_text_input=intent_result.free_text_input or "",
            )

    elif intent_result.intent_type == IntentType.TRIP_MODIFICATION:
        # 行程修改意图
        if not current_trip_id:
            return _stream_clarification(
                db,
                actual_conv_id,
                conv_id_for_response,
                user_message,
                "你还没有关联的行程哦！可以先告诉我你想去哪个城市，我来帮你规划一个新行程~",
                history_messages
            )
        else:
            # 启动后台修改任务
            return await _stream_start_trip_modification(
                db=db,
                current_user=current_user,
                conversation_id=actual_conv_id,
                conv_id_for_response=conv_id_for_response,
                user_message=user_message,
                current_trip_id=current_trip_id,
                modification_summary=intent_result.modification_summary or content,
                history_messages=history_messages,
            )

    else:
        # 普通聊天意图
        return _stream_normal_chat(
            db=db,
            current_user=current_user,
            conversation_id=actual_conv_id,
            conv_id_for_response=conv_id_for_response,
            user_message=user_message,
            history_messages=history_messages,
            messages=messages,
            trip_plan=trip_plan,
            esagent_service=esagent_service,
        )


def _stream_clarification(
    db: AsyncSession,
    conversation_id: int,
    conv_id_for_response: str,
    user_message: Any,
    clarification_text: str,
    history_messages: List
) -> StreamingResponse:
    """返回追问的流式响应"""
    async def stream_generator():
        # 返回会话ID
        yield json.dumps({
            "type": "conversation_id",
            "data": conv_id_for_response
        }, ensure_ascii=False) + "\n"

        # 返回用户消息
        yield json.dumps({
            "type": "user_message",
            "data": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
            }
        }, ensure_ascii=False) + "\n"

        # 返回追问内容
        for char in clarification_text:
            yield json.dumps({
                "type": "content",
                "data": char
            }, ensure_ascii=False) + "\n"
            import asyncio
            await asyncio.sleep(0.02)

        # 使用curd层函数保存消息
        await save_clarification_message_with_new_session(
            conversation_id=conversation_id,
            clarification_text=clarification_text,
            should_update_title=len(history_messages) <= 1
        )

        # 完成
        yield json.dumps({
            "type": "done",
            "data": {
                "conversation_id": conv_id_for_response,
            }
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


async def _stream_start_trip_planning(
    db: AsyncSession,
    current_user: User,
    conversation_id: int,
    conv_id_for_response: str,
    user_message: Any,
    intent_params: Dict[str, Any],
    free_text_input: str = ""
) -> StreamingResponse:
    """启动后台行程规划的流式响应"""
    from schemas.trip import TripRequest
    from datetime import datetime, timedelta

    # 构建 TripRequest
    city = intent_params.get("city", "")

    # 修复 travel_days - 确保是整数。只有明确天数或日期范围才允许启动规划。
    travel_days = intent_params.get("travel_days")
    if travel_days is not None:
        try:
            travel_days = int(travel_days)
        except (ValueError, TypeError) as e:
            raise ValueError("旅行天数格式不正确，请重新提供天数") from e
        if travel_days <= 0:
            raise ValueError("旅行天数必须大于0")

    # 处理日期
    start_date = intent_params.get("start_date")
    end_date = intent_params.get("end_date")

    # 如果 start_date 还是 None 或者格式不对，设置默认值
    if not start_date:
        # 默认从明天开始
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # 尝试解析日期，确保格式正确
        try:
            # 如果已经是 YYYY-MM-DD 格式，直接使用
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            # 如果格式不对，使用明天作为默认
            logger.warning(f"无法解析日期 {start_date}，使用默认日期")
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("结束日期格式不正确，请使用 YYYY-MM-DD") from e

    if not end_date and travel_days:
        # 根据天数计算结束日期
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=travel_days - 1)
            end_date = end_dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"计算结束日期失败: {e}")
            end_date = start_date
    elif end_date and travel_days is None:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            travel_days = (end_dt - start_dt).days + 1
        except Exception as e:
            raise ValueError("无法根据开始和结束日期计算旅行天数") from e

    if travel_days is None:
        raise ValueError("缺少旅行天数或结束日期，无法启动行程规划")
    if travel_days <= 0:
        raise ValueError("结束日期必须晚于或等于开始日期")

    logger.info(f"行程规划参数: city={city}, start_date={start_date}, end_date={end_date}, travel_days={travel_days}")

    trip_request = TripRequest(
        city=city,
        start_date=start_date,
        end_date=end_date,
        travel_days=travel_days,
        transportation=intent_params.get("transportation", "公共交通"),
        accommodation=intent_params.get("accommodation", "舒适型"),
        preferences=intent_params.get("preferences", ["历史文化", "自然景观"]),
        free_text_input=free_text_input
    )

    # 创建后台任务
    from core.task_manager import TaskManager
    from services.amap_service import get_amap_mcp_tool
    from core.trip_planner_agent import TripPlannerAgent
    # fix_trip_plan_locations 已移入 aplan_trip 内部阶段，规划路径无需再调用
    from curd.trip_plan import create_trip_plan
    import asyncio

    async def trip_plan_task(task_id: int, db_session, progress_callback):
        """行程规划任务执行逻辑"""
        timings = TimingCollector()

        # 步骤1: 初始化
        await progress_callback("初始化中...", 10, 1)

        with timings.measure("init_agent", "task"):
            mcp_tool = get_amap_mcp_tool()
            agent = TripPlannerAgent(mcp_tool=mcp_tool)

        # 步骤2: 搜索攻略
        await progress_callback("搜索旅游攻略...", 20, 2)

        # 步骤3: 搜索景点
        await progress_callback("搜索景点信息...", 35, 3)

        # 步骤4: 查询天气
        await progress_callback("查询天气信息...", 50, 4)

        # 步骤5: 搜索酒店
        await progress_callback("搜索酒店推荐...", 65, 5)

        # 步骤6: 生成行程
        await progress_callback("生成行程计划...", 80, 6)
        with timings.measure("agent_plan_trip_total", "task"):
            trip_plan = await agent.aplan_trip(trip_request)
        timings.extend(agent.get_timing_report().get("items", []), prefix="agent.")

        # 坐标修正已在 aplan_trip 内部阶段完成，无需重复调用

        # 步骤7: 保存数据库
        await progress_callback("保存到数据库...", 90, 7)
        with timings.measure("db_create_trip_plan", "task"):
            record = await create_trip_plan(db_session, current_user.id, trip_plan)

        # 关联会话和行程
        with timings.measure("db_link_conversation_trip", "task"):
            await update_conversation_generic(
                db_session, conversation_id, current_user.id,
                {"current_trip_id": record.id}
            )

        # 添加规划完成的消息
        completion_message = (
            f"🎉 行程规划完成！我已经为你生成了 {city}{travel_days} 天的行程。\n\n"
            f"你可以在右侧查看行程摘要，或点击「查看完整行程」按钮查看详细规划和地图。"
        )
        with timings.measure("db_create_completion_message", "task"):
            await create_message(
                db_session, conversation_id, "assistant", completion_message
            )

        with timings.measure("db_final_commit", "task"):
            await db_session.commit()

        await progress_callback("完成！", 100, 8)
        timing_report = timings.report()
        ranking_preview = " | ".join(
            f"{idx + 1}.{item['stage']}={item['duration_seconds']}s"
            for idx, item in enumerate(timing_report["rank"][:8])
        )
        logger.info(f"[Timing] 对话触发行程规划耗时排名 task_id={task_id}: {ranking_preview}")

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
        input_data=trip_request.model_dump(),
        total_steps=8,
        conversation_id=conversation_id,
    )

    logger.info(f"后台行程规划任务已创建: task_id={task.id}")

    # 返回流式响应
    async def stream_generator():
        # 返回会话ID
        yield json.dumps({
            "type": "conversation_id",
            "data": conv_id_for_response
        }, ensure_ascii=False) + "\n"

        # 返回用户消息
        yield json.dumps({
            "type": "user_message",
            "data": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
            }
        }, ensure_ascii=False) + "\n"

        # 返回任务开始信息
        yield json.dumps({
            "type": "task_started",
            "data": {
                "task_id": str(task.id),
                "message": f"好的！我正在为你规划{city}{travel_days}天的行程，请稍候..."
            }
        }, ensure_ascii=False) + "\n"

        # 返回确认消息
        confirmation_text = f"好的！我正在为你规划{city}{travel_days}天的行程，请稍候...\n\n你可以在右侧看到规划进度，或随时切换页面，后台会继续生成~"
        for char in confirmation_text:
            yield json.dumps({
                "type": "content",
                "data": char
            }, ensure_ascii=False) + "\n"
            import asyncio
            await asyncio.sleep(0.01)

        # 完成
        yield json.dumps({
            "type": "done",
            "data": {
                "task_id": str(task.id),
                "conversation_id": str(conv_id_for_response),
            }
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


async def _stream_start_trip_modification(
    db: AsyncSession,
    current_user: User,
    conversation_id: int,
    conv_id_for_response: str,
    user_message: Any,
    current_trip_id: int,
    modification_summary: str,
    history_messages: List,
) -> StreamingResponse:
    """启动后台行程修改的流式响应"""
    from schemas.trip import TripPlan

    # 获取原行程
    from curd.trip_plan import get_trip_plan_by_id
    trip_record = await get_trip_plan_by_id(db, current_trip_id, current_user.id)
    if not trip_record:
        return _stream_clarification(
            db,
            conversation_id,
            conv_id_for_response,
            user_message,
            "找不到原行程了，可能已被删除。你可以重新告诉我想去哪，我来帮你规划新行程~",
            history_messages
        )

    original_trip = TripPlan(**trip_record.plan_data)
    city = original_trip.city

    # 构建对话历史摘要
    conversation_history = "\n".join([
        f"{msg.role}: {msg.content}"
        for msg in history_messages[-10:]  # 只保留最近10条
    ]) if history_messages else None

    # 创建后台任务
    from core.task_manager import TaskManager
    from services.amap_service import get_amap_mcp_tool
    from core.trip_modifier_agent import get_trip_modifier_agent
    from services.location_fix_service import fix_trip_plan_locations
    from curd.trip_plan import create_trip_plan
    from curd.conversation import update_conversation_generic

    async def trip_modification_task(task_id: int, db_session, progress_callback):
        """行程修改任务执行逻辑"""
        timings = TimingCollector()

        # 步骤1: 初始化
        await progress_callback("初始化中...", 10, 1)

        with timings.measure("init_modifier_agent", "task"):
            mcp_tool = get_amap_mcp_tool()
            agent = get_trip_modifier_agent(mcp_tool=mcp_tool)

        # 步骤2: 分析修改需求
        await progress_callback("分析修改需求...", 25, 2)

        # 步骤3: 修改行程
        await progress_callback("修改行程中...", 50, 3)
        with timings.measure("agent_modify_trip_total", "task"):
            modified_trip = await agent.amodify_trip(
                original_trip=original_trip,
                modification_summary=modification_summary,
                conversation_history=conversation_history
            )

        # 步骤4: 修正坐标
        await progress_callback("修正景点坐标...", 70, 4)
        import asyncio
        with timings.measure("location_fix", "task"):
            modified_trip = await asyncio.to_thread(fix_trip_plan_locations, modified_trip)

        # 步骤5: 保存新行程
        await progress_callback("保存新行程...", 85, 5)
        with timings.measure("db_create_modified_trip_plan", "task"):
            new_record = await create_trip_plan(db_session, current_user.id, modified_trip)

        # 步骤6: 关联会话和新行程
        await progress_callback("更新会话关联...", 95, 6)
        with timings.measure("db_link_conversation_trip", "task"):
            await update_conversation_generic(
                db_session, conversation_id, current_user.id,
                {"current_trip_id": new_record.id}
            )

        # 添加修改完成的消息
        completion_message = (
            f"🎉 行程修改完成！我已经根据你的要求调整了 {city} 的行程。\n\n"
            f"你可以在右侧查看修改后的行程摘要，或点击「查看完整行程」按钮查看详细规划。"
        )
        with timings.measure("db_create_completion_message", "task"):
            await create_message(
                db_session, conversation_id, "assistant", completion_message
            )

        with timings.measure("db_final_commit", "task"):
            await db_session.commit()

        await progress_callback("完成！", 100, 6)
        timing_report = timings.report()
        ranking_preview = " | ".join(
            f"{idx + 1}.{item['stage']}={item['duration_seconds']}s"
            for idx, item in enumerate(timing_report["rank"][:8])
        )
        logger.info(f"[Timing] 行程修改耗时排名 task_id={task_id}: {ranking_preview}")

        return {
            "trip_id": new_record.id,
            "trip_plan": modified_trip.model_dump(),
            "timing_report": timing_report,
            "timing_rank": timing_report["rank"],
        }

    # 创建并运行任务
    task = await TaskManager.create_and_run_task(
        db=db,
        user_id=current_user.id,
        task_type="trip_modification",
        coroutine_func=trip_modification_task,
        input_data={
            "original_trip_id": current_trip_id,
            "modification_summary": modification_summary,
        },
        total_steps=6,
        conversation_id=conversation_id,
        trip_id=current_trip_id,
    )

    logger.info(f"后台行程修改任务已创建: task_id={task.id}")

    # 返回流式响应
    async def stream_generator():
        # 返回会话ID
        yield json.dumps({
            "type": "conversation_id",
            "data": conv_id_for_response
        }, ensure_ascii=False) + "\n"

        # 返回用户消息
        yield json.dumps({
            "type": "user_message",
            "data": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
            }
        }, ensure_ascii=False) + "\n"

        # 返回任务开始信息
        yield json.dumps({
            "type": "task_started",
            "data": {
                "task_id": str(task.id),
                "message": f"好的！我正在帮你修改{city}的行程，请稍候..."
            }
        }, ensure_ascii=False) + "\n"

        # 返回确认消息
        confirmation_text = f"好的！我正在帮你修改{city}的行程，请稍候...\n\n你可以在右侧看到修改进度，或随时切换页面，后台会继续修改~"
        for char in confirmation_text:
            yield json.dumps({
                "type": "content",
                "data": char
            }, ensure_ascii=False) + "\n"
            import asyncio
            await asyncio.sleep(0.01)

        # 完成
        yield json.dumps({
            "type": "done",
            "data": {
                "task_id": str(task.id),
                "conversation_id": str(conv_id_for_response),
            }
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


def _stream_normal_chat(
    db: AsyncSession,
    current_user: User,
    conversation_id: int,
    conv_id_for_response: str,
    user_message: Any,
    history_messages: List,
    messages: List[Message],
    trip_plan: Optional[Dict[str, Any]],
    esagent_service: Any,
) -> StreamingResponse:
    """普通聊天的流式响应"""
    async def stream_generator():
        full_content = ""
        thinking_process = []
        current_thinking = None
        current_tool_call = None

        try:
            # 返回会话ID
            yield json.dumps({
                "type": "conversation_id",
                "data": conv_id_for_response
            }, ensure_ascii=False) + "\n"

            # 返回用户消息
            yield json.dumps({
                "type": "user_message",
                "data": {
                    "id": user_message.id,
                    "role": user_message.role,
                    "content": user_message.content,
                }
            }, ensure_ascii=False) + "\n"

            logger.info(f"开始流式生成回复：conversation_id={conversation_id}")

            if not esagent_service:
                yield json.dumps({
                    "type": "error",
                    "data": "LLM服务不可用，请检查配置"
                }, ensure_ascii=False) + "\n"
                return

            # 流式生成（传入行程数据）
            async for chunk_bytes in generate_stream(messages, trip_plan=trip_plan):
                chunk_str = chunk_bytes.decode("utf-8")
                chunk_data = json.loads(chunk_str)

                chunk_type = chunk_data.get("type")
                chunk_content = chunk_data.get("data")

                if chunk_type == "content":
                    if not full_content:
                        pass  # 第一个内容块
                    full_content += chunk_content
                    yield chunk_str
                    # 添加小延迟，让前端有流式的感觉
                    import asyncio
                    await asyncio.sleep(0.03)
                elif chunk_type == "thinking_start":
                    current_thinking = {
                        "type": "thinking",
                        "iteration": chunk_content.get("iteration"),
                        "content": ""
                    }
                    yield chunk_str
                elif chunk_type == "thinking_content":
                    if current_thinking:
                        current_thinking["content"] += chunk_content
                    yield chunk_str
                elif chunk_type == "thinking_end":
                    if current_thinking:
                        thinking_process.append(current_thinking)
                        current_thinking = None
                    yield chunk_str
                elif chunk_type == "tool_call_start":
                    current_tool_call = {
                        "type": "tool_call",
                        "tool_name": chunk_content.get("tool_name"),
                        "parameters": chunk_content.get("parameters"),
                        "result": ""
                    }
                    yield chunk_str
                elif chunk_type == "tool_call_end":
                    if current_tool_call:
                        current_tool_call["result"] = chunk_content.get("result")
                        thinking_process.append(current_tool_call)
                        current_tool_call = None
                    yield chunk_str
                elif chunk_type == "done":
                    break
                elif chunk_type == "error":
                    yield chunk_str
                    return
                elif "content" in chunk_data:
                    if chunk_data["content"] == "[DONE]":
                        break
                    full_content += chunk_data["content"]
                    yield json.dumps({
                        "type": "content",
                        "data": chunk_data["content"]
                    }, ensure_ascii=False) + "\n"
                elif "error" in chunk_data:
                    yield json.dumps({
                        "type": "error",
                        "data": chunk_data["error"]
                    }, ensure_ascii=False) + "\n"
                    return

            # 使用curd层函数保存消息
            await save_assistant_message_with_new_session(
                conversation_id=conversation_id,
                content=full_content,
                thinking_process=thinking_process if thinking_process else None,
                should_update_title=len(history_messages) <= 1
            )

            # 完成
            yield json.dumps({
                "type": "done",
                "data": {
                    "conversation_id": conv_id_for_response,
                }
            }, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.error(f"流式生成出错: {e}", exc_info=True)
            yield json.dumps({
                "type": "error",
                "data": f"生成回复失败: {str(e)}"
            }, ensure_ascii=False) + "\n"
            return

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
    "/conversation/{conversation_id}/link-trip",
    summary="将会话关联到行程",
    description="为会话指定当前行程"
)
async def link_conversation_to_trip(
    conversation_id: str,
    trip_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["chat:send"])],
    db: AsyncSession = Depends(get_db)
):
    """关联会话和行程"""
    from curd.conversation import update_conversation_generic, get_conversation_by_id
    from curd.trip_plan import get_trip_plan_by_id

    # 验证权限
    conversation = await get_conversation_by_id(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    trip = await get_trip_plan_by_id(db, trip_id, current_user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="行程不存在")

    # 更新关联
    await update_conversation_generic(db, conversation_id, current_user.id, {"current_trip_id": trip_id})

    return {"success": True, "message": "关联成功"}

"""轻量级后台任务管理器"""

import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models import AsyncSessionLocal
from models.task import Task, TaskStatus
from curd.task import create_task, update_task, get_task_by_id
from core.logger import logger
from utils.snowflake_id import generate_snowflake_id as generate_id


class TaskManager:
    """轻量级任务管理器"""

    # 存储运行中的任务：{task_id: asyncio.Task}
    _running_tasks: Dict[int, asyncio.Task] = {}

    @classmethod
    async def create_and_run_task(
        cls,
        db: AsyncSession,
        user_id: int,
        task_type: str,
        coroutine_func: Callable,
        input_data: Optional[Dict] = None,
        trip_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        total_steps: int = 5,
    ) -> Task:
        """
        创建并运行后台任务

        Args:
            db: 数据库会话（仅用于创建任务记录）
            user_id: 用户ID
            task_type: 任务类型
            coroutine_func: 异步执行函数，签名：async def func(task_id, db_session, progress_callback)
            input_data: 输入数据
            trip_id: 关联的行程ID
            conversation_id: 关联的会话ID
            total_steps: 总步骤数

        Returns:
            Task对象
        """
        # 1. 创建任务记录
        task_id = generate_id()
        task = await create_task(db, {
            "id": task_id,
            "user_id": user_id,
            "task_type": task_type,
            "trip_id": trip_id,
            "conversation_id": conversation_id,
            "status": TaskStatus.PENDING,
            "input_data": input_data,
            "total_steps": total_steps,
        })

        # 2. 定义进度回调（使用独立 session）
        async def progress_callback(step_name: str, step_progress: int, current_step: int = None):
            """进度更新回调 - 使用独立 session"""
            async with AsyncSessionLocal() as session:
                try:
                    await update_task(session, task_id, {
                        "current_step": step_name,
                        "step_progress": step_progress,
                        "status": TaskStatus.RUNNING,
                    })
                    await session.commit()
                except Exception as e:
                    logger.error(f"[Task] 更新进度失败: task_id={task_id}, error={str(e)}")
                    await session.rollback()

        # 3. 包装任务执行（使用独立 session）
        async def wrapped_task():
            task_session = None
            try:
                logger.info(f"[Task] 任务开始: task_id={task_id}, type={task_type}")

                # 创建独立的 session 供任务使用
                task_session = AsyncSessionLocal()

                # 更新状态为运行中（用独立 session）
                async with AsyncSessionLocal() as session:
                    await update_task(session, task_id, {
                        "status": TaskStatus.RUNNING,
                        "start_time": datetime.utcnow(),
                    })
                    await session.commit()

                # 执行实际任务（传入独立 session）
                result = await coroutine_func(task_id, task_session, progress_callback)

                # 更新为完成（用独立 session）
                async with AsyncSessionLocal() as session:
                    await update_task(session, task_id, {
                        "status": TaskStatus.COMPLETED,
                        "output_data": result,
                        "step_progress": 100,
                        "end_time": datetime.utcnow(),
                    })
                    await session.commit()

                logger.info(f"[Task] 任务完成: task_id={task_id}")

            except asyncio.CancelledError:
                logger.warning(f"[Task] 任务被取消: task_id={task_id}")
                async with AsyncSessionLocal() as session:
                    await update_task(session, task_id, {
                        "status": TaskStatus.CANCELLED,
                        "end_time": datetime.utcnow(),
                    })
                    await session.commit()
            except Exception as e:
                logger.error(f"[Task] 任务失败: task_id={task_id}, error={str(e)}", exc_info=True)
                async with AsyncSessionLocal() as session:
                    await update_task(session, task_id, {
                        "status": TaskStatus.FAILED,
                        "error_message": str(e),
                        "end_time": datetime.utcnow(),
                    })
                    await session.commit()
                await cls._save_task_failure_message(conversation_id, task_type, str(e))
            finally:
                # 关闭任务 session
                if task_session:
                    await task_session.close()
                # 从运行列表移除
                cls._running_tasks.pop(task_id, None)

        # 4. 启动后台任务
        asyncio_task = asyncio.create_task(wrapped_task())
        cls._running_tasks[task_id] = asyncio_task

        return task

    @classmethod
    def _build_task_failure_message(cls, task_type: str, error_message: str) -> str:
        """构建后台任务失败时写入会话的用户可见消息。"""
        public_error = (error_message or "未知错误").strip()
        if len(public_error) > 300:
            public_error = public_error[:300] + "..."

        if task_type == "trip_plan":
            prefix = "行程规划失败了"
            suggestion = "你可以稍后重试，或换一种更明确的描述，比如目的地、天数和偏好。"
        elif task_type == "trip_modification":
            prefix = "行程修改失败了"
            suggestion = "原行程没有被覆盖。你可以把想修改的天数、景点或日期说得更具体一些。"
        else:
            prefix = "后台任务失败了"
            suggestion = "你可以稍后重试。"

        return f"{prefix}，这次没有保存新的结果。\n\n原因：{public_error}\n\n{suggestion}"

    @classmethod
    async def _save_task_failure_message(
        cls,
        conversation_id: Optional[int],
        task_type: str,
        error_message: str
    ) -> None:
        """后台任务失败时，在关联会话中补一条助手消息，避免刷新后对话断层。"""
        if not conversation_id:
            return

        try:
            from curd.conversation import create_message

            async with AsyncSessionLocal() as session:
                await create_message(
                    session,
                    conversation_id,
                    "assistant",
                    cls._build_task_failure_message(task_type, error_message),
                )
        except Exception as save_error:
            logger.error(
                f"[Task] 保存失败消息失败: conversation_id={conversation_id}, error={save_error}",
                exc_info=True
            )

    @classmethod
    async def cancel_task(cls, db: AsyncSession, task_id: int, user_id: int) -> bool:
        """取消任务"""
        task = await get_task_by_id(db, task_id)
        if not task or task.user_id != user_id:
            return False

        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return True  # 已经结束

        # 标记为取消
        await update_task(db, task_id, {"is_cancelled": True})

        # 取消asyncio任务
        asyncio_task = cls._running_tasks.get(task_id)
        if asyncio_task and not asyncio_task.done():
            asyncio_task.cancel()

        return True

    @classmethod
    def get_running_task_count(cls) -> int:
        """获取当前运行中的任务数"""
        # 清理已完成的任务
        cls._running_tasks = {
            tid: t for tid, t in cls._running_tasks.items()
            if not t.done()
        }
        return len(cls._running_tasks)

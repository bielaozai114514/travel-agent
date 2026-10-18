"""
服务预热管理模块

提供按优先级异步预热服务的功能，包括：
- EmbeddingModel 加载
- Qdrant 连接
- 各 Agent 初始化
- 健康检查状态管理
"""

import asyncio
import threading
from typing import Dict, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from functools import wraps

from core.logger import logger


class WarmupStatus(Enum):
    """预热状态枚举"""
    PENDING = "pending"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass
class WarmupTask:
    """预热任务"""
    name: str
    priority: int  # 数字越小优先级越高
    status: WarmupStatus = WarmupStatus.PENDING
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    task_func: Optional[Callable] = None


class WarmupManager:
    """
    服务预热管理器

    按优先级异步预热各项服务，避免启动时阻塞太久
    """

    def __init__(self):
        self._tasks: Dict[str, WarmupTask] = {}
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()
        self._started = False
        self._background_tasks = set()

    def register_task(
        self,
        name: str,
        priority: int,
        task_func: Callable,
    ) -> "WarmupManager":
        """
        注册预热任务

        Args:
            name: 任务名称
            priority: 优先级（数字越小越先执行）
            task_func: 任务函数，可以是同步或异步

        Returns:
            self
        """
        with self._thread_lock:
            self._tasks[name] = WarmupTask(
                name=name,
                priority=priority,
                task_func=task_func,
            )
        return self

    async def start(self, delay_seconds: float = 0.0):
        """
        开始预热

        Args:
            delay_seconds: 延迟启动的秒数（可选）
        """
        if self._started:
            logger.warning("WarmupManager 已经启动")
            return

        self._started = True

        if delay_seconds > 0:
            logger.info(f"预热将在 {delay_seconds} 秒后开始...")
            asyncio.create_task(self._delayed_start(delay_seconds))
        else:
            await self._start_all()

    async def _delayed_start(self, delay_seconds: float):
        """延迟启动"""
        await asyncio.sleep(delay_seconds)
        await self._start_all()

    async def _start_all(self):
        """按优先级启动所有任务"""
        import time

        # 按优先级排序任务
        sorted_tasks = sorted(
            self._tasks.values(),
            key=lambda t: t.priority
        )

        # 按优先级分组执行
        current_priority = None
        current_group = []

        for task in sorted_tasks:
            if current_priority != task.priority:
                # 执行上一组任务
                if current_group:
                    await self._run_task_group(current_group)
                    current_group = []
                current_priority = task.priority
            current_group.append(task)

        # 执行最后一组任务
        if current_group:
            await self._run_task_group(current_group)

    async def _run_task_group(self, tasks: list[WarmupTask]):
        """并行执行一组任务"""
        import time

        logger.info(f"开始执行优先级 {tasks[0].priority} 的预热任务: {[t.name for t in tasks]}")

        async with asyncio.TaskGroup() as tg:
            for task in tasks:
                task.status = WarmupStatus.LOADING
                task.start_time = time.time()
                bg_task = tg.create_task(self._run_single_task(task))
                self._background_tasks.add(bg_task)
                bg_task.add_done_callback(self._background_tasks.discard)

    async def _run_single_task(self, task: WarmupTask):
        """执行单个预热任务"""
        import time

        try:
            logger.info(f"预热任务开始: {task.name}")

            # 执行任务函数
            if asyncio.iscoroutinefunction(task.task_func):
                await task.task_func()
            else:
                # 在线程池中运行同步函数
                await asyncio.to_thread(task.task_func)

            task.status = WarmupStatus.READY
            logger.info(f"预热任务完成: {task.name}")

        except Exception as e:
            task.status = WarmupStatus.FAILED
            task.error = str(e)
            logger.error(f"预热任务失败: {task.name}, 错误: {e}", exc_info=True)
        finally:
            task.end_time = time.time()

    def get_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取预热状态

        Args:
            name: 任务名称，None 则返回所有任务状态

        Returns:
            状态字典
        """
        with self._thread_lock:
            if name:
                task = self._tasks.get(name)
                if not task:
                    return {"error": f"任务不存在: {name}"}
                return {
                    "name": task.name,
                    "status": task.status.value,
                    "error": task.error,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                }
            else:
                return {
                    "overall": self._get_overall_status(),
                    "tasks": {
                        name: {
                            "status": task.status.value,
                            "error": task.error,
                            "priority": task.priority,
                        }
                        for name, task in self._tasks.items()
                    }
                }

    def _get_overall_status(self) -> str:
        """获取整体状态"""
        with self._thread_lock:
            if not self._tasks:
                return "idle"

            statuses = [t.status for t in self._tasks.values()]

            if all(s == WarmupStatus.READY for s in statuses):
                return "ready"
            if any(s == WarmupStatus.LOADING for s in statuses):
                return "loading"
            if any(s == WarmupStatus.FAILED for s in statuses):
                return "degraded"
            return "pending"

    def is_ready(self, name: Optional[str] = None) -> bool:
        """
        检查是否预热完成

        Args:
            name: 任务名称，None 则检查所有任务

        Returns:
            是否完成
        """
        with self._thread_lock:
            if name:
                task = self._tasks.get(name)
                return task is not None and task.status == WarmupStatus.READY
            else:
                return all(t.status == WarmupStatus.READY for t in self._tasks.values())


# 全局预热管理器实例
_warmup_manager: Optional[WarmupManager] = None


def get_warmup_manager() -> WarmupManager:
    """获取预热管理器单例"""
    global _warmup_manager
    if _warmup_manager is None:
        _warmup_manager = WarmupManager()
    return _warmup_manager


def setup_warmup_tasks() -> WarmupManager:
    """
    配置预热任务

    Returns:
        配置好的 WarmupManager
    """
    manager = get_warmup_manager()

    # ========== P1: 高优先级，启动后立即加载 ==========

    # 1. EmbeddingModel 预热
    def warmup_embedding_model():
        """预热嵌入模型"""
        from core.EsAgent.tools.builtin.rag.embeddings import get_embedding_model
        model = get_embedding_model()
        # 触发模型加载
        _ = model.model

    manager.register_task(
        name="embedding_model",
        priority=1,
        task_func=warmup_embedding_model,
    )

    # 2. Qdrant 连接预热
    async def warmup_qdrant():
        """预热 Qdrant 连接"""
        try:
            from core.EsAgent.tools.builtin.rag.vectorstore import QdrantVectorStore
            from settings import settings
            # 尝试创建一个临时的向量存储实例来测试连接
            # 这里不实际创建集合，只是测试连接
            logger.info("Qdrant 连接预热完成（占位）")
        except Exception as e:
            logger.warning(f"Qdrant 预热失败（可能未配置）: {e}")

    manager.register_task(
        name="qdrant",
        priority=1,
        task_func=warmup_qdrant,
    )

    # ========== P2: 中优先级，延迟加载 ==========

    # 3. 聊天 Agent 预热
    def warmup_chat_agent():
        """预热聊天 Agent"""
        from core.agent import get_esagent_service
        _ = get_esagent_service()

    manager.register_task(
        name="chat_agent",
        priority=2,
        task_func=warmup_chat_agent,
    )

    # 4. 行程规划 Agent 预热（新：初始化MCP单例）
    async def warmup_trip_planner():
        """预热行程规划相关组件"""
        from services.amap_service import get_amap_mcp_tool
        # 预热MCP工具单例（惰性初始化，第一次调用时真正启动）
        try:
            mcp_tool = get_amap_mcp_tool()
            logger.info("行程规划预热完成：MCP工具单例已准备")
        except Exception as e:
            logger.info(f"行程规划预热完成：无MCP工具（{e}）")

    manager.register_task(
        name="trip_planner_agent",
        priority=2,
        task_func=warmup_trip_planner,
    )

    # ========== P3: 低优先级，按需加载 ==========
    # MCP 工具等按需加载，不在这里预热

    return manager


async def start_warmup_with_delay():
    """
    启动预热：P1 立即执行，P2 延迟 2 秒执行
    """
    manager = setup_warmup_tasks()

    # 先启动 P1 任务
    p1_tasks = [task for task in manager._tasks.values() if task.priority == 1]
    if p1_tasks:
        await manager._run_task_group(p1_tasks)

    # 延迟 2 秒后启动 P2 任务
    async def delayed_p2():
        await asyncio.sleep(2.0)
        p2_tasks = [task for task in manager._tasks.values() if task.priority == 2]
        if p2_tasks:
            await manager._run_task_group(p2_tasks)

    asyncio.create_task(delayed_p2())

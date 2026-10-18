"""
健康检查路由

提供服务健康状态检查接口
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Optional

from core.logger import logger
from core.warmup import get_warmup_manager

router = APIRouter(prefix="/health", tags=["健康检查"])


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    overall: str
    tasks: Optional[Dict[str, Dict[str, str]]] = None
    timestamp: float


@router.get("", response_model=HealthResponse)
async def get_health():
    """
    获取服务健康状态

    返回服务整体状态和各预热任务的状态
    """
    import time

    warmup_manager = get_warmup_manager()
    warmup_status = warmup_manager.get_status()

    overall = warmup_status.get("overall", "unknown")

    # 确定整体 status
    if overall == "ready":
        status = "healthy"
    elif overall == "loading":
        status = "degraded"
    elif overall == "degraded":
        status = "degraded"
    elif overall == "pending":
        status = "degraded"
    else:
        status = "unknown"

    return HealthResponse(
        status=status,
        overall=overall,
        tasks=warmup_status.get("tasks"),
        timestamp=time.time()
    )


@router.get("/ready")
async def is_ready():
    """
    检查服务是否就绪（Kubernetes readiness probe 用）

    返回 200 表示服务已就绪
    """
    from fastapi import HTTPException

    warmup_manager = get_warmup_manager()

    # 检查核心服务是否就绪
    if warmup_manager.is_ready("embedding_model") and warmup_manager.is_ready("chat_agent"):
        return {"ready": True}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/live")
async def is_live():
    """
    检查服务是否存活（Kubernetes liveness probe 用）

    返回 200 表示服务存活
    """
    return {"live": True}

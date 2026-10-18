"""后台任务API路由"""

from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, Security, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db_session import get_db
from models.user import User
from schemas.task import TaskResponse, TaskListResponse
from curd.task import get_task_by_id, get_tasks_by_user
from core.logger import logger

router = APIRouter(prefix="/task", tags=["后台任务"])


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="获取任务详情",
    description="根据ID获取任务详情和进度"
)
async def get_task(
    task_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["tasks:read"])],
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    task = await get_task_by_id(db, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")

    return TaskResponse(
        success=True,
        message="获取成功",
        data=task.to_dict()
    )


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="获取任务列表",
    description="获取当前用户的任务列表"
)
async def list_tasks(
    current_user: Annotated[User, Security(get_current_user, scopes=["tasks:read"])],
    db: AsyncSession = Depends(get_db),
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """获取任务列表"""
    tasks, total = await get_tasks_by_user(
        db, current_user.id, task_type=task_type, status=status,
        page=page, page_size=page_size
    )

    return TaskListResponse(
        success=True,
        message="获取成功",
        data={
            "list": [t.to_dict() for t in tasks],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.post(
    "/tasks/{task_id}/cancel",
    summary="取消任务",
    description="取消正在运行的任务"
)
async def cancel_task_endpoint(
    task_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["tasks:write"])],
    db: AsyncSession = Depends(get_db)
):
    """取消任务"""
    from core.task_manager import TaskManager

    success = await TaskManager.cancel_task(db, task_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无法取消")

    return {"success": True, "message": "任务已取消"}

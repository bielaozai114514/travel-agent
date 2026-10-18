"""
Agent Trace 追踪系统 API 路由
"""

from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from core.logger import logger
from services.trace_service import trace_service


router = APIRouter(prefix="/admin/trace", tags=["Trace 追踪"])


# ============ Response Models ============

class TraceListItem(BaseModel):
    """Trace 列表项"""
    id: int
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    level: str
    name: str
    status: str
    timestamp: str
    duration_ms: Optional[float]
    agent_type: Optional[str]
    error_message: Optional[str]
    error_type: Optional[str]


class TraceListResponse(BaseModel):
    """Trace 列表响应"""
    items: List[TraceListItem]
    total: int
    page: int
    page_size: int


class TraceDetailResponse(BaseModel):
    """Trace 详情响应"""
    trace_id: str
    spans: List[Dict[str, Any]]
    tree: List[Dict[str, Any]]


class LogFileInfo(BaseModel):
    """日志文件信息"""
    filename: str
    size: int
    size_mb: float
    modified_time: str


class LogContentResponse(BaseModel):
    """日志内容响应"""
    filename: str
    lines: List[str]
    total_lines: int
    offset: int
    limit: int


class TraceStatisticsResponse(BaseModel):
    """Trace 统计响应"""
    period_days: int
    total_count: int
    success_count: int
    failed_count: int
    success_rate: float
    agent_stats: Dict[str, int]


# ============ API Endpoints ============

@router.get("/traces", response_model=TraceListResponse)
async def get_trace_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    trace_id: Optional[str] = Query(None, description="Trace ID"),
    level: Optional[str] = Query(None, description="层级: AGENT|STEP|TOOL|LLM"),
    agent_type: Optional[str] = Query(None, description="Agent 类型"),
    status: Optional[str] = Query(None, description="状态: STARTED|COMPLETED|FAILED"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO format)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO format)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
):
    """
    获取 Trace 列表

    默认只返回 AGENT 层级的记录（顶层调用）
    """
    try:
        # 解析时间
        start_dt = None
        end_dt = None
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

        traces, total = await trace_service.get_trace_list(
            page=page,
            page_size=page_size,
            trace_id=trace_id,
            level=level,
            agent_type=agent_type,
            status=status,
            start_time=start_dt,
            end_time=end_dt,
            keyword=keyword,
        )

        return TraceListResponse(
            items=traces,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"获取 Trace 列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取 Trace 列表失败")


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
async def get_trace_detail(trace_id: str):
    """
    获取单个 Trace 的完整详情（包含所有层级）
    """
    try:
        detail = await trace_service.get_trace_detail(trace_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Trace not found")
        return TraceDetailResponse(**detail)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Trace 详情失败: {e}")
        raise HTTPException(status_code=500, detail="获取 Trace 详情失败")


@router.delete("/traces/{trace_id}")
async def delete_trace(trace_id: str):
    """
    删除 Trace（级联删除所有相关 spans）
    """
    try:
        success = await trace_service.delete_trace(trace_id)
        if not success:
            raise HTTPException(status_code=404, detail="Trace not found")
        return {"success": True, "message": "Trace deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除 Trace 失败: {e}")
        raise HTTPException(status_code=500, detail="删除 Trace 失败")


@router.get("/statistics", response_model=TraceStatisticsResponse)
async def get_statistics(days: int = Query(7, ge=1, le=30, description="统计天数")):
    """
    获取 Trace 统计数据
    """
    try:
        stats = await trace_service.get_statistics(days=days)
        return TraceStatisticsResponse(**stats)

    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计数据失败")


@router.get("/logs/files", response_model=List[LogFileInfo])
async def get_log_files():
    """
    获取日志文件列表
    """
    try:
        files = trace_service.get_log_files()
        return [LogFileInfo(**f) for f in files]

    except Exception as e:
        logger.error(f"获取日志文件列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取日志文件列表失败")


@router.get("/logs/files/{filename}", response_model=LogContentResponse)
async def read_log_file(
    filename: str,
    offset: int = Query(0, ge=0, description="起始行数"),
    limit: int = Query(1000, ge=1, le=5000, description="读取行数"),
):
    """
    读取日志文件内容
    """
    try:
        content = trace_service.read_log_file(filename, offset=offset, limit=limit)
        if not content:
            raise HTTPException(status_code=404, detail="Log file not found")
        return LogContentResponse(**content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        raise HTTPException(status_code=500, detail="读取日志文件失败")

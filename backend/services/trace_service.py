"""
Trace Service - Trace 数据 CRUD 和查询服务
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import logger
from models import AsyncSessionLocal
from models.agent_trace import AgentTrace, AgentTraceDetail, TraceLevel, TraceStatus
from core.trace import Span


class TraceService:
    """Trace 服务"""

    def __init__(self):
        self.log_dir = Path("logs")

    async def save_span(self, span: Span) -> Optional[int]:
        """
        保存 Span 到数据库

        Args:
            span: Span 对象

        Returns:
            保存的记录 ID
        """
        try:
            async with AsyncSessionLocal() as session:
                # 创建主表记录
                trace_record = AgentTrace(
                    trace_id=span.trace_id,
                    span_id=span.span_id,
                    parent_span_id=span.parent_span_id,
                    level=span.level,
                    name=span.name,
                    status=span.status,
                    timestamp=span.timestamp,
                    duration_ms=int(span.duration_ms) if span.duration_ms else None,
                    agent_type=span.agent_type,
                    error_message=span.error_message,
                    error_type=span.error_type,
                    trace_metadata=span.metadata if span.metadata else None,
                )
                session.add(trace_record)
                await session.flush()

                # 创建详情记录
                trace_detail = AgentTraceDetail(
                    trace_id=span.trace_id,
                    span_id=span.span_id,
                    trace_record_id=trace_record.id,
                    full_data=span.to_dict(),
                )
                session.add(trace_detail)

                await session.commit()
                return trace_record.id

        except Exception as e:
            logger.error(f"[TraceService] 保存 Span 失败: {e}")
            return None

    async def get_trace_list(
        self,
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
        level: Optional[str] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取 Trace 列表（只返回 AGENT 层级的记录，用于列表页）

        Args:
            page: 页码
            page_size: 每页大小
            trace_id: Trace ID 筛选
            level: 层级筛选
            agent_type: Agent 类型筛选
            status: 状态筛选
            start_time: 开始时间
            end_time: 结束时间
            keyword: 关键词搜索

        Returns:
            (trace列表, 总数)
        """
        try:
            async with AsyncSessionLocal() as session:
                # 构建查询
                query = select(AgentTrace)

                # 默认只显示 AGENT 层级（顶层调用）
                if level:
                    query = query.where(AgentTrace.level == level)
                else:
                    query = query.where(AgentTrace.level == TraceLevel.AGENT)

                # 筛选条件
                if trace_id:
                    query = query.where(AgentTrace.trace_id == trace_id)
                if agent_type:
                    query = query.where(AgentTrace.agent_type == agent_type)
                if status:
                    query = query.where(AgentTrace.status == status)
                if start_time:
                    query = query.where(AgentTrace.timestamp >= start_time)
                if end_time:
                    query = query.where(AgentTrace.timestamp <= end_time)
                if keyword:
                    query = query.where(
                        or_(
                            AgentTrace.name.contains(keyword),
                            AgentTrace.trace_id.contains(keyword),
                            AgentTrace.error_message.contains(keyword),
                        )
                    )

                # 查询总数
                count_query = select(func.count()).select_from(query.subquery())
                total_result = await session.execute(count_query)
                total = total_result.scalar() or 0

                # 查询列表
                query = query.order_by(desc(AgentTrace.timestamp))
                query = query.offset((page - 1) * page_size).limit(page_size)

                result = await session.execute(query)
                traces = result.scalars().all()

                return [t.to_dict() for t in traces], total

        except Exception as e:
            logger.error(f"[TraceService] 获取 Trace 列表失败: {e}")
            return [], 0

    async def get_trace_detail(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个 Trace 的完整详情（包含所有层级）

        Args:
            trace_id: Trace ID

        Returns:
            Trace 完整详情，按树状结构组织
        """
        try:
            async with AsyncSessionLocal() as session:
                # 查询该 trace_id 的所有 spans
                query = (
                    select(AgentTrace, AgentTraceDetail)
                    .join(AgentTraceDetail, AgentTrace.id == AgentTraceDetail.trace_record_id)
                    .where(AgentTrace.trace_id == trace_id)
                    .order_by(AgentTrace.timestamp)
                )

                result = await session.execute(query)
                rows = result.all()

                if not rows:
                    return None

                # 构建完整数据
                spans = []
                for trace, detail in rows:
                    span_data = trace.to_dict(include_detail=False)
                    if detail and detail.full_data:
                        span_data["full_data"] = detail.full_data
                    spans.append(span_data)

                # 组织成树状结构
                return {
                    "trace_id": trace_id,
                    "spans": spans,
                    "tree": self._build_tree(spans),
                }

        except Exception as e:
            logger.error(f"[TraceService] 获取 Trace 详情失败: {e}")
            return None

    def _build_tree(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将 spans 组织成树状结构
        """
        span_map = {s["span_id"]: {**s, "children": []} for s in spans}
        root_spans = []

        for span in spans:
            span_id = span["span_id"]
            parent_span_id = span.get("parent_span_id")

            if parent_span_id and parent_span_id in span_map:
                span_map[parent_span_id]["children"].append(span_map[span_id])
            else:
                root_spans.append(span_map[span_id])

        return root_spans

    async def delete_trace(self, trace_id: str) -> bool:
        """
        删除 Trace（级联删除所有相关 spans）

        Args:
            trace_id: Trace ID

        Returns:
            是否删除成功
        """
        try:
            async with AsyncSessionLocal() as session:
                # 查询所有相关记录
                query = select(AgentTrace).where(AgentTrace.trace_id == trace_id)
                result = await session.execute(query)
                traces = result.scalars().all()

                for trace in traces:
                    await session.delete(trace)

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"[TraceService] 删除 Trace 失败: {e}")
            return False

    async def cleanup_old_traces(self, days: int = 7) -> int:
        """
        清理旧的 Trace 数据

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            async with AsyncSessionLocal() as session:
                # 查询需要删除的 trace_ids
                query = select(AgentTrace.trace_id).where(
                    AgentTrace.timestamp < cutoff_time
                )
                result = await session.execute(query)
                trace_ids = result.scalars().all()

                if not trace_ids:
                    return 0

                # 删除
                delete_query = select(AgentTrace).where(
                    AgentTrace.trace_id.in_(trace_ids)
                )
                delete_result = await session.execute(delete_query)
                traces = delete_result.scalars().all()

                for trace in traces:
                    await session.delete(trace)

                await session.commit()
                return len(trace_ids)

        except Exception as e:
            logger.error(f"[TraceService] 清理旧 Trace 失败: {e}")
            return 0

    def get_log_files(self) -> List[Dict[str, Any]]:
        """
        获取日志文件列表

        Returns:
            日志文件信息列表
        """
        try:
            log_files = []
            if not self.log_dir.exists():
                return log_files

            for file_path in sorted(self.log_dir.glob("*.log"), reverse=True):
                stat = file_path.stat()
                log_files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

            return log_files

        except Exception as e:
            logger.error(f"[TraceService] 获取日志文件列表失败: {e}")
            return []

    def read_log_file(self, filename: str, offset: int = 0, limit: int = 1000) -> Optional[Dict[str, Any]]:
        """
        读取日志文件内容

        Args:
            filename: 文件名
            offset: 起始行数（从 0 开始）
            limit: 读取行数

        Returns:
            日志内容
        """
        try:
            file_path = self.log_dir / filename
            if not file_path.exists():
                return None

            lines = []
            total_lines = 0

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f):
                    total_lines += 1
                    if offset <= line_num < offset + limit:
                        lines.append(line.rstrip("\n"))

            return {
                "filename": filename,
                "lines": lines,
                "total_lines": total_lines,
                "offset": offset,
                "limit": limit,
            }

        except Exception as e:
            logger.error(f"[TraceService] 读取日志文件失败: {e}")
            return None

    async def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        获取 Trace 统计数据

        Args:
            days: 统计天数

        Returns:
            统计数据
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            async with AsyncSessionLocal() as session:
                # 总调用数
                total_query = select(func.count()).where(
                    and_(
                        AgentTrace.level == TraceLevel.AGENT,
                        AgentTrace.timestamp >= cutoff_time
                    )
                )
                total_result = await session.execute(total_query)
                total_count = total_result.scalar() or 0

                # 成功数
                success_query = select(func.count()).where(
                    and_(
                        AgentTrace.level == TraceLevel.AGENT,
                        AgentTrace.status == TraceStatus.COMPLETED,
                        AgentTrace.timestamp >= cutoff_time
                    )
                )
                success_result = await session.execute(success_query)
                success_count = success_result.scalar() or 0

                # 失败数
                failed_count = total_count - success_count

                # 按 Agent 类型统计
                agent_query = (
                    select(AgentTrace.agent_type, func.count())
                    .where(
                        and_(
                            AgentTrace.level == TraceLevel.AGENT,
                            AgentTrace.agent_type.is_not(None),
                            AgentTrace.timestamp >= cutoff_time
                        )
                    )
                    .group_by(AgentTrace.agent_type)
                )
                agent_result = await session.execute(agent_query)
                agent_stats = {row[0]: row[1] for row in agent_result.all()}

                return {
                    "period_days": days,
                    "total_count": total_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "success_rate": round(success_count / total_count * 100, 2) if total_count > 0 else 0,
                    "agent_stats": agent_stats,
                }

        except Exception as e:
            logger.error(f"[TraceService] 获取统计数据失败: {e}")
            return {}


# 全局单例
trace_service = TraceService()

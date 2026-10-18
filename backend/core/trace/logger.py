"""
Trace Logger 配置
"""

from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Dict, Any

from core.logger import LoggerManager


def setup_trace_logger(
    log_dir: Optional[Path] = None,
    console_output: bool = True,
    file_output: bool = True,
):
    """
    配置 Trace Logger（可选，默认已自动配置）

    Args:
        log_dir: 日志目录
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
    """
    if log_dir:
        LoggerManager.LOG_DIR = log_dir

    # trace logger 已在 Tracer 初始化时创建
    pass


class TraceJSONFormatter:
    """Trace JSON 格式化工具"""

    @staticmethod
    def format_span_for_jsonl(span_data: Dict[str, Any]) -> str:
        """将 Span 数据格式化为 JSONL 行"""
        return json.dumps(span_data, ensure_ascii=False)

    @staticmethod
    def parse_span_from_jsonl(line: str) -> Optional[Dict[str, Any]]:
        """从 JSONL 行解析 Span 数据"""
        try:
            return json.loads(line.strip())
        except Exception:
            return None

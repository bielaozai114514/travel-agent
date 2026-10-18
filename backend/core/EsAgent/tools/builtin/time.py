from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo
from ..base import Tool, ToolParameter
from ...core.exceptions import ToolException

class TimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="time",
            description="获取当前时间",
        )

    def run(self, parameters: Optional[dict] = None) -> str:
        """获取当前时间"""
        try:
            print("正在获取当前时间(北京时间)")
            return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            error_msg = f"获取当前时间失败: {str(e)}"
            print(f"❌ {error_msg}")
            raise error_msg

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="input",
                type="string",
                description="暂时没有参数，直接获取当前时间",
                required=False
            )
        ]

# 便捷函数
def get_time() -> str:
    """
    获取当前时间

    Returns:
        当前时间字符串
    """
    tool = TimeTool()
    return tool.run()


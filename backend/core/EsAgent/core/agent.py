"""Agent基类"""

import warnings
from abc import ABC, abstractmethod
from typing import Optional, Any, List, Union
from .message import Message
from .llm import EsAgentLLM
from .config import Config


class Agent(ABC):
    """Agent基类（无状态化）"""

    def __init__(
        self,
        name: str,
        llm: EsAgentLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        # 删除内部历史存储，实现完全无状态化

    @abstractmethod
    def run(
        self,
        input_text: str,
        external_history: Optional[List[Union[Message, dict]]] = None,
        **kwargs
    ) -> str:
        """
        运行Agent

        Args:
            input_text: 用户输入
            external_history: 外部传入的历史记录，可以是Message对象列表或字典列表
            **kwargs: 其他参数

        Returns:
            Agent响应
        """
        pass

    def add_message(self, message: Message):
        """添加消息到内部历史记录（已废弃，Agent无状态化，历史由调用方管理）"""
        warnings.warn(
            "Agent无状态化，add_message已废弃，历史记录由调用方管理",
            DeprecationWarning,
            stacklevel=2
        )
        # 空实现，保持兼容性

    def clear_history(self):
        """清空内部历史记录（已废弃，Agent无状态化，历史由调用方管理）"""
        warnings.warn(
            "Agent无状态化，clear_history已废弃，历史记录由调用方管理",
            DeprecationWarning,
            stacklevel=2
        )
        # 空实现，保持兼容性

    def get_history(self) -> List[Message]:
        """获取内部历史记录（已废弃，Agent无状态化，历史由调用方管理）"""
        warnings.warn(
            "Agent无状态化，get_history已废弃，历史记录由调用方管理",
            DeprecationWarning,
            stacklevel=2
        )
        return []  # 返回空列表，保持兼容性

    def _merge_history(
        self,
        external_history: Optional[List[Union[Message, dict]]] = None
    ) -> List[dict]:
        """
        只使用外部传入的历史，Agent不存储任何状态

        Args:
            external_history: 外部传入的历史记录

        Returns:
            消息列表（字典格式）
        """
        messages = []

        if external_history:
            for msg in external_history:
                if isinstance(msg, Message):
                    messages.append(msg.to_dict())
                elif isinstance(msg, dict):
                    messages.append(msg)

        # 不再使用内部历史，Agent完全无状态
        return messages
    
    def __str__(self) -> str:
        """返回Agent的字符串表示"""
        return f"Agent(name={self.name}, provider={self.llm.provider})"
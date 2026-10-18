"""
对话上下文管理器 - 确保Agent上下文的稳定性和一致性

负责：
1. 对话历史的Token限制和智能截断
2. System Prompt的安全构建和保护
3. 行程上下文的可靠注入
4. 消息格式验证和清洗
5. 消息角色顺序校验
"""
import json
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from core.logger import logger
from schemas.llm import Message


class ContextStrategy(str, Enum):
    """上下文截断策略"""
    RECENT_FIRST = "recent_first"  # 保留最近的消息（默认）
    IMPORTANT_FIRST = "important_first"  # 保留重要消息 + 最近消息
    SUMMARY_FIRST = "summary_first"  # 旧消息摘要 + 最近消息


@dataclass
class ContextValidationResult:
    """上下文验证结果"""
    is_valid: bool
    issues: List[str]
    warnings: List[str]
    fixed_messages: Optional[List[Dict[str, str]]] = None


class ChatContextManager:
    """聊天上下文管理器"""

    # 默认Token限制（估算：1个中文汉字≈2个token，1个英文单词≈1.3个token）
    DEFAULT_MAX_TOKENS = 8000
    # 预留给System Prompt和当前输入的Token
    RESERVED_TOKENS = 1500
    # 安全边际（防止接近上限）
    SAFETY_MARGIN = 500

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        strategy: ContextStrategy = ContextStrategy.RECENT_FIRST
    ):
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.strategy = strategy
        self.effective_max_tokens = self.max_tokens - self.RESERVED_TOKENS - self.SAFETY_MARGIN

        logger.info(f"ChatContextManager初始化: max_tokens={self.max_tokens}, "
                   f"effective_max={self.effective_max_tokens}, strategy={strategy}")

    def build_safe_context(
        self,
        system_prompt: str,
        history_messages: List[Message],
        current_input: str,
        trip_context: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        构建安全的上下文（主入口）

        Args:
            system_prompt: 基础系统提示词
            history_messages: 历史消息列表
            current_input: 当前用户输入
            trip_context: 可选的行程上下文

        Returns:
            (构建好的消息列表, 元数据信息)
        """
        metadata = {
            "original_history_count": len(history_messages),
            "truncated": False,
            "trip_context_injected": bool(trip_context),
            "issues": [],
            "warnings": []
        }

        # 1. 验证和清洗历史消息
        validation = self._validate_and_clean_messages(history_messages)
        metadata["issues"].extend(validation.issues)
        metadata["warnings"].extend(validation.warnings)

        if validation.fixed_messages:
            messages_to_process = validation.fixed_messages
        else:
            messages_to_process = [
                {"role": msg.role, "content": msg.content}
                for msg in history_messages
            ]

        # 2. 构建完整的System Prompt（包含行程上下文）
        full_system_prompt = self._build_full_system_prompt(system_prompt, trip_context)

        # 3. 截断历史消息（如果需要）
        truncated_history, was_truncated = self._truncate_history(
            messages_to_process,
            full_system_prompt,
            current_input
        )
        metadata["truncated"] = was_truncated
        metadata["final_history_count"] = len(truncated_history)

        # 4. 构建最终消息列表
        final_messages = [{"role": "system", "content": full_system_prompt}]
        final_messages.extend(truncated_history)
        final_messages.append({"role": "user", "content": current_input})

        # 5. 最终验证
        final_validation = self._validate_final_context(final_messages)
        metadata["issues"].extend(final_validation.issues)
        metadata["warnings"].extend(final_validation.warnings)

        if metadata["issues"]:
            logger.warning(f"上下文构建完成，但存在问题: {metadata['issues']}")
        if metadata["warnings"]:
            logger.debug(f"上下文构建警告: {metadata['warnings']}")

        logger.info(f"上下文构建完成: 原始消息数={metadata['original_history_count']}, "
                   f"最终消息数={metadata['final_history_count'] + 2}, "
                   f"被截断={metadata['truncated']}")

        return final_messages, metadata

    def _validate_and_clean_messages(
        self,
        messages: List[Message]
    ) -> ContextValidationResult:
        """验证和清洗历史消息"""
        issues = []
        warnings = []
        cleaned_messages = []
        needs_fix = False

        last_role = None
        for i, msg in enumerate(messages):
            # 检查角色
            if msg.role not in ["user", "assistant", "system"]:
                issues.append(f"消息{i}: 无效角色 '{msg.role}'")
                needs_fix = True
                continue

            # 检查角色交替（不能连续两个相同角色）
            if msg.role == last_role and msg.role != "system":
                warnings.append(f"消息{i}: 连续 {msg.role} 消息")

            # 检查内容
            if not msg.content or not msg.content.strip():
                warnings.append(f"消息{i}: 空内容")
                needs_fix = True
                continue

            # 检查内容长度
            if len(msg.content) > 10000:
                warnings.append(f"消息{i}: 内容过长 ({len(msg.content)}字符)")

            cleaned_messages.append({
                "role": msg.role,
                "content": msg.content.strip()
            })
            last_role = msg.role

        # 检查是否以user消息开头（如果有历史）
        if cleaned_messages and cleaned_messages[0]["role"] == "assistant":
            warnings.append("历史消息以assistant开头")

        is_valid = len(issues) == 0
        return ContextValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            fixed_messages=cleaned_messages if needs_fix else None
        )

    def _build_full_system_prompt(
        self,
        base_prompt: str,
        trip_context: Optional[str]
    ) -> str:
        """构建完整的System Prompt，确保行程上下文安全注入"""
        parts = []

        # 添加行程上下文（如果有）
        if trip_context:
            # 确保行程上下文格式正确
            cleaned_trip_context = self._clean_trip_context(trip_context)
            parts.append(cleaned_trip_context)
            parts.append("")  # 空行分隔

        # 添加基础System Prompt
        parts.append(base_prompt)

        full_prompt = "\n".join(parts)

        # 验证System Prompt长度
        if len(full_prompt) > 5000:
            logger.warning(f"System Prompt过长: {len(full_prompt)}字符")

        return full_prompt

    def _clean_trip_context(self, trip_context: str) -> str:
        """清洗行程上下文，确保格式安全"""
        # 移除可能的有害字符
        cleaned = trip_context.replace("\x00", "")  # 移除空字符
        # 确保以【当前关联行程】开头
        if not cleaned.strip().startswith("【当前关联行程】"):
            cleaned = "【当前关联行程】\n" + cleaned
        return cleaned

    def _truncate_history(
        self,
        history_messages: List[Dict[str, str]],
        system_prompt: str,
        current_input: str
    ) -> Tuple[List[Dict[str, str]], bool]:
        """
        智能截断历史消息

        Returns:
            (截断后的消息列表, 是否被截断)
        """
        if not history_messages:
            return [], False

        # 估算当前Token使用量
        current_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(current_input)

        # 如果已经超出限制，只保留最近的几条消息
        if current_tokens > self.effective_max_tokens:
            logger.warning(f"System Prompt + 当前输入已接近Token限制，仅保留最近1条消息")
            return history_messages[-1:], True

        if self.strategy == ContextStrategy.RECENT_FIRST:
            return self._truncate_recent_first(
                history_messages,
                self.effective_max_tokens - current_tokens
            )
        else:
            # 默认使用recent_first策略
            return self._truncate_recent_first(
                history_messages,
                self.effective_max_tokens - current_tokens
            )

    def _truncate_recent_first(
        self,
        messages: List[Dict[str, str]],
        max_allowed_tokens: int
    ) -> Tuple[List[Dict[str, str]], bool]:
        """保留最近消息的截断策略"""
        # 从后往前累加，直到达到Token限制
        selected = []
        total_tokens = 0
        was_truncated = False

        # 倒序遍历
        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens(msg["content"])
            if total_tokens + msg_tokens > max_allowed_tokens:
                # 如果一条消息都没选，至少选最后一条
                if not selected:
                    # 截断这条消息的内容
                    truncated_content = self._truncate_content(msg["content"], max_allowed_tokens)
                    selected.append({
                        "role": msg["role"],
                        "content": truncated_content
                    })
                    was_truncated = True
                else:
                    was_truncated = True
                break
            selected.append(msg)
            total_tokens += msg_tokens

        # 恢复原始顺序
        selected.reverse()

        if was_truncated:
            logger.info(f"历史消息已截断: 保留{len(selected)}/{len(messages)}条, "
                       f"估算{total_tokens}tokens")

        return selected, was_truncated

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """截断单条消息内容"""
        # 粗略估算：中文字符数 * 2 ≈ token数
        max_chars = max_tokens // 2
        if len(content) <= max_chars:
            return content

        truncated = content[:max_chars - 10] + "...[内容已截断]"
        logger.debug(f"单条消息内容已截断: {len(content)}→{len(truncated)}字符")
        return truncated

    def _validate_final_context(self, messages: List[Dict[str, str]]) -> ContextValidationResult:
        """验证最终的上下文"""
        issues = []
        warnings = []

        # 检查基本结构
        if not messages:
            issues.append("消息列表为空")
            return ContextValidationResult(is_valid=False, issues=issues, warnings=warnings)

        # 检查第一条是system
        if messages[0]["role"] != "system":
            warnings.append("第一条消息不是system")

        # 检查最后一条是user
        if messages[-1]["role"] != "user":
            issues.append("最后一条消息不是user")

        # 检查消息数量
        if len(messages) > 50:
            warnings.append(f"消息数量较多: {len(messages)}条")

        # 估算总Token数
        total_tokens = sum(self._estimate_tokens(m["content"]) for m in messages)
        if total_tokens > self.max_tokens:
            issues.append(f"总Token数可能超限: 估算{total_tokens}tokens")

        return ContextValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=warnings
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        粗略估算Token数量

        估算规则：
        - 中文字符：每个≈2 tokens
        - 英文字符：每个≈0.3 tokens（单词≈1.3 tokens）
        - 混合文本：简化估算
        """
        if not text:
            return 0

        # 统计中文字符数
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 剩余字符数
        other_chars = len(text) - chinese_chars

        # 估算
        tokens = chinese_chars * 2 + other_chars // 3
        return max(tokens, 1)


# 全局单例
_context_manager_instance: Optional[ChatContextManager] = None


def get_context_manager(
    max_tokens: Optional[int] = None,
    strategy: ContextStrategy = ContextStrategy.RECENT_FIRST
) -> ChatContextManager:
    """获取上下文管理器单例"""
    global _context_manager_instance
    if _context_manager_instance is None:
        _context_manager_instance = ChatContextManager(max_tokens=max_tokens, strategy=strategy)
    return _context_manager_instance

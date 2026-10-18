"""
Agent稳定性增强模块

提供：
1. JSON解析容错增强
2. LLM/工具调用重试机制
3. Circuit Breaker熔断器
4. 输出格式验证
"""
import json
import re
import time
import random
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Type, Callable, Union
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from core.logger import logger


# ==================== JSON解析容错增强 ====================

class JSONParseError(Exception):
    """JSON解析失败异常"""
    pass


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    parse_method: str = "unknown"


class RobustJSONParser:
    """
    鲁棒JSON解析器

    支持多种容错策略：
    1. 标准JSON解析
    2. 提取JSON块（从```json ... ```中提取）
    3. 修复常见JSON错误
    4. 模糊匹配提取
    """

    # 常见JSON错误修复映射
    JSON_FIXES = [
        (r",\s*}", "}"),  # 移除 trailing comma
        (r",\s*]", "]"),  # 移除 trailing comma in array
        (r"(\w+)\s*:", r'"\1":'),  # 未加引号的key
        (r"'([^']+)'", r'"\1"'),  # 单引号转双引号
        (r"(\d+\.\d+)\s*([,}])", r"\1\2"),  # 确保浮点数格式
    ]

    @classmethod
    def parse(cls, text: str, schema: Optional[Dict] = None) -> ParseResult:
        """
        尝试多种方法解析JSON

        Args:
            text: 可能包含JSON的文本
            schema: 可选的schema验证（暂未实现）

        Returns:
            ParseResult
        """
        # 方法1: 直接解析
        result = cls._try_direct_parse(text)
        if result.success:
            return result

        # 方法2: 提取JSON块
        result = cls._try_extract_json_block(text)
        if result.success:
            return result

        # 方法3: 修复JSON后解析
        result = cls._try_fix_and_parse(text)
        if result.success:
            return result

        # 方法4: 模糊提取
        result = cls._try_fuzzy_extract(text)
        if result.success:
            return result

        return ParseResult(
            success=False,
            error="所有解析方法都失败",
            parse_method="all_failed"
        )

    @classmethod
    def _try_direct_parse(cls, text: str) -> ParseResult:
        """尝试直接解析"""
        try:
            data = json.loads(text.strip())
            return ParseResult(success=True, data=data, parse_method="direct")
        except json.JSONDecodeError:
            return ParseResult(success=False, parse_method="direct")

    @classmethod
    def _try_extract_json_block(cls, text: str) -> ParseResult:
        """从markdown代码块中提取JSON"""
        # 尝试 ```json ... ```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(pattern, text)

        for match in matches:
            try:
                data = json.loads(match.strip())
                return ParseResult(success=True, data=data, parse_method="json_block")
            except json.JSONDecodeError:
                continue

        # 尝试 { ... } 块
        pattern = r"\{[\s\S]*\}"
        match = re.search(pattern, text)
        if match:
            try:
                data = json.loads(match.group(0))
                return ParseResult(success=True, data=data, parse_method="json_braces")
            except json.JSONDecodeError:
                pass

        return ParseResult(success=False, parse_method="json_block")

    @classmethod
    def _try_fix_and_parse(cls, text: str) -> ParseResult:
        """尝试修复常见JSON错误后解析"""
        # 先尝试提取JSON部分
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            return ParseResult(success=False, parse_method="fix_and_parse")

        json_text = json_match.group(0)

        # 应用修复
        fixed_text = json_text
        for pattern, replacement in cls.JSON_FIXES:
            fixed_text = re.sub(pattern, replacement, fixed_text)

        try:
            data = json.loads(fixed_text)
            return ParseResult(success=True, data=data, parse_method="fix_and_parse")
        except json.JSONDecodeError:
            return ParseResult(success=False, parse_method="fix_and_parse")

    @classmethod
    def _try_fuzzy_extract(cls, text: str) -> ParseResult:
        """模糊提取关键信息（作为最后手段）"""
        try:
            # 提取常见字段
            result = {}

            # 提取 intent_type
            intent_match = re.search(r'"intent_type"\s*:\s*"([^"]+)"', text)
            if intent_match:
                result["intent_type"] = intent_match.group(1)

            # 提取 city
            city_match = re.search(r'"city"\s*:\s*"([^"]+)"', text)
            if city_match:
                result["city"] = city_match.group(1)

            # 提取 parameters
            params_match = re.search(r'"parameters"\s*:\s*(\{[\s\S]*?\})', text)
            if params_match:
                try:
                    result["parameters"] = json.loads(params_match.group(1))
                except:
                    pass

            if result:
                return ParseResult(success=True, data=result, parse_method="fuzzy_extract")

            return ParseResult(success=False, parse_method="fuzzy_extract")
        except Exception:
            return ParseResult(success=False, parse_method="fuzzy_extract")


# ==================== 重试机制 ====================

class RetryStrategy(str, Enum):
    """重试策略"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    FIXED_INTERVAL = "fixed_interval"  # 固定间隔
    LINEAR_BACKOFF = "linear_backoff"  # 线性退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # 初始延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True  # 添加随机抖动
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retry_exceptions: Tuple[Type[Exception], ...] = ()

    def calculate_delay(self, attempt: int) -> float:
        """计算第N次重试的延迟"""
        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.initial_delay * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.initial_delay * attempt
        else:  # FIXED_INTERVAL
            delay = self.initial_delay

        # 限制最大延迟
        delay = min(delay, self.max_delay)

        # 添加抖动
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


def async_retry(config: Optional[RetryConfig] = None):
    """
    异步函数重试装饰器

    Args:
        config: 重试配置，使用默认配置如果为None
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否不应该重试
                    if isinstance(e, config.non_retry_exceptions):
                        logger.warning(f"遇到不可重试异常，放弃重试: {type(e).__name__}")
                        raise

                    # 检查是否应该重试
                    if not isinstance(e, config.retry_exceptions):
                        raise

                    if attempt >= config.max_attempts:
                        logger.error(f"已达到最大重试次数 {config.max_attempts}，放弃重试")
                        break

                    delay = config.calculate_delay(attempt)
                    logger.warning(
                        f"调用 {func.__name__} 失败 (attempt {attempt}/{config.max_attempts}): "
                        f"{type(e).__name__}: {e}，{delay:.2f}秒后重试"
                    )

                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


def sync_retry(config: Optional[RetryConfig] = None):
    """
    同步函数重试装饰器
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if isinstance(e, config.non_retry_exceptions):
                        raise

                    if not isinstance(e, config.retry_exceptions):
                        raise

                    if attempt >= config.max_attempts:
                        logger.error(f"已达到最大重试次数 {config.max_attempts}，放弃重试")
                        break

                    delay = config.calculate_delay(attempt)
                    logger.warning(
                        f"调用 {func.__name__} 失败 (attempt {attempt}/{config.max_attempts}): "
                        f"{type(e).__name__}: {e}，{delay:.2f}秒后重试"
                    )

                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


# ==================== Circuit Breaker 熔断器 ====================

class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常状态，请求通过
    OPEN = "open"  # 熔断状态，请求快速失败
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 30.0  # 恢复超时（秒）
    expected_exception: Tuple[Type[Exception], ...] = (Exception,)
    success_threshold: int = 2  # 半开状态成功阈值


@dataclass
class CircuitMetrics:
    """熔断器指标"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    熔断器实现

    状态机：
    CLOSED → (失败次数超过阈值) → OPEN
    OPEN → (超过恢复超时) → HALF_OPEN
    HALF_OPEN → (成功次数达标) → CLOSED
    HALF_OPEN → (失败) → OPEN
    """

    _instances: Dict[str, 'CircuitBreaker'] = {}

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitMetrics()
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else threading.Lock()

    @classmethod
    def get_or_create(cls, name: str, config: Optional[CircuitBreakerConfig] = None) -> 'CircuitBreaker':
        """获取或创建熔断器单例"""
        if name not in cls._instances:
            cls._instances[name] = CircuitBreaker(name, config)
        return cls._instances[name]

    async def async_allow_request(self) -> bool:
        """异步检查是否允许请求"""
        async with self._lock:
            return self._check_and_transition()

    def sync_allow_request(self) -> bool:
        """同步检查是否允许请求"""
        with self._lock:
            return self._check_and_transition()

    def _check_and_transition(self) -> bool:
        """检查状态并可能转换"""
        now = datetime.now()

        if self.metrics.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if (self.metrics.last_failure_time and
                (now - self.metrics.last_failure_time).total_seconds() > self.config.recovery_timeout):
                logger.info(f"熔断器 {self.name} 进入半开状态")
                self.metrics.state = CircuitState.HALF_OPEN
                self.metrics.success_count = 0
                return True
            return False

        elif self.metrics.state == CircuitState.HALF_OPEN:
            # 半开状态允许尝试
            return True

        else:  # CLOSED
            return True

    async def async_record_success(self):
        """异步记录成功"""
        async with self._lock:
            self._record_success()

    def sync_record_success(self):
        """同步记录成功"""
        with self._lock:
            self._record_success()

    def _record_success(self):
        """记录成功（内部方法）"""
        if self.metrics.state == CircuitState.HALF_OPEN:
            self.metrics.success_count += 1
            if self.metrics.success_count >= self.config.success_threshold:
                logger.info(f"熔断器 {self.name} 恢复到关闭状态")
                self.metrics.state = CircuitState.CLOSED
                self.metrics.failure_count = 0
                self.metrics.success_count = 0
        elif self.metrics.state == CircuitState.CLOSED:
            self.metrics.failure_count = max(0, self.metrics.failure_count - 1)

    async def async_record_failure(self, exception: Optional[Exception] = None):
        """异步记录失败"""
        async with self._lock:
            self._record_failure(exception)

    def sync_record_failure(self, exception: Optional[Exception] = None):
        """同步记录失败"""
        with self._lock:
            self._record_failure(exception)

    def _record_failure(self, exception: Optional[Exception] = None):
        """记录失败（内部方法）"""
        self.metrics.failure_count += 1
        self.metrics.last_failure_time = datetime.now()

        if self.metrics.state == CircuitState.HALF_OPEN:
            logger.warning(f"熔断器 {self.name} 半开状态失败，回到打开状态")
            self.metrics.state = CircuitState.OPEN
        elif self.metrics.state == CircuitState.CLOSED:
            if self.metrics.failure_count >= self.config.failure_threshold:
                logger.warning(f"熔断器 {self.name} 打开！失败次数: {self.metrics.failure_count}")
                self.metrics.state = CircuitState.OPEN

    def get_state(self) -> CircuitState:
        """获取当前状态"""
        return self.metrics.state

    def get_metrics(self) -> Dict:
        """获取指标"""
        return {
            "state": self.metrics.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None
        }


# ==================== 便捷函数 ====================

# 默认重试配置（LLM调用）
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter=True,
    retry_exceptions=(Exception,),  # 可根据具体LLM异常调整
)

# 工具调用重试配置
TOOL_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    initial_delay=1.0,
    max_delay=10.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter=True,
)

# 默认熔断器配置
LLM_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    success_threshold=2,
)


def parse_json_safely(text: str, fallback: Optional[Any] = None) -> Tuple[bool, Any]:
    """
    安全解析JSON的便捷函数

    Args:
        text: 可能包含JSON的文本
        fallback: 解析失败时的返回值

    Returns:
        (是否成功, 解析结果或fallback)
    """
    result = RobustJSONParser.parse(text)
    if result.success:
        return True, result.data
    logger.warning(f"JSON解析失败，使用fallback。方法: {result.parse_method}, 错误: {result.error}")
    return False, fallback

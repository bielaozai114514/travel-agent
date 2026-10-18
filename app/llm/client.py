"""可插拔 LLM 客户端。

设计要点（面试可讲）：
1. 无 Key 时 available() 返回 False，上层自动降级到规则引擎，保证演示链路永远可跑；
2. 强制 JSON 输出 + 一次纠错重试，避免模型返回带 markdown 代码块导致解析失败；
3. 统一超时与重试，调用失败不抛到业务层，由 Agent 决定降级策略。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """读取项目根目录 .env（不引入额外依赖）。已存在的环境变量优先，不被覆盖。"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


class LLMUnavailable(RuntimeError):
    """未配置模型凭证时抛出，用于触发规则引擎兜底。"""


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout: float = 45.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.getenv("LLM_API_KEY", "").strip(),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
            model=os.getenv("LLM_MODEL", "deepseek-chat").strip(),
            timeout=float(os.getenv("LLM_TIMEOUT", "45")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        )


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出里抠出 JSON：优先直接解析，其次剥 markdown 代码块，最后找首尾花括号。"""
    text = text.strip()
    for candidate in (text, *[m.group(1) for m in _JSON_BLOCK.finditer(text)]):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError(f"无法从模型输出中解析 JSON：{text[:200]}")


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return bool(self.config.api_key)

    def _ensure_client(self) -> Any:
        if not self.available:
            raise LLMUnavailable("未配置 LLM_API_KEY，使用规则引擎兜底")
        if self._client is None:
            from openai import OpenAI  # 延迟导入：无 key 场景不强制安装依赖

            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        schema_hint: str = "",
    ) -> dict[str, Any]:
        """要求模型返回 JSON 对象；解析失败时追加一次纠错重试。"""
        client = self._ensure_client()
        messages = [
            {"role": "system", "content": system + ("\n\n" + schema_hint if schema_hint else "")},
            {"role": "user", "content": user},
        ]
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or ""
                return _extract_json(content)
            except Exception as exc:  # noqa: BLE001 - 网络/解析错误统一降级
                last_error = exc
                messages.append({"role": "user", "content": "上一次输出不是合法 JSON，请只输出 JSON 对象，不要任何解释。"})
                time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"LLM 调用失败：{last_error}") from last_error

    def complete_text(self, system: str, user: str, *, temperature: float = 0.5) -> str:
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()

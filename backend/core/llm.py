import json
from typing import List, AsyncGenerator, Optional, Dict, Any

from schemas.llm import Message
from core.logger import logger
from core.agent import get_esagent_service


def convert_messages(messages: List[Message]) -> List[dict]:
    service = get_esagent_service()
    return service.convert_messages(messages)


async def generate_stream(
    messages: List[Message],
    trip_plan: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[bytes, None]:
    service = get_esagent_service()
    async for chunk in service.generate_stream(messages, trip_plan=trip_plan):
        yield chunk


async def generate_non_stream(
    messages: List[Message],
    trip_plan: Optional[Dict[str, Any]] = None
) -> str:
    service = get_esagent_service()
    return await service.generate_non_stream(messages, trip_plan=trip_plan)
from fastapi import APIRouter, HTTPException, status, Depends, Security
from fastapi.responses import StreamingResponse
from fastapi.security import SecurityScopes
from typing import Annotated

from core.llm import generate_stream, generate_non_stream
from core.logger import logger
from schemas.llm import LLMRequest
from dependencies.llm import get_esagent_service_instance
from dependencies.auth import get_current_user
from models.user import User

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/")
async def llm_chat(
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])],
    messages: LLMRequest,
    esagent_service: Annotated[object, Depends(get_esagent_service_instance)],
):
    if not messages.stream:
        try:
            response = await generate_non_stream(messages.messages)
            logger.info(f"非流式生成成功")
            return {"content": response}
        except Exception as e:
            logger.error(f"非流式生成出错: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"非流式生成出错: {e}",
            )
    else:
        return StreamingResponse(
            generate_stream(messages.messages),
            media_type="text/plain",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

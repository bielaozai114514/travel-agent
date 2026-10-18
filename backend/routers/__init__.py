from fastapi import APIRouter

from routers import llm
from routers import user
from routers import role
from routers import permission
from routers import conversation
from routers import chat
from routers import trip
from routers import map
from routers import poi
from routers import guide
from routers import health
from routers import trace
from routers import task

api_router = APIRouter()

api_router.include_router(llm.router)
api_router.include_router(user.router)
api_router.include_router(role.router)
api_router.include_router(permission.router)
api_router.include_router(conversation.router)
api_router.include_router(chat.router)
api_router.include_router(trip.router)
api_router.include_router(map.router)
api_router.include_router(poi.router)
api_router.include_router(guide.router)
api_router.include_router(health.router)
api_router.include_router(trace.router)
api_router.include_router(task.router)

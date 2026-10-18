from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from models import create_table
from core.logger import logger
from core.exceptions import register_exception_handlers
from core.warmup import start_warmup_with_delay

from routers import api_router
from settings import settings


# 取代on_event的生命周期生成器 on_event在新版本被弃用
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 应用启动前的操作
    await create_table()

    # 自动初始化数据库（权限、管理员）
    import asyncio
    from utils.auto_init import auto_init_database
    asyncio.create_task(auto_init_database())

    # 设置并启动预热任务（P1 立即，P2 延迟 2 秒）
    asyncio.create_task(start_warmup_with_delay())

    logger.info("启动成功")
    yield  # 应用运行时

    # 应用关闭时


app = FastAPI(lifespan=lifespan)

# 注册全局异常处理器
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "welcome to TravelAgent"}

def app_run():
    import uvicorn
    import os

    # 根据环境决定配置
    # 开发环境使用 reload=True，单 worker
    # 生产环境建议使用多 worker（注意单例agent的问题）
    config = {
        "host": settings.BACKEND_HOST,
        "port": settings.BACKEND_PORT,
        "reload": settings.RELOAD,
        # 并发配置
        "workers": settings.WORKERS,  # 开发环境保持 生产环境可设为 CPU 核心数
        "limit_concurrency": settings.LIMIT_CONCURRENCY,  # 限制并发连接数
        "backlog": settings.BACKLOG,  # 等待连接队列大小
        # 超时配置
        "timeout_keep_alive": settings.TIMEOUT_KEEP_ALIVE,
    }

    # 如果 reload 开启，强制 workers=1
    if config["reload"]:
        config["workers"] = 1

    print(f"====================启动 FastAPI 服务，配置: {config}====================")
    uvicorn.run("main:app", **config)

if __name__ == "__main__":
    app_run()
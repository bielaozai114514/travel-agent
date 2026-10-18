from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from jwt.exceptions import PyJWTError
from typing import Dict, List, Any

from schemas.exception import ErrorResponse, ValidationErrorResponse, ValidationErrorDetail
from core.logger import logger


# 自定义业务异常（CRUD层抛这个，Router层捕获转HTTP异常）
class CRUDError(Exception):
    """CRUD操作通用异常"""

    pass


class ResourceNotFoundError(CRUDError):
    """资源不存在异常"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


class ResourceAlreadyExistsError(CRUDError):
    """资源已存在异常"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)

class PermissionDeniedError(CRUDError):
    """权限错误"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)

def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理器
    :param app: FastAPI应用实例
    """

    # 异常提示语映射表：按 请求路径前缀 → 异常类型 → 提示语配置
    EXCEPTION_DETAIL_MAP: Dict[str, Dict[str, str]] = {
        "/users/login": {
            "sql": "登录服务暂时不可用",
            "jwt": "登录令牌无效或已过期，请重新登录",
            "value": "登录参数格式错误",
            "unknown": "登录服务暂时不可用",
        },
        "/users/register": {
            "sql": "注册服务暂时不可用",
            "value": "注册参数格式错误",
            "unknown": "注册服务暂时不可用",
        },
        "/users": {
            "sql": "用户操作失败，请稍后重试",
            "value": "用户参数格式错误",
            "unknown": "用户操作失败，请稍后重试",
        },
        "/roles": {
            "sql": "角色操作失败，请稍后重试",
            "value": "角色参数格式错误",
            "unknown": "角色操作失败，请稍后重试",
        },
        "/permissions": {
            "sql": "权限操作失败，请稍后重试",
            "value": "权限参数格式错误",
            "unknown": "权限操作失败，请稍后重试",
        },
        "/chat": {
            "sql": "聊天服务暂时不可用",
            "value": "消息参数格式错误",
            "unknown": "聊天服务暂时不可用",
        },
        "/trip": {
            "sql": "行程规划服务暂时不可用",
            "value": "行程参数格式错误",
            "unknown": "行程规划服务暂时不可用",
        },
        "/guide": {
            "sql": "旅游攻略服务暂时不可用",
            "value": "攻略参数格式错误",
            "unknown": "旅游攻略服务暂时不可用",
        },
        "/task": {
            "sql": "任务服务暂时不可用",
            "value": "任务参数格式错误",
            "unknown": "任务服务暂时不可用",
        },
        "/conversation": {
            "sql": "会话服务暂时不可用",
            "value": "会话参数格式错误",
            "unknown": "会话服务暂时不可用",
        },
        "/map": {
            "sql": "地图服务暂时不可用",
            "value": "地图参数格式错误",
            "unknown": "地图服务暂时不可用",
        },
        "/poi": {
            "sql": "景点查询服务暂时不可用",
            "value": "查询参数格式错误",
            "unknown": "景点查询服务暂时不可用",
        },
    }

    def get_request_context(request: Request) -> dict:
        """获取请求上下文"""
        return {
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
        }

    def get_custom_detail(path: str, exc_type: str) -> str:
        """
        根据请求路径和异常类型获取定制化提示语
        :param path: 请求路径
        :param exc_type: 异常类型标识（sql/jwt/crud/unknown）
        :return: 定制化提示语
        """
        # 遍历映射表，匹配路径前缀
        for path_prefix, detail_map in EXCEPTION_DETAIL_MAP.items():
            if path.startswith(path_prefix):
                return detail_map.get(exc_type, "服务器内部错误，请稍后重试")

        # 默认提示语
        default_map = {
            "sql": "数据库操作失败，请稍后再试",
            "jwt": "令牌无效或已过期，请重新登录",
            "crud": "业务操作失败，请稍后再试",
            "value": "参数格式错误，请检查后重试",
            "unknown": "服务器内部错误，请稍后重试",
        }
        return default_map.get(exc_type, "服务器内部错误，请稍后重试")

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """处理参数校验/业务逻辑中的ValueError"""
        ctx = get_request_context(request)
        custom_detail = get_custom_detail(ctx["path"], "value")
        logger.error(
            f"[ValueError异常] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | error={str(exc)}"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(custom_detail if str(exc) == "" else str(exc)),
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理手动抛出的HTTP业务异常（如401/400/404）"""
        ctx = get_request_context(request)
        logger.warning(
            f"[HTTP异常] | {ctx['method']} {ctx['path']} | "
            f"status_code={exc.status_code} | detail={exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                status_code=exc.status_code,
                detail=exc.detail,
            ).model_dump(),
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """处理SQLAlchemy数据库异常"""
        ctx = get_request_context(request)
        custom_detail = get_custom_detail(ctx["path"], "sql")
        logger.error(
            f"[数据库异常] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | error={str(exc)[:200]}...",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=custom_detail,
            ).model_dump(),
        )

    @app.exception_handler(PyJWTError)
    async def jwt_exception_handler(request: Request, exc: PyJWTError):
        """处理JWT令牌异常"""
        ctx = get_request_context(request)
        custom_detail = get_custom_detail(ctx["path"], "jwt")
        logger.error(
            f"[JWT异常] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | error={str(exc)}"
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ErrorResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=custom_detail,
            ).model_dump(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(CRUDError)
    async def crud_exception_handler(request: Request, exc: CRUDError):
        """处理自定义CRUD业务异常"""
        ctx = get_request_context(request)
        custom_detail = get_custom_detail(ctx["path"], "crud")
        if isinstance(exc, ResourceNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            detail = exc.msg
        elif isinstance(exc, ResourceAlreadyExistsError):
            status_code = status.HTTP_400_BAD_REQUEST
            detail = exc.msg
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            detail = custom_detail

        logger.error(
            f"[CRUD业务异常] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | error={str(exc)}"
        )
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(status_code=status_code, detail=detail).model_dump(),
        )

    @app.exception_handler(Exception)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求参数验证错误（Pydantic/FastAPI验证失败）"""
        ctx = get_request_context(request)
        
        # 解析验证错误，提取字段级别的错误信息
        errors = []
        for error in exc.errors():
            # 提取字段路径
            field_path = ".".join(str(loc) for loc in error.get("loc", []))
            # 提取错误信息
            message = error.get("msg", "")
            # 提取输入值
            value = error.get("input", None)
            
            errors.append(
                ValidationErrorDetail(
                    field=field_path,
                    message=message,
                    value=value
                )
            )
            
        logger.warning(
            f"[参数验证错误] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | errors={len(errors)}个字段验证失败"
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ValidationErrorResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="请求参数验证失败，请检查以下字段",
                errors=errors
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """兜底异常处理器（捕获所有未匹配的异常）"""
        ctx = get_request_context(request)
        custom_detail = get_custom_detail(ctx["path"], "unknown")
        logger.critical(
            f"[未知系统异常] | {ctx['method']} {ctx['path']} | "
            f"client_ip={ctx['client_ip']} | error={str(exc)[:200]}...",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=custom_detail,
            ).model_dump(),
        )

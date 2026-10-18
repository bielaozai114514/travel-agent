"""旅游攻略API路由"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, HTTPException, Security, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db_session import get_db
from models.user import User
from schemas.guide import (
    GuideCreate, GuideUpdate, GuideReview, GuideResponse,
    GuideListResponse, GuideCommentCreate, GuideCommentUpdate,
    GuideCommentResponse, GuideSearchRequest, GuideRAGSearchRequest,
    GuideRAGSearchResponse, SuccessResponse, ErrorResponse,
    GuideToTripRequest, GuideToTripResponse, GuideGenerateRequest,
    GuideGenerateResponse
)
from schemas import PageParams
from models.guide import GuideStatus
from core.logger import logger
from curd.guide import (
    # 攻略 CRUD
    get_guide_by_id,
    get_guide_list,
    get_user_unpublished_guides,
    create_guide,
    update_guide,
    delete_guide,
    review_guide,
    increment_guide_view_count,
    increment_guide_share_count,
    # 评论 CRUD
    get_comments_by_guide,
    create_comment,
    delete_comment,
    # 点赞 CRUD
    check_like_status,
    toggle_like
)

router = APIRouter(prefix="/guides", tags=["旅游攻略"])


def build_guide_response(guide):
    """构建攻略响应，正确处理author关系"""
    author_data = None
    if guide.author is not None:
        author_data = {
            "id": str(guide.author.id),
            "username": guide.author.username
        }

    return GuideResponse(
        id=guide.id,
        title=guide.title,
        city=guide.city,
        summary=guide.summary,
        content_format=guide.content_format,
        content=guide.content,
        content_path=guide.content_path,
        tags=guide.tags,
        is_ai_generated=getattr(guide, 'is_ai_generated', False),
        author_id=guide.author_id,
        author=author_data,
        is_official=guide.is_official,
        status=guide.status,
        review_comment=guide.review_comment,
        reviewer_id=guide.reviewer_id,
        review_time=guide.review_time,
        view_count=guide.view_count,
        like_count=guide.like_count,
        comment_count=guide.comment_count,
        share_count=guide.share_count,
        create_time=guide.create_time,
        update_time=guide.update_time
    )


# ============ 攻略相关接口 ============

@router.get(
    "/my-unpublished",
    summary="获取我的未发布攻略",
    description="获取当前用户的草稿、待审核、已拒绝攻略"
)
async def get_my_unpublished_guides(
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:read"])],
    db: AsyncSession = Depends(get_db)
):
    """获取我的未发布攻略"""
    try:
        guides = await get_user_unpublished_guides(db, current_user.id)
        return {
            "success": True,
            "data": {
                "items": [build_guide_response(g) for g in guides],
                "total": len(guides)
            }
        }
    except Exception as e:
        logger.error(f"获取未发布攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "",
    response_model=GuideListResponse,
    summary="获取攻略列表",
    description="获取攻略列表，支持搜索和过滤"
)
async def list_guides(
    keyword: Annotated[Optional[str], Query(description="搜索关键词")] = None,
    city: Annotated[Optional[str], Query(description="城市过滤")] = None,
    tags: Annotated[Optional[List[str]], Query(description="标签过滤")] = None,
    is_official: Annotated[Optional[bool], Query(description="是否只看官方攻略")] = None,
    is_ai_generated: Annotated[Optional[bool], Query(description="是否只看AI生成的攻略")] = None,
    status: Annotated[Optional[str], Query(description="状态过滤，管理员不传则查看所有")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
    current_user: Annotated[Optional[User], Security(get_current_user, scopes=["guides:read"], use_cache=False)] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取攻略列表"""
    try:
        # 判断是否是管理员
        is_admin = False
        if current_user:
            is_admin = any(r.name in ["admin", "guide_admin"] for r in current_user.roles)

        # 解析 status 参数（处理空字符串）
        final_status = None
        if status and status.strip():
            try:
                final_status = GuideStatus(status)
            except ValueError:
                pass

        # 非管理员默认只看已发布的
        if not is_admin and final_status is None:
            final_status = GuideStatus.PUBLISHED

        search_params = GuideSearchRequest(
            keyword=keyword,
            city=city,
            tags=tags,
            is_official=is_official,
            is_ai_generated=is_ai_generated,
            status=final_status,
            page=page,
            page_size=page_size
        )

        guides, total = await get_guide_list(
            db,
            search_params,
            current_user_id=current_user.id if current_user else None,
            is_admin=is_admin
        )

        return GuideListResponse(
            total=total,
            items=[build_guide_response(g) for g in guides],
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"获取攻略列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{guide_id}",
    response_model=GuideResponse,
    summary="获取攻略详情",
    description="根据ID获取攻略详情，并增加浏览次数"
)
async def get_guide_detail(
    guide_id: int,
    increment_view: Annotated[bool, Query(description="是否增加浏览次数")] = True,
    current_user: Annotated[Optional[User], Security(get_current_user, scopes=["guides:read"], use_cache=False)] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取攻略详情"""
    try:
        guide = await get_guide_by_id(guide_id, db)

        # 如果是已发布的攻略，任何人都可以看；否则需要权限
        if guide.status != GuideStatus.PUBLISHED:
            if not current_user:
                raise HTTPException(status_code=401, detail="请先登录")
            if current_user.id != guide.author_id and not any(r.name in ["admin", "guide_admin"] for r in current_user.roles):
                raise HTTPException(status_code=403, detail="无权限查看该攻略")

        # 增加浏览次数
        if increment_view and guide.status == GuideStatus.PUBLISHED:
            await increment_guide_view_count(guide_id, db)
            # 重新获取以更新计数
            guide = await get_guide_by_id(guide_id, db)

        return build_guide_response(guide)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取攻略详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "",
    response_model=GuideResponse,
    summary="创建攻略",
    description="创建新的旅游攻略"
)
async def create_new_guide(
    guide_in: GuideCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """创建攻略"""
    try:
        # 检查用户是否有官方攻略权限
        is_official = any(r.name in ["admin", "guide_admin"] for r in current_user.roles)

        guide = await create_guide(guide_in, current_user.id, db, is_official=is_official)
        return build_guide_response(guide)
    except Exception as e:
        logger.error(f"创建攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{guide_id}",
    response_model=GuideResponse,
    summary="更新攻略",
    description="更新已有的攻略"
)
async def update_guide_endpoint(
    guide_id: int,
    guide_in: GuideUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """更新攻略"""
    try:
        is_admin = any(r.name in ["admin", "guide_admin"] for r in current_user.roles)
        guide = await update_guide(guide_id, guide_in, current_user.id, db, is_admin=is_admin)
        return build_guide_response(guide)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{guide_id}",
    response_model=SuccessResponse,
    summary="删除攻略",
    description="删除指定的攻略"
)
async def delete_guide_endpoint(
    guide_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """删除攻略"""
    try:
        is_admin = any(r.name in ["admin", "guide_admin"] for r in current_user.roles)
        await delete_guide(guide_id, current_user.id, db, is_admin=is_admin)
        return SuccessResponse(message="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{guide_id}/share",
    response_model=SuccessResponse,
    summary="分享攻略",
    description="记录攻略分享次数"
)
async def share_guide(
    guide_id: int,
    current_user: Annotated[Optional[User], Security(get_current_user, scopes=["guides:read"], use_cache=False)] = None,
    db: AsyncSession = Depends(get_db)
):
    """分享攻略"""
    try:
        await increment_guide_share_count(guide_id, db)
        return SuccessResponse(message="分享成功")
    except Exception as e:
        logger.error(f"分享攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 审核相关接口 ============

@router.post(
    "/{guide_id}/review",
    response_model=GuideResponse,
    summary="审核攻略",
    description="管理员审核攻略（通过/拒绝）"
)
async def review_guide_endpoint(
    guide_id: int,
    review_in: GuideReview,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:admin"])],
    db: AsyncSession = Depends(get_db)
):
    """审核攻略"""
    try:
        guide = await review_guide(guide_id, review_in, current_user.id, db)
        return build_guide_response(guide)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核攻略失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 评论相关接口 ============

@router.get(
    "/{guide_id}/comments",
    summary="获取攻略评论",
    description="获取指定攻略的评论列表"
)
async def list_comments(
    guide_id: int,
    page_num: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    current_user: Annotated[Optional[User], Security(get_current_user, scopes=["guides:read"], use_cache=False)] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取攻略评论列表"""
    try:
        page_params = PageParams(page_num=page_num, page_size=page_size)
        comments, total = await get_comments_by_guide(guide_id, db, page_params)

        return {
            "success": True,
            "data": {
                "list": [GuideCommentResponse.model_validate(c) for c in comments],
                "total": total,
                "page_num": page_num,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    except Exception as e:
        logger.error(f"获取评论列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{guide_id}/comments",
    response_model=GuideCommentResponse,
    summary="创建评论",
    description="为攻略创建评论或回复"
)
async def create_comment_endpoint(
    guide_id: int,
    comment_in: GuideCommentCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """创建评论"""
    try:
        comment = await create_comment(
            guide_id,
            comment_in.content,
            current_user.id,
            db,
            comment_in.parent_id
        )
        return GuideCommentResponse.model_validate(comment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建评论失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/comments/{comment_id}",
    response_model=SuccessResponse,
    summary="删除评论",
    description="删除指定的评论"
)
async def delete_comment_endpoint(
    comment_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """删除评论"""
    try:
        is_admin = any(r.name in ["admin", "guide_admin"] for r in current_user.roles)
        await delete_comment(comment_id, current_user.id, db, is_admin=is_admin)
        return SuccessResponse(message="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除评论失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 点赞相关接口 ============

@router.get(
    "/{guide_id}/like",
    summary="检查点赞状态",
    description="检查当前用户是否已点赞该攻略"
)
async def check_like(
    guide_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:read"])],
    db: AsyncSession = Depends(get_db)
):
    """检查点赞状态"""
    try:
        is_liked = await check_like_status(guide_id, current_user.id, db)
        return {
            "success": True,
            "data": {
                "guide_id": str(guide_id),
                "is_liked": is_liked
            }
        }
    except Exception as e:
        logger.error(f"检查点赞状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{guide_id}/like",
    summary="切换点赞状态",
    description="点赞或取消点赞攻略"
)
async def toggle_like_endpoint(
    guide_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """切换点赞状态"""
    try:
        result = await toggle_like(guide_id, current_user.id, db)
        return {
            "success": True,
            "data": {
                "guide_id": str(guide_id),
                "is_liked": result["is_liked"],
                "like_count": result["like_count"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换点赞状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ RAG 搜索接口 ============

@router.post(
    "/rag/search",
    response_model=GuideRAGSearchResponse,
    summary="RAG智能搜索",
    description="使用RAG进行旅游攻略智能搜索"
)
async def rag_search_guides(
    request: GuideRAGSearchRequest,
    current_user: Annotated[Optional[User], Security(get_current_user, scopes=["guides:read"], use_cache=False)] = None,
    db: AsyncSession = Depends(get_db)
):
    """RAG智能搜索攻略"""
    try:
        from services.guide_rag_service import search_guides_rag

        results = await search_guides_rag(
            query=request.query,
            city=request.city,
            limit=request.limit,
            min_score=request.min_score,
            use_llm_optimization=request.use_llm_optimization,
            enable_query_rewrite=request.enable_query_rewrite,
            enable_keyword_extraction=request.enable_keyword_extraction
        )

        return GuideRAGSearchResponse(
            success=True,
            message=f"找到 {len(results)} 条相关攻略",
            results=results,
            total=len(results)
        )
    except Exception as e:
        logger.error(f"RAG搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 攻略转行程接口 ============

@router.post(
    "/{guide_id}/to-trip",
    response_model=GuideToTripResponse,
    summary="攻略转行程",
    description="根据攻略内容生成旅行规划"
)
async def guide_to_trip(
    guide_id: int,
    request: GuideToTripRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])],
    db: AsyncSession = Depends(get_db)
):
    """攻略转行程"""
    from datetime import datetime
    from curd.guide import get_guide_by_id
    from core.trip_planner_agent import TripPlannerAgent
    from services.amap_service import get_amap_mcp_tool
    from schemas.trip import TripRequest
    from curd.trip_plan import create_trip_plan

    try:
        # 获取攻略
        guide = await get_guide_by_id(guide_id, db)

        # 计算旅行天数
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
        travel_days = (end_date - start_date).days + 1

        if travel_days < 1:
            raise HTTPException(status_code=400, detail="结束日期必须大于等于开始日期")

        # 构建自由文本输入，包含攻略内容
        free_text_parts = []
        free_text_parts.append(f"参考攻略：{guide.title}")
        if guide.summary:
            free_text_parts.append(f"攻略摘要：{guide.summary}")
        free_text_parts.append(f"攻略内容：{guide.content[:2000]}")  # 限制长度避免token过多

        if request.preferences:
            free_text_parts.append(f"额外要求：{', '.join(request.preferences)}")

        # 创建行程规划请求
        trip_request = TripRequest(
            city=guide.city,
            start_date=request.start_date,
            end_date=request.end_date,
            travel_days=travel_days,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=guide.tags or [],
            free_text_input="\n".join(free_text_parts)
        )

        # 调用行程规划agent（每次新建实例，使用异步方法以经过阶段式编排和 RC-LRA）
        mcp_tool = get_amap_mcp_tool()
        agent = TripPlannerAgent(mcp_tool=mcp_tool)
        trip_plan = await agent.aplan_trip(trip_request)

        # 保存到数据库
        record = await create_trip_plan(db, current_user.id, trip_plan)

        logger.info(f"攻略转行程成功: 攻略ID={guide_id}, 行程ID={record.id}")

        return GuideToTripResponse(
            success=True,
            message="行程生成成功",
            data=trip_plan.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"攻略转行程失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"行程生成失败: {str(e)}")


@router.post(
    "/generate",
    response_model=GuideGenerateResponse,
    summary="AI生成攻略",
    description="根据参数AI生成攻略草稿"
)
async def generate_guide(
    request: GuideGenerateRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["guides:write"])]
):
    """AI生成攻略"""
    import json
    from core.EsAgent import EsAgentLLM
    from settings import settings

    try:
        logger.info(f"AI生成攻略请求: city={request.city}, days={request.days}")

        # 初始化LLM
        llm = EsAgentLLM(
            model=settings.MODEL_NAME,
            api_key=settings.MODEL_API_KEY,
            base_url=settings.MODEL_BASE_URL,
            temperature=0.7
        )

        # 构建提示词
        tags_str = ", ".join(request.tags) if request.tags else "无特定要求"
        prompt = f"""请为{request.city}撰写一篇{request.days}天的旅游攻略。

预算范围：{request.budget}
风格标签：{tags_str}
额外要求：{request.extra_requirements if request.extra_requirements else "无"}

请按以下格式输出JSON：
{{
    "title": "攻略标题",
    "summary": "100-200字的攻略摘要",
    "content": "完整的攻略内容，使用Markdown格式，包含行程安排、美食推荐、住宿建议、实用贴士等部分。注意在内容末尾加上'⚠️ 本篇攻略由AI生成，仅供参考'的提示",
    "tags": ["标签1", "标签2", "标签3"]
}}

请确保内容真实实用，不要编造不存在的景点。"""

        # 调用LLM
        response = await llm.ainvoke([
            {"role": "system", "content": "你是一个专业的旅游攻略写手，擅长撰写实用、详细的旅游攻略。请用JSON格式输出，不要有其他文本。"},
            {"role": "user", "content": prompt}
        ])

        # 解析响应
        result = None
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
                result = json.loads(json_str)
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
                result = json.loads(json_str)
            else:
                # 尝试找到第一个{和最后一个}
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                result = json.loads(json_str)

        if not result:
            raise ValueError("无法解析LLM响应")

        logger.info(f"AI生成攻略成功: title={result.get('title')}")

        return GuideGenerateResponse(
            success=True,
            message="AI生成攻略成功",
            data={
                "title": result.get("title", ""),
                "city": request.city, 
                "summary": result.get("summary", ""),
                "content": result.get("content", ""),
                "tags": result.get("tags", [])
            }
        )

    except Exception as e:
        logger.error(f"AI生成攻略失败: {str(e)}", exc_info=True)
        return GuideGenerateResponse(
            success=False,
            message=f"AI生成攻略失败: {str(e)}",
            data=None
        )

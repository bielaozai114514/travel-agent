"""旅游攻略数据模型"""

from typing import List, Optional, Annotated
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_serializer

from models.guide import GuideStatus, ContentFormat


# ============ 基础模型 ============

class GuideBase(BaseModel):
    """攻略基础模型"""
    title: Annotated[str, Field(..., min_length=1, max_length=255, description="攻略标题")]
    city: Annotated[str, Field(..., min_length=1, max_length=100, description="相关城市")]
    summary: Annotated[Optional[str], Field(None, description="攻略摘要")]
    content_format: Annotated[ContentFormat, Field(default=ContentFormat.MARKDOWN, description="内容格式")]
    content: Annotated[str, Field(..., min_length=1, description="攻略内容")]
    content_path: Annotated[Optional[str], Field(None, max_length=500, description="原始文件存储路径")]
    tags: Annotated[Optional[List[str]], Field(None, description="标签数组")]
    is_ai_generated: Annotated[bool, Field(default=False, description="是否AI生成")]


class GuideCreate(GuideBase):
    """创建攻略请求"""
    status: Annotated[Optional[GuideStatus], Field(None, description="攻略状态")]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "杭州3天亲子游攻略",
                "city": "杭州",
                "summary": "带老人小孩轻松游杭州的完整攻略",
                "content_format": "markdown",
                "content": "# 杭州亲子游攻略\n\n## 第一天：西湖...",
                "tags": ["亲子", "老人友好", "轻松"],
                "status": "published"
            }
        }
    )


class GuideUpdate(BaseModel):
    """更新攻略请求"""
    title: Annotated[Optional[str], Field(None, min_length=1, max_length=255, description="攻略标题")]
    city: Annotated[Optional[str], Field(None, min_length=1, max_length=100, description="相关城市")]
    summary: Annotated[Optional[str], Field(None, description="攻略摘要")]
    content_format: Annotated[Optional[ContentFormat], Field(None, description="内容格式")]
    content: Annotated[Optional[str], Field(None, min_length=1, description="攻略内容")]
    content_path: Annotated[Optional[str], Field(None, max_length=500, description="原始文件存储路径")]
    tags: Annotated[Optional[List[str]], Field(None, description="标签数组")]
    status: Annotated[Optional[GuideStatus], Field(None, description="攻略状态")]


class GuideReview(BaseModel):
    """审核攻略请求"""
    status: Annotated[GuideStatus, Field(..., description="审核状态：published/rejected")]
    review_comment: Annotated[Optional[str], Field(None, description="审核意见")]


class GuideResponse(GuideBase):
    """攻略响应"""
    id: Annotated[int, Field(..., description="攻略ID")]
    author_id: Annotated[int, Field(..., description="作者用户ID")]
    author: Annotated[Optional[dict], Field(None, description="作者信息")]
    is_official: Annotated[bool, Field(..., description="是否官方攻略")]
    status: Annotated[GuideStatus, Field(..., description="攻略状态")]
    review_comment: Annotated[Optional[str], Field(None, description="审核意见")]
    reviewer_id: Annotated[Optional[int], Field(None, description="审核人用户ID")]
    review_time: Annotated[Optional[datetime], Field(None, description="审核时间")]
    view_count: Annotated[int, Field(..., description="浏览次数")]
    like_count: Annotated[int, Field(..., description="点赞次数")]
    comment_count: Annotated[int, Field(..., description="评论次数")]
    share_count: Annotated[int, Field(..., description="分享次数")]
    create_time: Annotated[datetime, Field(..., description="创建时间")]
    update_time: Annotated[datetime, Field(..., description="更新时间")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'author_id', 'reviewer_id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class GuideGenerateRequest(BaseModel):
    """AI生成攻略请求"""
    city: Annotated[str, Field(..., description="目的地城市")]
    days: Annotated[int, Field(2, ge=1, le=7, description="游玩天数")]
    tags: Annotated[Optional[List[str]], Field(default=[], description="标签列表")]
    budget: Annotated[Optional[str], Field(default="中等", description="预算范围")]
    extra_requirements: Annotated[Optional[str], Field(default="", description="额外要求")]


class GuideGenerateResponse(BaseModel):
    """AI生成攻略响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(..., description="消息")]
    data: Annotated[Optional[dict], Field(default=None, description="攻略数据")]


class GuideListResponse(BaseModel):
    """攻略列表响应"""
    total: Annotated[int, Field(..., description="总数")]
    items: Annotated[List[GuideResponse], Field(..., description="攻略列表")]
    page: Annotated[int, Field(..., description="当前页")]
    page_size: Annotated[int, Field(..., description="每页数量")]


# ============ 评论相关模型 ============

class GuideCommentBase(BaseModel):
    """评论基础模型"""
    content: Annotated[str, Field(..., min_length=1, description="评论内容")]


class GuideCommentCreate(GuideCommentBase):
    """创建评论请求"""
    parent_id: Annotated[Optional[int], Field(None, description="父评论ID")]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "这篇攻略写得太好了！",
                "parent_id": None
            }
        }
    )


class GuideCommentUpdate(BaseModel):
    """更新评论请求"""
    content: Annotated[str, Field(..., min_length=1, description="评论内容")]


class GuideCommentResponse(GuideCommentBase):
    """评论响应"""
    id: Annotated[int, Field(..., description="评论ID")]
    guide_id: Annotated[int, Field(..., description="关联攻略ID")]
    user_id: Annotated[int, Field(..., description="评论用户ID")]
    user_name: Annotated[Optional[str], Field(None, description="评论用户名")]
    parent_id: Annotated[Optional[int], Field(None, description="父评论ID")]
    like_count: Annotated[int, Field(..., description="点赞次数")]
    is_deleted: Annotated[bool, Field(..., description="是否删除")]
    replies: Annotated[Optional[List["GuideCommentResponse"]], Field(None, description="回复列表")]
    create_time: Annotated[datetime, Field(..., description="创建时间")]
    update_time: Annotated[datetime, Field(..., description="更新时间")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'guide_id', 'user_id', 'parent_id')
    def serialize_id(self, value: int) -> str:
        return str(value)


class GuideCommentListResponse(BaseModel):
    """评论列表响应"""
    total: Annotated[int, Field(..., description="总数")]
    items: Annotated[List[GuideCommentResponse], Field(..., description="评论列表")]
    page: Annotated[int, Field(..., description="当前页")]
    page_size: Annotated[int, Field(..., description="每页数量")]


# ============ 点赞相关模型 ============

class GuideLikeResponse(BaseModel):
    """点赞响应"""
    guide_id: Annotated[int, Field(..., description="攻略ID")]
    user_id: Annotated[int, Field(..., description="用户ID")]
    create_time: Annotated[datetime, Field(..., description="点赞时间")]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('guide_id', 'user_id')
    def serialize_id(self, value: int) -> str:
        return str(value)


# ============ 搜索相关模型 ============

class GuideSearchRequest(BaseModel):
    """攻略搜索请求"""
    keyword: Annotated[Optional[str], Field(None, description="搜索关键词")]
    city: Annotated[Optional[str], Field(None, description="城市过滤")]
    tags: Annotated[Optional[List[str]], Field(None, description="标签过滤")]
    is_official: Annotated[Optional[bool], Field(None, description="是否只看官方攻略")]
    is_ai_generated: Annotated[Optional[bool], Field(None, description="是否只看AI生成的攻略")]
    status: Annotated[Optional[GuideStatus], Field(GuideStatus.PUBLISHED, description="状态过滤")]
    page: Annotated[int, Field(1, ge=1, description="页码")]
    page_size: Annotated[int, Field(10, ge=1, le=100, description="每页数量")]


class GuideRAGSearchRequest(BaseModel):
    """RAG搜索请求（用于智能问答）"""
    query: Annotated[str, Field(..., description="用户问题")]
    city: Annotated[Optional[str], Field(None, description="城市过滤（可选，大模型会自动提取）")]
    limit: Annotated[int, Field(5, ge=1, le=20, description="返回结果数量")]
    min_score: Annotated[float, Field(0.3, ge=0.0, le=1.0, description="最小相似度")]
    use_llm_optimization: Annotated[Optional[bool], Field(None, description="是否使用LLM优化查询（覆盖settings配置）")]
    enable_query_rewrite: Annotated[Optional[bool], Field(None, description="是否启用查询重写（覆盖settings配置）")]
    enable_keyword_extraction: Annotated[Optional[bool], Field(None, description="是否启用关键词提取（覆盖settings配置）")]


class GuideRAGSearchResponse(BaseModel):
    """RAG搜索响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(..., description="消息")]
    results: Annotated[List[dict], Field(..., description="搜索结果")]
    total: Annotated[int, Field(..., description="结果总数")]


class GuideToTripRequest(BaseModel):
    """攻略转行程请求"""
    start_date: Annotated[str, Field(..., description="开始日期 YYYY-MM-DD")]
    end_date: Annotated[str, Field(..., description="结束日期 YYYY-MM-DD")]
    preferences: Annotated[Optional[List[str]], Field(default=[], description="额外偏好")]


# 导入TripPlan避免循环依赖
try:
    from schemas.trip import TripPlan
except ImportError:
    TripPlan = None


class GuideToTripResponse(BaseModel):
    """攻略转行程响应"""
    success: Annotated[bool, Field(..., description="是否成功")]
    message: Annotated[str, Field(..., description="消息")]
    data: Annotated[Optional[dict], Field(default=None, description="行程数据")]


# ============ 通用响应模型 ============

class SuccessResponse(BaseModel):
    """成功响应"""
    success: Annotated[bool, Field(default=True, description="是否成功")]
    message: Annotated[str, Field(default="操作成功", description="消息")]


class ErrorResponse(BaseModel):
    """错误响应"""
    success: Annotated[bool, Field(default=False, description="是否成功")]
    message: Annotated[str, Field(..., description="错误消息")]
    error_code: Annotated[Optional[str], Field(None, description="错误代码")]


# 更新前向引用
GuideCommentResponse.model_rebuild()

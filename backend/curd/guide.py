"""旅游攻略数据访问层"""

from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from models.guide import TravelGuide, GuideComment, GuideLike, GuideStatus, ContentFormat
from models.user import User
from core.logger import logger
from core.exceptions import ResourceNotFoundError, ResourceAlreadyExistsError, PermissionDeniedError
from schemas.guide import GuideCreate, GuideUpdate, GuideReview, GuideSearchRequest
from schemas import PageParams
from services.guide_rag_service import sync_guide_to_rag


async def get_user_unpublished_guides(
    session: AsyncSession,
    user_id: int,
    load_author: bool = True
) -> List[TravelGuide]:
    """
    获取用户的未发布攻略（草稿、待审核、已拒绝）
    :param session: 异步数据库会话
    :param user_id: 用户ID
    :param load_author: 是否预加载作者信息
    :return: 攻略列表
    """
    try:
        stmt = select(TravelGuide).where(
            and_(
                TravelGuide.author_id == user_id,
                TravelGuide.status.in_([
                    GuideStatus.DRAFT,
                    GuideStatus.PENDING,
                    GuideStatus.REJECTED
                ])
            )
        ).order_by(TravelGuide.update_time.desc())

        if load_author:
            stmt = stmt.options(selectinload(TravelGuide.author))

        result = await session.scalars(stmt)
        guides = result.all()

        logger.debug(f"查询用户 {user_id} 的未发布攻略：{len(guides)} 条")
        return guides
    except SQLAlchemyError as e:
        logger.error(f"查询用户未发布攻略失败：错误={str(e)}")
        raise


# ============ 攻略 CRUD ============

async def get_guide_by_id(
    guide_id: int,
    session: AsyncSession,
    load_author: bool = True
) -> TravelGuide:
    """
    根据ID获取攻略
    :param guide_id: 攻略ID
    :param session: 异步数据库会话
    :param load_author: 是否预加载作者信息
    :return: 攻略对象
    """
    try:
        stmt = select(TravelGuide).where(TravelGuide.id == guide_id)
        if load_author:
            stmt = stmt.options(selectinload(TravelGuide.author))

        guide = await session.scalar(stmt)

        if guide is None:
            raise ResourceNotFoundError(f"攻略ID={guide_id} 不存在")

        logger.debug(f"成功查询到攻略ID={guide_id}")
        return guide
    except SQLAlchemyError as e:
        logger.error(f"查询攻略失败（数据库异常）：攻略ID={guide_id}，错误={str(e)}")
        raise


async def get_guide_list(
    session: AsyncSession,
    search_params: GuideSearchRequest,
    load_author: bool = True,
    current_user_id: Optional[int] = None,
    is_admin: bool = False
) -> Tuple[List[TravelGuide], int]:
    """
    获取攻略列表（带搜索过滤）
    :param session: 异步数据库会话
    :param search_params: 搜索参数
    :param load_author: 是否预加载作者信息
    :param current_user_id: 当前用户ID（用于过滤自己的草稿/待审核）
    :param is_admin: 是否是管理员
    :return: 攻略列表 + 总数
    """
    try:
        # 构建基础查询
        stmt = select(TravelGuide)

        # 可见性过滤逻辑
        if not is_admin:
            # 非管理员：
            # - 可以看到所有已发布的
            # - 可以看到自己的草稿、待审核、已拒绝的
            published_condition = TravelGuide.status == GuideStatus.PUBLISHED

            if current_user_id:
                # 登录用户：可以看已发布 + 自己的其他状态
                own_condition = TravelGuide.author_id == current_user_id
                stmt = stmt.where(or_(published_condition, own_condition))
            else:
                # 未登录用户：只能看已发布的
                stmt = stmt.where(published_condition)

        # 状态过滤（如果有指定）
        if search_params.status:
            stmt = stmt.where(TravelGuide.status == search_params.status)

        # 城市过滤
        if search_params.city:
            stmt = stmt.where(TravelGuide.city == search_params.city)

        # 官方攻略过滤
        if search_params.is_official is not None:
            stmt = stmt.where(TravelGuide.is_official == search_params.is_official)

        # AI生成攻略过滤
        if search_params.is_ai_generated is not None:
            stmt = stmt.where(TravelGuide.is_ai_generated == search_params.is_ai_generated)

        # 关键词搜索
        if search_params.keyword:
            keyword = f"%{search_params.keyword}%"
            stmt = stmt.where(
                or_(
                    TravelGuide.title.like(keyword),
                    TravelGuide.summary.like(keyword),
                    TravelGuide.content.like(keyword)
                )
            )

        # 标签过滤（JSON数组包含）
        if search_params.tags and len(search_params.tags) > 0:
            for tag in search_params.tags:
                stmt = stmt.where(TravelGuide.tags.contains([tag]))

        # 查询总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await session.scalar(count_stmt)

        # 预加载作者
        if load_author:
            stmt = stmt.options(selectinload(TravelGuide.author))

        # 排序：官方攻略优先，然后按创建时间倒序
        stmt = stmt.order_by(
            TravelGuide.is_official.desc(),
            TravelGuide.create_time.desc()
        )

        # 分页
        offset = (search_params.page - 1) * search_params.page_size
        stmt = stmt.offset(offset).limit(search_params.page_size)

        # 执行查询
        result = await session.scalars(stmt)
        guides = result.all()

        logger.debug(f"查询攻略列表完成：总数={total}，当前页={search_params.page}")
        return guides, total
    except SQLAlchemyError as e:
        logger.error(f"查询攻略列表失败（数据库异常）：错误={str(e)}")
        raise


async def create_guide(
    guide_in: GuideCreate,
    author_id: int,
    session: AsyncSession,
    is_official: bool = False
) -> TravelGuide:
    """
    创建攻略
    :param guide_in: 攻略创建数据
    :param author_id: 作者用户ID
    :param session: 异步数据库会话
    :param is_official: 是否官方攻略
    :return: 创建的攻略对象
    """
    try:
        # 确定状态：
        # - 如果是草稿，保持草稿
        # - 如果是官方攻略，可以直接发布或按传入状态
        # - 普通用户尝试发布的，改为待审核
        final_status = guide_in.status
        if final_status == GuideStatus.PUBLISHED and not is_official:
            final_status = GuideStatus.PENDING
        elif final_status is None:
            final_status = GuideStatus.PENDING if is_official else GuideStatus.DRAFT

        new_guide = TravelGuide(
            title=guide_in.title,
            author_id=author_id,
            city=guide_in.city,
            summary=guide_in.summary,
            content_format=guide_in.content_format,
            content=guide_in.content,
            content_path=guide_in.content_path,
            tags=guide_in.tags,
            is_official=is_official,
            is_ai_generated=getattr(guide_in, 'is_ai_generated', False),
            status=final_status,
        )

        session.add(new_guide)
        await session.flush()
        guide_id = new_guide.id
        await session.commit()

        stmt = (
            select(TravelGuide)
            .where(TravelGuide.id == guide_id)
            .options(selectinload(TravelGuide.author))
        )
        guide = await session.scalar(stmt)


        # 如果直接发布了，同步到 RAG
        if guide.status == GuideStatus.PUBLISHED:
            try:
                await sync_guide_to_rag(guide)
            except Exception as e:
                logger.warning(f"攻略同步到 RAG 失败：{str(e)}")

        logger.info(f"成功创建攻略：ID={guide.id}，标题={guide}")
        return guide
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"创建攻略失败（数据库异常）：错误={str(e)}")
        raise


async def update_guide(
    guide_id: int,
    guide_in: GuideUpdate,
    user_id: int,
    session: AsyncSession,
    is_admin: bool = False
) -> TravelGuide:
    """
    更新攻略
    :param guide_id: 攻略ID
    :param guide_in: 更新数据
    :param user_id: 操作用户ID
    :param session: 异步数据库会话
    :param is_admin: 是否管理员可编辑任意攻略
    :return: 更新后的攻略对象
    """
    try:
        guide = await get_guide_by_id(guide_id, session)

        # 权限检查：只有作者或管理员可以更新
        if not is_admin and guide.author_id != user_id:
            raise PermissionDeniedError("无权限编辑该攻略")

        guide_data = guide_in.model_dump(exclude_unset=True)

        # 状态变更逻辑
        if "status" in guide_data and not is_admin:
            new_status = guide_data["status"]
            current_status = guide.status

            # 普通用户不能直接发布
            if new_status == GuideStatus.PUBLISHED:
                # 如果当前是已拒绝，重新提交审核
                if current_status == GuideStatus.REJECTED:
                    guide_data["status"] = GuideStatus.PENDING
                # 其他情况，也改为待审核
                else:
                    guide_data["status"] = GuideStatus.PENDING
            # 如果是草稿或待审核，保持原样
            elif new_status in [GuideStatus.DRAFT, GuideStatus.PENDING]:
                pass

        # 如果没有指定状态，但当前是待审核或已拒绝，编辑后保持待审核
        elif "status" not in guide_data and not is_admin:
            if guide.status in [GuideStatus.PENDING, GuideStatus.REJECTED]:
                guide_data["status"] = GuideStatus.PENDING

        # 检查是否从非发布状态变为发布状态
        was_published = guide.status == GuideStatus.PUBLISHED

        for key, value in guide_data.items():
            if hasattr(guide, key) and value is not None:
                setattr(guide, key, value)

        await session.commit()

        stmt = (
            select(TravelGuide)
            .where(TravelGuide.id == guide_id)
            .options(selectinload(TravelGuide.author))
        )
        guide = await session.scalar(stmt)

        # 如果变为发布状态，同步到 RAG
        if not was_published and guide.status == GuideStatus.PUBLISHED:
            try:
                await sync_guide_to_rag(guide)
            except Exception as e:
                logger.warning(f"攻略同步到 RAG 失败：{str(e)}")

        logger.info(f"成功更新攻略：ID={guide_id}")
        return guide
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"更新攻略失败（数据库异常）：攻略ID={guide_id}，错误={str(e)}")
        raise


async def delete_guide(
    guide_id: int,
    user_id: int,
    session: AsyncSession,
    is_admin: bool = False
) -> None:
    """
    删除攻略
    :param guide_id: 攻略ID
    :param user_id: 操作用户ID
    :param session: 异步数据库会话
    :param is_admin: 是否管理员
    :return: 无
    """
    try:
        guide = await get_guide_by_id(guide_id, session)

        # 权限检查
        if not is_admin and guide.author_id != user_id:
            raise PermissionDeniedError("无权限删除该攻略")

        # 先从 RAG 向量数据库中删除
        try:
            from services.guide_rag_service import remove_guide_from_rag
            await remove_guide_from_rag(guide_id)
        except Exception as rag_error:
            logger.warning(f"从 RAG 删除攻略失败，但继续删除数据库记录：{str(rag_error)}")

        await session.delete(guide)
        await session.commit()

        logger.info(f"成功删除攻略：ID={guide_id}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"删除攻略失败（数据库异常）：攻略ID={guide_id}，错误={str(e)}")
        raise


async def review_guide(
    guide_id: int,
    review_in: GuideReview,
    reviewer_id: int,
    session: AsyncSession
) -> TravelGuide:
    """
    审核攻略
    :param guide_id: 攻略ID
    :param review_in: 审核数据
    :param reviewer_id: 审核人ID
    :param session: 异步数据库会话
    :return: 审核后的攻略对象
    """
    try:
        guide = await get_guide_by_id(guide_id, session)

        guide.status = review_in.status
        guide.review_comment = review_in.review_comment
        guide.reviewer_id = reviewer_id
        guide.review_time = datetime.now()

        await session.commit()

        stmt = (
            select(TravelGuide)
            .where(TravelGuide.id == guide_id)
            .options(selectinload(TravelGuide.author))
        )
        guide = await session.scalar(stmt)

        # 如果审核通过发布，同步到 RAG
        if review_in.status == GuideStatus.PUBLISHED:
            try:
                await sync_guide_to_rag(guide)
            except Exception as e:
                logger.warning(f"攻略同步到 RAG 失败：{str(e)}")

        logger.info(f"成功审核攻略：ID={guide_id}，状态={review_in.status}")
        return guide
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"审核攻略失败（数据库异常）：攻略ID={guide_id}，错误={str(e)}")
        raise


async def increment_guide_view_count(guide_id: int, session: AsyncSession) -> None:
    """
    增加攻略浏览次数
    :param guide_id: 攻略ID
    :param session: 异步数据库会话
    """
    try:
        guide = await get_guide_by_id(guide_id, session, load_author=False)
        guide.view_count += 1
        await session.commit()
        logger.debug(f"攻略浏览次数+1：ID={guide_id}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"增加浏览次数失败：攻略ID={guide_id}，错误={str(e)}")
        raise


async def increment_guide_share_count(guide_id: int, session: AsyncSession) -> None:
    """
    增加攻略分享次数
    :param guide_id: 攻略ID
    :param session: 异步数据库会话
    """
    try:
        guide = await get_guide_by_id(guide_id, session, load_author=False)
        guide.share_count += 1
        await session.commit()
        logger.debug(f"攻略分享次数+1：ID={guide_id}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"增加分享次数失败：攻略ID={guide_id}，错误={str(e)}")
        raise


# ============ 评论 CRUD ============

async def get_comments_by_guide(
    guide_id: int,
    session: AsyncSession,
    page_params: Optional[PageParams] = None,
    load_user: bool = True
) -> Tuple[List[GuideComment], int]:
    """
    获取攻略的评论列表（只返回一级评论）
    :param guide_id: 攻略ID
    :param session: 异步数据库会话
    :param page_params: 分页参数
    :param load_user: 是否预加载用户信息
    :return: 评论列表 + 总数
    """
    try:
        # 只查询一级评论（parent_id is None）且未删除的
        stmt = select(GuideComment).where(
            and_(
                GuideComment.guide_id == guide_id,
                GuideComment.parent_id.is_(None),
                GuideComment.is_deleted == False
            )
        )

        # 查询总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await session.scalar(count_stmt)

        # 预加载用户和回复

        stmt = stmt.options(
            selectinload(GuideComment.user),
            selectinload(GuideComment.replies, recursion_depth=10).selectinload(GuideComment.user),
        )


        # 排序：按创建时间倒序
        stmt = stmt.order_by(GuideComment.create_time.desc())

        # 分页
        if page_params:
            offset = (page_params.page_num - 1) * page_params.page_size
            stmt = stmt.offset(offset).limit(page_params.page_size)

        result = await session.scalars(stmt)
        comments = result.all()

        logger.debug(f"查询攻略评论完成：总数={total}")
        return comments, total
    except SQLAlchemyError as e:
        logger.error(f"查询攻略评论失败（数据库异常）：攻略ID={guide_id}，错误={str(e)}")
        raise


async def create_comment(
    guide_id: int,
    content: str,
    user_id: int,
    session: AsyncSession,
    parent_id: Optional[int] = None
) -> GuideComment:
    """
    创建评论
    :param guide_id: 攻略ID
    :param content: 评论内容
    :param user_id: 用户ID
    :param session: 异步数据库会话
    :param parent_id: 父评论ID（回复时使用
    :return: 创建的评论对象
    """
    try:
        # 检查攻略存在
        await get_guide_by_id(guide_id, session, load_author=False)

        new_comment = GuideComment(
            guide_id=guide_id,
            user_id=user_id,
            parent_id=parent_id,
            content=content
        )

        session.add(new_comment)

        # 更新攻略评论数
        guide = await session.get(TravelGuide, guide_id)
        if guide:
            guide.comment_count += 1

        await session.flush()
        comment_id = new_comment.id
        await session.commit()

        stmt = (
            select(GuideComment)
            .where(GuideComment.id == comment_id)
            .options(
                selectinload(GuideComment.user),
                selectinload(GuideComment.replies).selectinload(GuideComment.user),
            )
        )
        comment = await session.scalar(stmt)

        logger.info(f"成功创建评论：ID={comment.id}")
        return comment
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"创建评论失败（数据库异常）：错误={str(e)}")
        raise


async def delete_comment(
    comment_id: int,
    user_id: int,
    session: AsyncSession,
    is_admin: bool = False
) -> None:
    """
    删除评论（软删除）
    :param comment_id: 评论ID
    :param user_id: 操作用户ID
    :param session: 异步数据库会话
    :param is_admin: 是否管理员
    :return: 无
    """
    try:
        stmt = select(GuideComment).where(GuideComment.id == comment_id)
        comment = await session.scalar(stmt)

        if comment is None:
            raise ResourceNotFoundError(f"评论ID={comment_id} 不存在")

        # 权限检查
        if not is_admin and comment.user_id != user_id:
            raise PermissionDeniedError("无权限删除该评论")

        # 软删除
        comment.is_deleted = True

        # 更新攻略评论数
        guide = await session.get(TravelGuide, comment.guide_id)
        if guide and guide.comment_count > 0:
            guide.comment_count -= 1

        await session.commit()

        logger.info(f"成功删除评论：ID={comment_id}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"删除评论失败（数据库异常）：评论ID={comment_id}，错误={str(e)}")
        raise


# ============ 点赞 CRUD ============

async def check_like_status(guide_id: int, user_id: int, session: AsyncSession) -> bool:
    """
    检查用户是否已点赞攻略
    :param guide_id: 攻略ID
    :param user_id: 用户ID
    :param session: 异步数据库会话
    :return: 是否已点赞
    """
    try:
        stmt = select(GuideLike).where(
            and_(GuideLike.guide_id == guide_id, GuideLike.user_id == user_id)
        )
        like = await session.scalar(stmt)
        return like is not None
    except SQLAlchemyError as e:
        logger.error(f"检查点赞状态失败：错误={str(e)}")
        raise


async def toggle_like(guide_id: int, user_id: int, session: AsyncSession) -> Dict[str, Any]:
    """
    切换点赞状态（点赞/取消点赞）
    :param guide_id: 攻略ID
    :param user_id: 用户ID
    :param session: 异步数据库会话
    :return: 操作结果（is_liked表示当前状态）
    """
    try:
        # 检查攻略存在
        await get_guide_by_id(guide_id, session, load_author=False)

        stmt = select(GuideLike).where(
            and_(GuideLike.guide_id == guide_id, GuideLike.user_id == user_id)
        )
        existing_like = await session.scalar(stmt)

        guide = await session.get(TravelGuide, guide_id)

        if existing_like:
            # 取消点赞
            await session.delete(existing_like)
            if guide and guide.like_count > 0:
                guide.like_count -= 1
            is_liked = False
            logger.info(f"用户取消点赞攻略：ID={guide_id}")
        else:
            # 点赞
            new_like = GuideLike(guide_id=guide_id, user_id=user_id)
            session.add(new_like)
            if guide:
                guide.like_count += 1
            is_liked = True
            logger.info(f"用户点赞攻略：ID={guide_id}")

        await session.commit()

        return {
            "is_liked": is_liked,
            "like_count": guide.like_count if guide else 0
        }
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"切换点赞状态失败：错误={str(e)}")
        raise

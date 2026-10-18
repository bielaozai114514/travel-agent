"""旅游攻略 RAG 服务 — 负责攻略与向量数据库的同步与搜索

业务入口: search_guides_rag() → 根据 RAG_SEARCH_MODE 分发到具体搜索策略
最终方法: M5 Adaptive TCR-RAG (RAG_SEARCH_MODE=adaptive_tcr，默认)
"""

import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.guide import TravelGuide, GuideStatus
from core.logger import logger
from core.EsAgent.tools.builtin.rag.rag_tool import RAGTool
from settings import settings
from services.rag_query_utils import (
    rewrite_query_with_llm,
    extract_keywords_with_llm,
    _clean_expired_cache,
)


# ========== RAG Tool Initialization ==========

# 全局 RAG 工具实例
_guide_rag_tool = None
_basic_rag_tool = None


def get_guide_rag_tool() -> RAGTool:
    """
    获取攻略 RAG 工具实例（单例模式）

    Returns:
        RAGTool 实例
    """
    global _guide_rag_tool

    if _guide_rag_tool is None:
        # 使用专门的 collection 存储攻略
        _guide_rag_tool = RAGTool(
            collection_name="travel_guides",
            rag_namespace="guides",
            chunk_size=800,  # 攻略可能比较长，使用稍大的分块
            chunk_overlap=100
        )
        logger.info("攻略 RAG 工具初始化成功")

    return _guide_rag_tool


def get_basic_rag_tool() -> RAGTool:
    """
    获取基础向量 RAG 工具实例（单例模式）

    仅使用 chunk.content 建立向量，不注入标题、城市、标签、章节。

    Returns:
        RAGTool 实例
    """
    global _basic_rag_tool

    if _basic_rag_tool is None:
        collection_name = settings.QDRANT_BASIC_COLLECTION_NAME
        _basic_rag_tool = RAGTool(
            collection_name=collection_name,
            rag_namespace="guides_basic",
            chunk_size=800,
            chunk_overlap=100,
        )
        logger.info(f"基础向量 RAG 工具初始化成功 (collection: {collection_name})")

    return _basic_rag_tool


# ========== RAG Index Sync ==========

async def sync_guide_to_rag(guide: TravelGuide) -> bool:
    """
    同步单个攻略到 RAG 向量数据库（TCR增强版：标题路径注入 + section_type）

    Args:
        guide: 攻略对象

    Returns:
        是否同步成功
    """
    try:
        # AI生成的攻略不进入RAG知识库
        if getattr(guide, 'is_ai_generated', False):
            logger.info(f"AI生成的攻略 {guide.id} 不同步到RAG")
            return False

        # 只同步已发布的攻略
        if guide.status != GuideStatus.PUBLISHED:
            logger.debug(f"攻略 {guide.id} 状态为 {guide.status}，不同步到 RAG")
            return False

        rag_tool = get_guide_rag_tool()

        # 构建文档内容
        doc_content = f"""# {guide.title}

城市: {guide.city}

标签: {', '.join(guide.tags) if guide.tags else '无'}

{guide.summary or ''}

{guide.content}
"""

        # 先删除旧数据
        rag_tool.delete_by_document_id_structured(f"guide_{guide.id}")

        # 使用 DocumentProcessor 直接分块（绕过 rag_tool.run，以便注入 section_type）
        from core.EsAgent.tools.builtin.rag.document_processor import DocumentProcessor
        from services.tcr_section_classifier import classify_section

        doc_processor = DocumentProcessor(chunk_size=800, chunk_overlap=100)
        base_metadata = {
            "document_id": f"guide_{guide.id}",
            "guide_id": str(guide.id),
            "title": guide.title,
            "city": guide.city,
            "author_id": str(guide.author_id),
            "is_official": guide.is_official,
            "tags": guide.tags or [],
            "source": "travel_guide"
        }
        chunks = doc_processor.process_text(text=doc_content, metadata=base_metadata)

        if not chunks:
            logger.warning(f"攻略 {guide.id} 分块结果为空")
            return False

        # 对每个 chunk：分类 section_type + 构造标题路径注入的 embed_content
        tags_str = ', '.join(guide.tags or [])
        for chunk in chunks:
            heading_path = chunk["metadata"].get("heading_path") or ""
            section_type = classify_section(heading_path, chunk["content"])
            chunk["metadata"]["section_type"] = section_type

            # 标题路径注入：将完整上下文加入 embed_content
            chunk["embed_content"] = (
                f"标题：{guide.title}\n"
                f"城市：{guide.city}\n"
                f"标签：{tags_str}\n"
                f"章节：{heading_path}\n"
                f"内容：\n{chunk['content']}"
            )

        # 向量化（用 embed_content 而非原始 content）
        vectors = rag_tool.embedding_model.encode(
            [chunk["embed_content"] for chunk in chunks],
            batch_size=32,
            show_progress_bar=False
        )

        # 写入 Qdrant（metadata 保存原始 content + section_type）
        metadata_list = []
        for chunk in chunks:
            meta = chunk["metadata"].copy()
            meta["content"] = chunk["content"]
            if settings.TCR_STORE_EMBED_CONTENT:
                meta["embed_content"] = chunk["embed_content"]
            metadata_list.append(meta)

        rag_tool.vectorstore.add_vectors(vectors=vectors, metadata=metadata_list)

        logger.info(f"攻略 {guide.id} 成功同步到 RAG（{len(chunks)} chunks, TCR增强）")
        return True

    except Exception as e:
        logger.error(f"同步攻略 {guide.id} 到 RAG 失败: {str(e)}", exc_info=True)
        return False


async def sync_guide_to_basic_rag(guide: TravelGuide) -> bool:
    """
    同步单个攻略到基础向量 collection（仅使用 chunk.content 做向量）

    metadata 保留完整字段用于评估，但 embedding 文本只使用 chunk.content。

    Args:
        guide: 攻略对象

    Returns:
        是否同步成功
    """
    try:
        if getattr(guide, 'is_ai_generated', False):
            logger.info(f"AI生成的攻略 {guide.id} 不同步到基础 RAG")
            return False

        if guide.status != GuideStatus.PUBLISHED:
            logger.debug(f"攻略 {guide.id} 状态为 {guide.status}，不同步到基础 RAG")
            return False

        rag_tool = get_basic_rag_tool()

        # 先删除旧数据
        rag_tool.delete_by_document_id_structured(f"guide_{guide.id}")

        # M0 朴素向量：纯字数分块，不做段落切分，不做 section_type 分类
        # 与 enhanced 版形成根本差异——增强版按 ## 标题语义切分，M0 按固定窗口滑动
        import re
        raw_text = guide.content or ""
        # 去掉 markdown 标题/格式符号，保留纯文本
        raw_text = re.sub(r'^#{1,3}\s+.*$', '', raw_text, flags=re.MULTILINE)
        raw_text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', raw_text)  # 去粗体/斜体
        raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)

        CHUNK_SIZE = 800
        CHUNK_OVERLAP = 100
        base_metadata = {
            "document_id": f"guide_{guide.id}",
            "guide_id": str(guide.id),
            "title": guide.title,
            "city": guide.city,
            "author_id": str(guide.author_id),
            "is_official": guide.is_official,
            "tags": guide.tags or [],
            "source": "travel_guide",
            "section_type": "",  # M0 无段落分类
            "heading_path": "",
        }

        chunks = []
        text_len = len(raw_text)
        start = 0
        chunk_idx = 0
        while start < text_len:
            end = min(start + CHUNK_SIZE, text_len)
            chunk_text = raw_text[start:end].strip()
            if chunk_text:
                meta = base_metadata.copy()
                meta["chunk_index"] = chunk_idx
                chunks.append({"content": chunk_text, "metadata": meta, "embed_content": chunk_text})
                chunk_idx += 1
            start += (CHUNK_SIZE - CHUNK_OVERLAP)

        if not chunks:
            logger.warning(f"攻略 {guide.id} 基础分块结果为空")
            return False

        # 向量化
        vectors = rag_tool.embedding_model.encode(
            [chunk["embed_content"] for chunk in chunks],
            batch_size=32,
            show_progress_bar=False,
        )
        metadata_list = []
        for chunk in chunks:
            meta = chunk["metadata"].copy()
            meta["content"] = chunk["content"]
            metadata_list.append(meta)

        rag_tool.vectorstore.add_vectors(vectors=vectors, metadata=metadata_list)

        logger.info(f"攻略 {guide.id} 成功同步到基础 RAG（{len(chunks)} chunks, 仅 content 向量化）")
        return True

    except Exception as e:
        logger.error(f"同步攻略 {guide.id} 到基础 RAG 失败: {str(e)}", exc_info=True)
        return False


async def remove_guide_from_rag(guide_id: int) -> bool:
    """
    从 RAG 向量数据库中删除攻略

    Args:
        guide_id: 攻略ID

    Returns:
        是否删除成功
    """
    try:
        rag_tool = get_guide_rag_tool()

        # 使用 RAGTool 的结构化删除方法
        success = rag_tool.delete_by_document_id_structured(f"guide_{guide_id}")

        if success:
            logger.info(f"攻略 {guide_id} 成功从 RAG 删除")
            return True
        else:
            logger.warning(f"攻略 {guide_id} 从 RAG 删除失败")
            return False

    except Exception as e:
        logger.error(f"从 RAG 删除攻略 {guide_id} 失败: {str(e)}", exc_info=True)
        return False


async def remove_guide_from_basic_rag(guide_id: int) -> bool:
    """从基础向量 RAG 中删除攻略（M0 用）"""
    try:
        rag_tool = get_basic_rag_tool()
        success = rag_tool.delete_by_document_id_structured(f"guide_{guide_id}")
        if success:
            logger.info(f"攻略 {guide_id} 成功从基础 RAG 删除")
            return True
        else:
            logger.warning(f"攻略 {guide_id} 从基础 RAG 删除失败")
            return False
    except Exception as e:
        logger.error(f"从基础 RAG 删除攻略 {guide_id} 失败: {str(e)}", exc_info=True)
        return False


async def sync_all_published_guides(db: AsyncSession) -> Dict[str, Any]:
    """
    同步所有已发布的攻略到 RAG

    Args:
        db: 数据库会话

    Returns:
        同步结果统计
    """
    try:
        # 查询所有已发布的攻略
        stmt = select(TravelGuide).where(TravelGuide.status == GuideStatus.PUBLISHED)
        result = await db.scalars(stmt)
        guides = result.all()

        logger.info(f"开始同步 {len(guides)} 篇攻略到 RAG")

        success_count = 0
        fail_count = 0

        for guide in guides:
            if await sync_guide_to_rag(guide):
                success_count += 1
            else:
                fail_count += 1

        return {
            "total": len(guides),
            "success": success_count,
            "failed": fail_count
        }

    except Exception as e:
        logger.error(f"批量同步攻略到 RAG 失败: {str(e)}", exc_info=True)
        raise


# ========== Business RAG Entry ==========

async def search_guides_rag(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    min_score: float = 0.3,
    use_llm_optimization: Optional[bool] = None,
    enable_query_rewrite: Optional[bool] = None,
    enable_keyword_extraction: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    业务 RAG 搜索入口，根据 RAG_SEARCH_MODE 分发到具体搜索策略。

    默认模式 adaptive_tcr → M5 Adaptive TCR-RAG（最终方法）

    可选模式:
        - adaptive_tcr: M5 最终方法，向量分数主导 + 轻量旅游约束校正
        - tcr: M3 TCR-RAG（全局规则重排，仅用于实验对比）
        - enhanced_vector: M1 增强索引向量检索 + 城市过滤
        - basic_vector: M0 朴素向量检索
        - llm_rag: M2 LLM-RAG（调用 LLM 做查询改写和关键词提取）
    """
    mode = settings.RAG_SEARCH_MODE

    if mode == "adaptive_tcr":
        return await search_guides_adaptive_tcr_mode(
            query=query, city=city, limit=limit,
        )

    if mode == "tcr":
        from services.tcr_rag_service import search_guides_tcr
        return await search_guides_tcr(
            query=query, city=city, limit=limit,
            min_score=min_score,
            use_llm_optimization=use_llm_optimization,
        )

    if mode == "enhanced_vector":
        return await search_guides_baseline_vector(
            query=query, city=city, limit=limit,
        )

    if mode == "basic_vector":
        return await search_guides_basic_vector(
            query=query, city=city, limit=limit,
        )

    if mode == "llm_rag":
        return await search_guides_legacy_llm_rag(
            query=query, city=city, limit=limit,
            min_score=min_score,
            use_llm_optimization=use_llm_optimization,
            enable_query_rewrite=enable_query_rewrite,
            enable_keyword_extraction=enable_keyword_extraction,
        )

    # fallback: adaptive_tcr
    logger.warning(f"未知 RAG_SEARCH_MODE={mode}，fallback 到 adaptive_tcr")
    return await search_guides_adaptive_tcr_mode(
        query=query, city=city, limit=limit,
    )


async def search_guides_legacy_llm_rag(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    min_score: float = 0.3,
    use_llm_optimization: Optional[bool] = None,
    enable_query_rewrite: Optional[bool] = None,
    enable_keyword_extraction: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    M2 LLM-RAG legacy: LLM 查询改写 + 关键词提取 + 城市过滤

    仅在 RAG_SEARCH_MODE=llm_rag 时使用，非业务默认。
    """
    try:
        _clean_expired_cache()

        use_llm = use_llm_optimization if use_llm_optimization is not None else settings.RAG_USE_LLM_OPTIMIZATION
        use_rewrite = enable_query_rewrite if enable_query_rewrite is not None else settings.RAG_QUERY_REWRITE_ENABLED
        use_keywords = enable_keyword_extraction if enable_keyword_extraction is not None else settings.RAG_KEYWORD_EXTRACTION_ENABLED

        rag_tool = get_guide_rag_tool()

        filter_conditions = None
        if city:
            filter_conditions = {"city": city}

        search_queries = [query]

        if use_llm:
            if use_rewrite:
                rewritten_query = await asyncio.to_thread(rewrite_query_with_llm, query, city)
                if rewritten_query and rewritten_query not in search_queries:
                    search_queries.append(rewritten_query)

            if use_keywords:
                keywords = await asyncio.to_thread(extract_keywords_with_llm, query, city)
                if keywords:
                    keyword_query = " ".join(keywords)
                    if keyword_query not in search_queries:
                        search_queries.append(keyword_query)

        logger.debug(f"RAG搜索查询列表: {search_queries}")

        all_results = []
        seen_chunk_ids = set()

        for search_query in search_queries:
            results = await asyncio.to_thread(
                rag_tool.search_structured,
                query=search_query,
                top_k=limit * 3,
                min_score=min_score,
                filter_conditions=filter_conditions
            )

            for result in results:
                metadata = result.get("metadata", {})
                guide_id = metadata.get("guide_id")
                score = result.get("score", 0)
                chunk_id = result.get("id")

                if score < min_score:
                    continue

                if city:
                    result_city = metadata.get("city")
                    if result_city and result_city != city:
                        continue

                dedup_key = chunk_id or guide_id
                if dedup_key and dedup_key in seen_chunk_ids:
                    continue
                if dedup_key:
                    seen_chunk_ids.add(dedup_key)

                all_results.append(result)

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_results = all_results[:limit]

        formatted_results = []
        for result in all_results:
            metadata = result.get("metadata", {})
            guide_id = metadata.get("guide_id")
            formatted_results.append({
                "id": guide_id,
                "title": metadata.get("title"),
                "city": metadata.get("city"),
                "content": result.get("content", "")[:500] if result.get("content") else metadata.get("content", "")[:500],
                "score": result.get("score", 0),
                "section_type": metadata.get("section_type", ""),
                "heading_path": metadata.get("heading_path", ""),
                "metadata": {
                    "author_id": metadata.get("author_id"),
                    "is_official": metadata.get("is_official"),
                    "tags": metadata.get("tags", []),
                    "section_type": metadata.get("section_type", ""),
                    "heading_path": metadata.get("heading_path", ""),
                    "content": (result.get("content", "") or metadata.get("content", ""))[:500],
                }
            })

        return formatted_results

    except Exception as e:
        logger.error(f"RAG 搜索攻略失败: {str(e)}", exc_info=True)
        return []


# ========== Context Builder ==========

def build_rag_context_for_agent(
    query: str,
    search_results: List[Dict[str, Any]],
    max_length: int = 3000
) -> str:
    """
    构建用于 Agent 的 RAG 上下文

    Args:
        query: 用户问题
        search_results: RAG 搜索结果
        max_length: 最大长度

    Returns:
        格式化的上下文字符串
    """
    if not search_results:
        return ""

    # section_type 中文标签映射
    section_labels = {
        "attraction": "景点信息",
        "route": "行程路线",
        "food": "美食推荐",
        "hotel": "住宿建议",
        "transport": "交通指南",
        "tip": "避坑提醒",
        "weather": "天气提示",
        "budget": "预算参考",
    }

    context_parts = ["以下是相关的旅游攻略参考：\n"]

    current_length = len(context_parts[0])

    for i, result in enumerate(search_results, 1):
        content = result.get("content", "")
        # 修复 bug：从 result 顶层取 title 和 city，回退到 metadata 内层
        title = result.get("title") or result.get("metadata", {}).get("title", f"攻略{i}")
        city = result.get("city") or result.get("metadata", {}).get("city", "")
        section_type = result.get("section_type") or result.get("metadata", {}).get("section_type", "")
        heading_path = result.get("heading_path") or result.get("metadata", {}).get("heading_path", "")

        section_label = section_labels.get(section_type, "")

        entry = f"\n## {title}\n"
        if city:
            entry += f"城市: {city}\n"
        if section_label:
            entry += f"[{section_label}]\n"
        if heading_path:
            entry += f"章节: {heading_path}\n"
        entry += f"{content}\n"

        # 检查长度
        if current_length + len(entry) > max_length:
            break

        context_parts.append(entry)
        current_length += len(entry)

    return "".join(context_parts)


# ========== Experiment Search Modes (kept for paper comparison) ==========

async def search_guides_basic_vector(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    M0 Basic: 朴素向量检索

    仅使用 chunk.content 构建向量，不注入标题/城市/标签/章节，
    检索时不使用城市过滤、查询改写或规则重排序。
    city 参数仅用于评估上下文兼容，不参与过滤或加分。
    """
    rag_tool = get_basic_rag_tool()

    results = await asyncio.to_thread(
        rag_tool.search_structured,
        query=query,
        top_k=limit,
        min_score=0.3,
        filter_conditions=None,  # 不使用城市过滤
    )

    formatted = []
    for result in results:
        metadata = result.get("metadata", {})
        formatted.append({
            "id": metadata.get("guide_id"),
            "title": metadata.get("title"),
            "city": metadata.get("city"),
            "content": (result.get("content") or metadata.get("content", ""))[:500],
            "score": result.get("score", 0),
            "section_type": metadata.get("section_type", ""),
            "heading_path": metadata.get("heading_path", ""),
            "metadata": {
                "tags": metadata.get("tags", []),
                "is_official": metadata.get("is_official", False),
                "section_type": metadata.get("section_type", ""),
                "heading_path": metadata.get("heading_path", ""),
                "content": (result.get("content") or metadata.get("content", ""))[:500],
            }
        })
    return formatted


async def search_guides_baseline_vector(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    M1 Enhanced: 增强索引向量检索 + 城市过滤（无LLM、无重排序）

    用于论文实验对比
    """
    rag_tool = get_guide_rag_tool()
    filter_conditions = {"city": city} if city else None

    results = await asyncio.to_thread(
        rag_tool.search_structured,
        query=query,
        top_k=limit,
        min_score=0.3,
        filter_conditions=filter_conditions
    )

    formatted = []
    for result in results:
        metadata = result.get("metadata", {})
        formatted.append({
            "id": metadata.get("guide_id"),
            "title": metadata.get("title"),
            "city": metadata.get("city"),
            "content": (result.get("content") or metadata.get("content", ""))[:500],
            "score": result.get("score", 0),
            "section_type": metadata.get("section_type", ""),
            "heading_path": metadata.get("heading_path", ""),
            "metadata": {
                "tags": metadata.get("tags", []),
                "is_official": metadata.get("is_official", False),
                "section_type": metadata.get("section_type", ""),
                "heading_path": metadata.get("heading_path", ""),
                "content": (result.get("content") or metadata.get("content", ""))[:500],
            }
        })
    return formatted


async def search_guides_baseline_vector_no_city_filter(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """M1-no-city: 增强索引向量检索，不启用城市过滤。

    用于消融实验——测量向量富化在无城市过滤条件下的独立贡献。
    与 search_guides_baseline_vector 的唯一区别是 filter_conditions=None。
    """
    rag_tool = get_guide_rag_tool()

    results = await asyncio.to_thread(
        rag_tool.search_structured,
        query=query,
        top_k=limit,
        min_score=0.3,
        filter_conditions=None,
    )

    formatted = []
    for result in results:
        metadata = result.get("metadata", {})
        formatted.append({
            "id": metadata.get("guide_id"),
            "title": metadata.get("title"),
            "city": metadata.get("city"),
            "content": (result.get("content") or metadata.get("content", ""))[:500],
            "score": result.get("score", 0),
            "section_type": metadata.get("section_type", ""),
            "heading_path": metadata.get("heading_path", ""),
            "metadata": {
                "tags": metadata.get("tags", []),
                "is_official": metadata.get("is_official", False),
                "section_type": metadata.get("section_type", ""),
                "heading_path": metadata.get("heading_path", ""),
                "content": (result.get("content") or metadata.get("content", ""))[:500],
            }
        })
    return formatted


async def search_guides_current_rag(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    M2 LLM-RAG: 多查询 + LLM重写 + 关键词提取 + 城市过滤（无重排序）

    Kept for experiment comparison only. Not used in business RAG.
    """
    return await search_guides_legacy_llm_rag(
        query=query, city=city, limit=limit,
        min_score=0.3,
        use_llm_optimization=True,
        enable_query_rewrite=True,
        enable_keyword_extraction=True,
    )


async def search_guides_tcr_mode(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """M3 TCR-RAG ablation: global rule-based tourism scoring. Kept for experiment comparison only."""
    from services.tcr_rag_service import search_guides_tcr
    old_reranker = settings.TCR_RERANKER_ENABLED
    try:
        settings.TCR_RERANKER_ENABLED = False
        return await search_guides_tcr(query=query, city=city, limit=limit, use_llm_optimization=False)
    finally:
        settings.TCR_RERANKER_ENABLED = old_reranker


async def search_guides_tcr_rerank_mode(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """M3+Reranker: TCR-RAG + Reranker. Requires reranker model, not used in current paper experiments."""
    from services.tcr_rag_service import search_guides_tcr
    old_reranker = settings.TCR_RERANKER_ENABLED
    try:
        settings.TCR_RERANKER_ENABLED = True
        return await search_guides_tcr(query=query, city=city, limit=limit, use_llm_optimization=False)
    finally:
        settings.TCR_RERANKER_ENABLED = old_reranker


async def search_guides_tcr_tuned_mode(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    intent_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """M4 TCR-Tuned ablation: guide-level aggregation on TCR candidates. Kept for experiment comparison only."""
    from services.rag_tuned_ranker import tuned_rank

    # 获取更多候选以支持 guide 聚合
    candidate_limit = max(limit * 6, 30)
    candidates = await search_guides_tcr_mode(query=query, city=city, limit=candidate_limit)
    return tuned_rank(
        candidates=candidates,
        query=query,
        city=city or "",
        intent_type=intent_type,
        limit=limit,
    )


# ========== Final M5 Adaptive Mode ==========

async def search_guides_adaptive_tcr_mode(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    intent_type: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    M3 Adaptive TCR-RAG: vector-score-dominant adaptive tourism constraint ranking.

    Candidates from M1 no-city-filter variant; applies lightweight feature correction
    (city, title, tag, keyword, section) while keeping vector score dominant.
    city_mismatch_penalty (-0.20) is now active since candidates span multiple cities.
    Does not call LLM.
    """
    from services.adaptive_tcr_ranker import is_top1_confident, adaptive_rank

    candidate_limit = max(limit * 6, 30)
    # 无城市过滤候选池 → city_mismatch_penalty 真正生效
    candidates = await search_guides_baseline_vector_no_city_filter(
        query=query,
        city=city,
        limit=candidate_limit,
    )

    if not candidates:
        return []

    # ====== RAG 结果日志（调试用，INFO 级别） ======
    logger.info(f"[RAG-M5] 候选池共 {len(candidates)} 条，城市过滤: {city}")
    for i, c in enumerate(candidates[:limit]):
        meta = c.get("metadata", {})
        logger.info(
            f"[RAG-M5] 候选#{i+1} | score={c.get('score', 0):.4f} | "
            f"title={meta.get('title', '?')} | "
            f"section={meta.get('section_type', '?')} | "
            f"content_preview={(c.get('content') or meta.get('content', ''))[:120]}"
        )

    if is_top1_confident(candidates, query, city or "", intent_type):
        # Top1 置信度高，保留原排序，补充标记
        results = candidates[:limit]
        for r in results:
            r["adaptive_reranked"] = False
            r["method_stage"] = "m1_kept"
            r["adaptive_score"] = round(r.get("score", 0), 4)
            r["vector_score"] = round(r.get("score", 0), 4)
        logger.info(f"[RAG-M5] top1 置信度高，保留 M1 原排序，最终返回 {len(results)} 条")
        return results

    # Top1 置信度低，触发自适应重排
    reranked = adaptive_rank(
        candidates=candidates,
        query=query,
        city=city or "",
        intent_type=intent_type,
        limit=limit,
    )
    logger.info(f"[RAG-M5] 触发自适应重排，最终返回 {len(reranked)} 条")
    for i, r in enumerate(reranked):
        meta = r.get("metadata", {})
        logger.info(
            f"[RAG-M5] 最终#{i+1} | adaptive_score={r.get('adaptive_score', 0):.4f} | "
            f"title={meta.get('title', '?')} | "
            f"section={meta.get('section_type', '?')}"
        )
    return reranked


async def search_guides_adaptive_tcr_v2_mode(
    query: str,
    city: Optional[str] = None,
    limit: int = 5,
    intent_type: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    M5-v2 ablation: relaxed confidence threshold + score-first-then-dedup.
    v2 is for ablation only, not used in production/business RAG.
    """
    from services.adaptive_tcr_ranker import is_top1_confident_v2, adaptive_rank_v2

    candidate_limit = max(limit * 6, 30)
    candidates = await search_guides_baseline_vector(
        query=query,
        city=city,
        limit=candidate_limit,
    )

    if not candidates:
        return []

    if is_top1_confident_v2(candidates, query, city or "", intent_type):
        # Top1 置信度高，保留原排序，补充标记
        results = candidates[:limit]
        for r in results:
            r["adaptive_reranked"] = False
            r["method_stage"] = "m1_kept"
            r["adaptive_score"] = round(r.get("score", 0), 4)
            r["vector_score"] = round(r.get("score", 0), 4)
        return results

    # Top1 置信度低，触发 v2 自适应重排
    return adaptive_rank_v2(
        candidates=candidates,
        query=query,
        city=city or "",
        intent_type=intent_type,
        limit=limit,
    )

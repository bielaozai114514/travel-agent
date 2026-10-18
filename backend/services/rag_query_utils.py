"""RAG查询工具函数 - 从guide_rag_service中拆分，供TCR-RAG和旧RAG共用"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from core.logger import logger
from core.EsAgent import EsAgentLLM
from settings import settings


# 查询缓存: {query_hash: (result, expire_time)}
_query_cache: Dict[str, Tuple[Any, datetime]] = {}


def _get_llm_for_rag() -> EsAgentLLM:
    """获取用于RAG查询优化的LLM实例"""
    return EsAgentLLM(
        model=settings.MODEL_NAME,
        api_key=settings.MODEL_API_KEY,
        base_url=settings.MODEL_BASE_URL,
        temperature=settings.RAG_LLM_TEMPERATURE,
        timeout=60,
    )


def _get_query_hash(query: str, city: Optional[str] = None, optimization_type: str = "raw") -> str:
    """生成查询的缓存key"""
    content = f"{query}:{city or ''}:{optimization_type}"
    return hashlib.md5(content.encode()).hexdigest()


def _get_cache(query_hash: str) -> Optional[Any]:
    """从缓存获取结果"""
    if not settings.RAG_CACHE_ENABLED:
        return None

    cached = _query_cache.get(query_hash)
    if cached:
        result, expire_time = cached
        if datetime.now() < expire_time:
            logger.debug(f"缓存命中: {query_hash[:16]}...")
            return result
        else:
            del _query_cache[query_hash]
    return None


def _set_cache(query_hash: str, result: Any):
    """设置缓存"""
    if not settings.RAG_CACHE_ENABLED:
        return

    expire_time = datetime.now() + timedelta(seconds=settings.RAG_CACHE_TTL_SECONDS)
    _query_cache[query_hash] = (result, expire_time)
    logger.debug(f"缓存已设置: {query_hash[:16]}..., 过期时间: {expire_time}")


def _clean_expired_cache():
    """清理过期缓存"""
    now = datetime.now()
    expired_keys = [k for k, (_, exp) in _query_cache.items() if exp < now]
    for k in expired_keys:
        del _query_cache[k]
    if expired_keys:
        logger.debug(f"清理了 {len(expired_keys)} 个过期缓存")


def rewrite_query_with_llm(query: str, city: Optional[str] = None) -> str:
    """
    使用LLM重写查询，使其更适合向量搜索

    Args:
        query: 原始用户查询
        city: 可选的城市限制

    Returns:
        优化后的查询字符串
    """
    cache_key = _get_query_hash(query, city, "rewrite")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        llm = _get_llm_for_rag()

        prompt = f"""你是一个旅游攻略搜索专家。请将用户的自然语言查询重写成一个更适合向量数据库搜索的查询字符串。

要求：
1. 保留所有关键信息（目的地、时间、活动类型等）
2. 使用更正式、更精确的表达
3. 添加相关的旅游词汇
4. 输出只需重写后的查询，不要有其他解释

原始查询：{query}
{('目的地城市：' + city) if city else ''}

重写后的查询："""

        result = llm.invoke([{"role": "user", "content": prompt}])
        result = result.strip()

        logger.debug(f"查询重写: '{query}' -> '{result}'")
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"查询重写失败，使用原始查询: {e}")
        return query


def extract_keywords_with_llm(query: str, city: Optional[str] = None) -> List[str]:
    """
    使用LLM提取查询中的关键词

    Args:
        query: 原始用户查询
        city: 可选的城市限制

    Returns:
        关键词列表
    """
    cache_key = _get_query_hash(query, city, "keywords")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        llm = _get_llm_for_rag()

        prompt = f"""你是一个旅游关键词提取专家。请从用户查询中提取最关键的搜索词。

要求：
1. 提取5-10个关键词
2. 包含：目的地、景点类型、活动、季节等
3. 只返回JSON数组，不要其他内容

查询：{query}
{('城市：' + city) if city else ''}

输出格式：["关键词1", "关键词2", ...]"""

        result = llm.invoke([{"role": "user", "content": prompt}])
        result = result.strip()

        # 尝试解析JSON
        try:
            if "```json" in result:
                json_start = result.find("```json") + 7
                json_end = result.find("```", json_start)
                result = result[json_start:json_end].strip()
            elif "```" in result:
                json_start = result.find("```") + 3
                json_end = result.find("```", json_start)
                result = result[json_start:json_end].strip()

            keywords = json.loads(result)
            if isinstance(keywords, list):
                logger.debug(f"关键词提取: '{query}' -> {keywords}")
                _set_cache(cache_key, keywords)
                return keywords
        except Exception:
            pass

        # 备用方案：简单分割
        keywords = [k.strip() for k in result.replace('"', "").replace("[", "").replace("]", "").split(",") if k.strip()]
        logger.debug(f"关键词提取(备用): '{query}' -> {keywords}")
        _set_cache(cache_key, keywords)
        return keywords

    except Exception as e:
        logger.warning(f"关键词提取失败: {e}")
        return [query]

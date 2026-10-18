"""旅游攻略搜索工具 - 供Agent使用的RAG搜索工具"""

from typing import List, Optional, Dict, Any
import asyncio
import threading
import re

from ..base import Tool, ToolParameter
from ...core.exceptions import ToolException
from core.logger import logger

# 全局引用，避免循环导入
_guide_rag_service = None

# 常见城市列表（用于从查询中提取城市）
COMMON_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "武汉", "西安", "南京",
    "天津", "苏州", "厦门", "青岛", "大连", "昆明", "长沙", "郑州", "济南", "沈阳",
    "哈尔滨", "长春", "石家庄", "太原", "合肥", "福州", "南昌", "南宁", "海口", "贵阳",
    "兰州", "银川", "西宁", "乌鲁木齐", "拉萨", "呼和浩特", "无锡", "常州", "宁波", "温州"
]


def _extract_city_from_query(query: str) -> Optional[str]:
    """
    从查询中尝试提取城市名

    Args:
        query: 用户查询

    Returns:
        提取到的城市名，或None
    """
    # 先检查常见城市
    for city in COMMON_CITIES:
        if city in query:
            return city

    # 尝试匹配"XX市"、"XX旅游"等模式
    patterns = [
        r"(\w+)市",
        r"(\w+)旅游",
        r"去(\w+)",
        r"到(\w+)",
        r"(\w+)旅行",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1)
            # 至少2个字才可能是城市名
            if len(city) >= 2:
                return city

    return None


def _get_guide_rag_service():
    """延迟导入guide_rag_service"""
    global _guide_rag_service
    if _guide_rag_service is None:
        from services.guide_rag_service import search_guides_rag, build_rag_context_for_agent
        _guide_rag_service = (search_guides_rag, build_rag_context_for_agent)
    return _guide_rag_service


def _run_async_in_thread(coro):
    """在新线程中运行异步函数"""
    result = None
    exception = None

    def thread_target():
        nonlocal result, exception
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
        except Exception as e:
            exception = e
        finally:
            try:
                loop.close()
            except:
                pass

    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join()

    if exception:
        raise exception
    return result


class GuideSearchTool(Tool):
    """旅游攻略搜索工具"""

    def __init__(self):
        super().__init__(
            name="guide_search",
            description="搜索旅游攻略知识库。仅用于查询旅游攻略、行程推荐、玩法建议等需要攻略经验的问题。天气、实时价格等非攻略类问题请使用其他工具。",
        )

    def run(self, parameters: Optional[dict] = None) -> str:
        """
        执行攻略搜索

        Args:
            parameters: 参数字典，包含:
                - query: 搜索查询（必需）
                - city: 城市（可选）
                - limit: 返回结果数量，默认5
                - min_score: 最小相似度，默认0.3
                - use_llm_optimization: 是否使用LLM优化（可选）
                - enable_query_rewrite: 是否启用查询重写（可选）
                - enable_keyword_extraction: 是否启用关键词提取（可选）

        Returns:
            搜索结果的格式化字符串
        """
        print(f"\n🔍 [GuideSearchTool] 被调用，parameters={parameters}")
        try:
            if not parameters:
                print("  [GuideSearchTool] 参数为空")
                parameters = {}

            # 同时支持 query 和 keywords 参数（兼容不同的LLM调用方式）
            query = parameters.get("query", "") or parameters.get("keywords", "")

            # 如果没有 query/keywords 但有 city，就用 city 作为搜索词
            if not query:
                city = parameters.get("city")
                if city:
                    query = f"{city}旅游攻略"
                    print(f"  [GuideSearchTool] 未找到 query/keywords，使用 city 作为搜索词: {query}")
                else:
                    print(f"  [GuideSearchTool] 错误: 未找到 query/keywords/city 参数，parameters={parameters}")
                    return "❌ 请提供搜索查询"

            print(f"  [GuideSearchTool] 最终搜索 query={query}")

            city = parameters.get("city")
            print(f"  [GuideSearchTool] 传入的 city={city}")
            # 如果 Agent 没有传 city，尝试从 query 中提取
            if not city:
                extracted_city = _extract_city_from_query(query)
                if extracted_city:
                    city = extracted_city
                    print(f"  [GuideSearchTool] 从查询中自动提取城市: {city}")
                else:
                    print(f"  [GuideSearchTool] 未能从查询中提取城市")

            limit = int(parameters.get("limit", 5))
            min_score = float(parameters.get("min_score", 0.3))  # 与guide_rag_service默认值对齐
            print(f"  [GuideSearchTool] limit={limit}, min_score={min_score}")

            # 可选参数
            use_llm_optimization = parameters.get("use_llm_optimization")
            if use_llm_optimization is not None:
                use_llm_optimization = str(use_llm_optimization).lower() in ("true", "1", "yes")

            enable_query_rewrite = parameters.get("enable_query_rewrite")
            if enable_query_rewrite is not None:
                enable_query_rewrite = str(enable_query_rewrite).lower() in ("true", "1", "yes")

            enable_keyword_extraction = parameters.get("enable_keyword_extraction")
            if enable_keyword_extraction is not None:
                enable_keyword_extraction = str(enable_keyword_extraction).lower() in ("true", "1", "yes")

            print(f"  [GuideSearchTool] 开始搜索: query='{query}', city={city}")

            # 获取搜索函数
            search_guides_rag, build_rag_context_for_agent = _get_guide_rag_service()
            print(f"  [GuideSearchTool] 已获取 RAG 服务函数")

            # 在新线程中运行异步搜索
            print(f"  [GuideSearchTool] 正在调用 search_guides_rag...")
            results = _run_async_in_thread(
                search_guides_rag(
                    query=query,
                    city=city,
                    limit=limit,
                    min_score=min_score,
                    use_llm_optimization=use_llm_optimization,
                    enable_query_rewrite=enable_query_rewrite,
                    enable_keyword_extraction=enable_keyword_extraction
                )
            )
            print(f"  [GuideSearchTool] RAG 搜索完成，找到 {len(results)} 条结果")

            if not results:
                print(f"  [GuideSearchTool] 未找到结果，返回提示信息")
                if city:
                    return f"未找到关于「{city}」的本地旅游攻略。请使用高德地图工具搜索{city}的景点、美食、酒店等信息。"
                else:
                    return "未找到相关的本地旅游攻略。请使用高德地图工具搜索相关信息。"

            # 构建格式化输出
            output_parts = ["📚 找到以下相关旅游攻略：\n"]

            for i, result in enumerate(results, 1):
                guide_id = result.get("id")
                title = result.get("title", "无标题")
                city_name = result.get("city", "")
                score = result.get("score", 0)
                content = result.get("content", "")
                tags = result.get("metadata", {}).get("tags", [])

                # 添加带链接的攻略标题
                if guide_id:
                    output_parts.append(f"\n【攻略 {i}】[{title}](guide://{guide_id})")
                else:
                    output_parts.append(f"\n【攻略 {i}】{title}")

                if city_name:
                    output_parts.append(f"📍 城市: {city_name}")
                if tags:
                    output_parts.append(f"🏷️ 标签: {', '.join(tags)}")
                output_parts.append(f"⭐ 相关度: {score:.2f}")
                if content:
                    output_parts.append(f"📝 摘要: {content[:200]}...")

            output_parts.append("\n💡 提示：点击攻略标题可以查看详情，你也可以让我根据这些攻略为你推荐行程。")

            return "\n".join(output_parts)

        except Exception as e:
            error_msg = f"❌ 搜索攻略失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询（推荐使用），例如：'杭州亲子游攻略'、'北京三日游'",
                required=True
            ),
            ToolParameter(
                name="keywords",
                type="string",
                description="搜索关键词（备用参数，与query二选一），例如：'杭州旅游推荐'",
                required=False
            ),
            ToolParameter(
                name="city",
                type="string",
                description="城市名称，可选，例如：'杭州'、'北京'",
                required=False
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回结果数量，默认5",
                required=False,
                default=5
            ),
            ToolParameter(
                name="min_score",
                type="number",
                description="最小相似度分数，0-1之间，默认0.3",
                required=False,
                default=0.3
            ),
            ToolParameter(
                name="use_llm_optimization",
                type="boolean",
                description="是否使用LLM优化查询，默认true",
                required=False,
                default=True
            ),
            ToolParameter(
                name="enable_query_rewrite",
                type="boolean",
                description="是否启用查询重写，默认true",
                required=False,
                default=True
            ),
            ToolParameter(
                name="enable_keyword_extraction",
                type="boolean",
                description="是否启用关键词提取，默认true",
                required=False,
                default=True
            )
        ]


# 便捷函数
def search_guides(query: str, city: Optional[str] = None, limit: int = 5) -> str:
    """
    便捷搜索攻略函数

    Args:
        query: 搜索查询
        city: 城市
        limit: 返回结果数量

    Returns:
        搜索结果字符串
    """
    tool = GuideSearchTool()
    return tool.run({"query": query, "city": city, "limit": limit})

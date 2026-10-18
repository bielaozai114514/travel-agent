"""检索器模块 - 提供向量检索功能"""

from typing import List, Dict, Any, Optional


class Retriever:
    """
    检索器类

    提供向量相似度搜索功能
    支持分数过滤和结果排序
    """

    def __init__(self, vectorstore, embedding_model):
        """
        初始化检索器

        Args:
            vectorstore: 向量存储实例
            embedding_model: 嵌入模型实例
        """
        self.vectorstore = vectorstore
        self.embedding_model = embedding_model

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_score: 最小相似度分数
            filter_conditions: 过滤条件

        Returns:
            搜索结果列表
        """
        print(f"🔍 正在搜索: {query}")

        query_vector = self.embedding_model.encode_single(query)

        if not query_vector:
            print("❌ 查询向量化失败")
            return []

        results = self.vectorstore.search(
            query_vector=query_vector,
            top_k=top_k * 2,
            score_threshold=min_score if min_score > 0 else None,
            filter_conditions=filter_conditions
        )

        filtered_results = [
            r for r in results
            if r.get("score", 0) >= min_score
        ]

        filtered_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        filtered_results = filtered_results[:top_k]

        print(f"✅ 找到 {len(filtered_results)} 个相关结果")

        return filtered_results

    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        通过向量搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            min_score: 最小相似度分数
            filter_conditions: 过滤条件

        Returns:
            搜索结果列表
        """
        results = self.vectorstore.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=min_score if min_score > 0 else None,
            filter_conditions=filter_conditions
        )

        return [
            r for r in results
            if r.get("score", 0) >= min_score
        ]

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """
        格式化搜索结果为字符串

        Args:
            results: 搜索结果列表

        Returns:
            格式化后的字符串
        """
        if not results:
            return "未找到相关内容"

        formatted = []
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            metadata = result.get("metadata", {})
            content = metadata.get("content", "")

            if not content:
                content = "内容不可用"

            source = metadata.get("source", "未知来源")
            heading = metadata.get("heading_path", "")

            formatted.append(f"\n【结果 {i}】(相似度: {score:.3f})")
            formatted.append(f"来源: {source}")
            if heading:
                formatted.append(f"章节: {heading}")
            formatted.append(f"内容:\n{content[:300]}{'...' if len(content) > 300 else ''}")

        return '\n'.join(formatted)

    def get_context_for_llm(
        self,
        results: List[Dict[str, Any]],
        max_length: int = 2000
    ) -> str:
        """
        获取用于LLM的上下文

        Args:
            results: 搜索结果列表
            max_length: 最大长度

        Returns:
            上下文字符串
        """
        if not results:
            return ""

        contexts = []
        total_length = 0

        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            content = metadata.get("content", "")

            if not content:
                continue

            context_piece = f"[文档{i}]\n{content}\n"

            if total_length + len(context_piece) > max_length:
                break

            contexts.append(context_piece)
            total_length += len(context_piece)

        return '\n'.join(contexts)

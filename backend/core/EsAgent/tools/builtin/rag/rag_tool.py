"""RAG工具主类 - 提供完整的检索增强生成能力"""

import os
from typing import Dict, Any, List, Optional

from ...base import Tool, ToolParameter
from .embeddings import get_embedding_model
from .vectorstore import QdrantVectorStore
from .document_processor import DocumentProcessor
from .retriever import Retriever
from ....core.llm import EsAgentLLM
from ....core.exceptions import ToolException


class RAGTool(Tool):
    """
    RAG工具 - 检索增强生成

    功能：
    1. 添加多格式文档（PDF、Word、Excel、图片等）
    2. 智能检索与召回
    3. LLM增强问答
    4. 知识库管理
    """

    def __init__(
        self,
        collection_name: str = "esagent_rag",
        rag_namespace: str = "default",
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        model_path: Optional[str] = None
    ):
        """
        初始化RAG工具

        Args:
            collection_name: Qdrant集合名称
            rag_namespace: RAG命名空间（用于数据隔离）
            qdrant_url: Qdrant服务地址
            qdrant_api_key: Qdrant API密钥
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
            model_path: 嵌入模型路径
        """
        super().__init__(
            name="rag",
            description="RAG知识检索工具 - 当用户询问知识库相关问题时必须使用此工具！支持：search(搜索知识)、ask(智能问答)、add_text(添加知识)、add_document(添加文档)、stats(统计信息)。使用示例：[TOOL_CALL:rag:action=search,query=关键词] 或 [TOOL_CALL:rag:action=ask,question=问题]"
        )

        self.collection_name = collection_name
        self.rag_namespace = rag_namespace
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        print(f"初始化RAG工具 (命名空间: {rag_namespace})")

        self.embedding_model = get_embedding_model(model_path)

        self.vectorstore = QdrantVectorStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name,
            vector_size=self.embedding_model.dimension,
            rag_namespace=rag_namespace
        )

        self.doc_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        self.retriever = Retriever(
            vectorstore=self.vectorstore,
            embedding_model=self.embedding_model
        )

        self.llm = EsAgentLLM()

        print(f" RAG工具初始化完成")

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行RAG工具

        Args:
            parameters: 参数字典，必须包含action字段

        Returns:
            执行结果字符串
        """
        action = parameters.get("action", "search")

        try:
            if action == "add_document":
                return self._add_document(parameters)
            elif action == "add_text":
                return self._add_text(parameters)
            elif action == "search":
                return self._search(parameters)
            elif action == "ask":
                return self._ask(parameters)
            elif action == "stats":
                return self._get_stats()
            elif action == "clear":
                return self._clear_namespace()
            elif action == "delete_by_document_id":
                return self._delete_by_document_id(parameters)
            else:
                return f"❌ 未知的操作: {action}"

        except Exception as e:
            error_msg = f"❌ RAG工具执行失败: {str(e)}"
            print(error_msg)
            return error_msg

    def search_structured(self, query: str, top_k: int = 5, min_score: float = 0.0, filter_conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        结构化搜索 - 返回结构化数据而不是格式化字符串

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            min_score: 最小相似度分数
            filter_conditions: 过滤条件

        Returns:
            结构化搜索结果列表
        """
        print(f"\n 结构化搜索知识库: {query}")
        results = self.retriever.search(
            query=query,
            top_k=top_k,
            min_score=min_score,
            filter_conditions=filter_conditions
        )
        return results

    def delete_by_document_id_structured(self, document_id: str) -> bool:
        """
        根据文档ID删除向量 - 结构化版本

        Args:
            document_id: 文档ID

        Returns:
            是否成功
        """
        try:
            from qdrant_client.http import models

            # 使用 metadata 中的 document_id 过滤删除
            filter_conditions = {"document_id": document_id}

            must_conditions = [
                models.FieldCondition(
                    key="rag_namespace",
                    match=models.MatchValue(value=self.rag_namespace)
                )
            ]

            for key, value in filter_conditions.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )

            query_filter = models.Filter(must=must_conditions)

            self.vectorstore.client.delete(
                collection_name=self.vectorstore.collection_name,
                points_selector=models.FilterSelector(
                    filter=query_filter
                )
            )
            print(f"成功删除文档ID: {document_id} 的向量")
            return True

        except Exception as e:
            print(f"删除向量失败: {e}")
            return False

    def _delete_by_document_id(self, parameters: Dict[str, Any]) -> str:
        """根据文档ID删除向量"""
        document_id = parameters.get("document_id")
        if not document_id:
            return "缺少document_id参数"

        success = self.delete_by_document_id_structured(document_id)
        if success:
            return f"成功删除文档: {document_id}"
        else:
            return f"删除文档失败: {document_id}"

    def _add_document(self, parameters: Dict[str, Any]) -> str:
        """添加文档到知识库"""
        file_path = parameters.get("file_path")

        if not file_path:
            return "缺少file_path参数"

        if not os.path.exists(file_path):
            return f"文件不存在: {file_path}"

        print(f"\n开始处理文档: {file_path}")

        chunks = self.doc_processor.process_document(file_path)

        if not chunks:
            return "文档处理失败，未生成任何文本块"

        vectors = self.embedding_model.encode(
            [chunk["content"] for chunk in chunks],
            batch_size=32,
            show_progress_bar=False
        )

        metadata_list = []
        for chunk in chunks:
            meta = chunk["metadata"].copy()
            meta["content"] = chunk["content"]
            metadata_list.append(meta)

        ids = self.vectorstore.add_vectors(
            vectors=vectors,
            metadata=metadata_list
        )

        return f"文档添加成功！\n" \
               f"- 文件: {os.path.basename(file_path)}\n" \
               f"- 文本块数量: {len(chunks)}\n" \
               f"- 向量ID数量: {len(ids)}"

    def _add_text(self, parameters: Dict[str, Any]) -> str:
        """直接添加文本到知识库"""
        text = parameters.get("text")
        document_id = parameters.get("document_id", "direct_input")
        metadata = parameters.get("metadata", {})

        if not text:
            return "缺少text参数"

        print(f"\n开始处理文本 (ID: {document_id})")

        # 合并 metadata
        full_metadata = {"document_id": document_id, **metadata}

        chunks = self.doc_processor.process_text(
            text=text,
            metadata=full_metadata
        )

        if not chunks:
            return "❌ 文本处理失败，未生成任何文本块"

        vectors = self.embedding_model.encode(
            [chunk["content"] for chunk in chunks],
            batch_size=32,
            show_progress_bar=False
        )

        metadata_list = []
        for chunk in chunks:
            meta = chunk["metadata"].copy()
            meta["content"] = chunk["content"]
            metadata_list.append(meta)

        ids = self.vectorstore.add_vectors(
            vectors=vectors,
            metadata=metadata_list
        )

        return f"文本添加成功！\n" \
               f"- 文本ID: {document_id}\n" \
               f"- 文本块数量: {len(chunks)}\n" \
               f"- 向量ID数量: {len(ids)}"

    def _search(self, parameters: Dict[str, Any]) -> str:
        """搜索知识库"""
        query = parameters.get("query")
        top_k = parameters.get("limit", 5)
        min_score = parameters.get("min_score", 0.0)

        if not query:
            return "❌ 缺少query参数"

        print(f"\n🔍 搜索知识库: {query}")

        results = self.retriever.search(
            query=query,
            top_k=top_k,
            min_score=min_score
        )

        return self.retriever.format_results(results)

    def _ask(self, parameters: Dict[str, Any]) -> str:
        """智能问答"""
        question = parameters.get("question")
        top_k = parameters.get("limit", 5)
        min_score = parameters.get("min_score", 0.3)

        if not question:
            return "❌ 缺少question参数"

        print(f"\n❓ 智能问答: {question}")

        results = self.retriever.search(
            query=question,
            top_k=top_k,
            min_score=min_score
        )

        if not results:
            return "❌ 未找到相关信息，无法回答问题"

        context = self.retriever.get_context_for_llm(results, max_length=2000)

        prompt = self._build_qa_prompt(question, context)

        print("🤖 正在生成答案...")
        answer = self.llm.invoke([{"role": "user", "content": prompt}])

        sources = []
        for i, result in enumerate(results[:3], 1):
            metadata = result.get("metadata", {})
            source = metadata.get("source", "未知来源")
            score = result.get("score", 0)
            sources.append(f"{i}. {source} (相似度: {score:.3f})")

        return f"{answer}\n\n" \
               f"📚 参考来源:\n" + '\n'.join(sources)

    def _build_qa_prompt(self, question: str, context: str) -> str:
        """构建问答提示词"""
        return f"""基于以下参考信息回答问题。如果参考信息中没有相关内容，请明确说明。

参考信息：
{context}

问题：{question}

请提供准确、详细的回答："""

    def _get_stats(self) -> str:
        """获取知识库统计信息"""
        stats = self.vectorstore.get_stats()

        return f"📊 知识库统计信息:\n" \
               f"- 集合名称: {stats.get('collection_name', 'N/A')}\n" \
               f"- 向量维度: {stats.get('vector_size', 'N/A')}\n" \
               f"- 距离度量: {stats.get('distance', 'N/A')}\n" \
               f"- 向量数量: {stats.get('points_count', 0)}\n" \
               f"- 命名空间: {stats.get('rag_namespace', 'N/A')}\n" \
               f"- 状态: {stats.get('status', 'N/A')}"

    def _clear_namespace(self) -> str:
        """清空当前命名空间"""
        success = self.vectorstore.clear_namespace()

        if success:
            return f"✅ 已清空命名空间: {self.rag_namespace}"
        else:
            return f"❌ 清空命名空间失败"

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="操作类型: add_document(添加文档), add_text(添加文本), search(搜索), ask(问答), stats(统计), clear(清空)",
                required=True
            ),
            ToolParameter(
                name="file_path",
                type="string",
                description="文档路径（add_document操作必需）",
                required=False
            ),
            ToolParameter(
                name="text",
                type="string",
                description="文本内容（add_text操作必需）",
                required=False
            ),
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询（search操作必需）",
                required=False
            ),
            ToolParameter(
                name="question",
                type="string",
                description="问题（ask操作必需）",
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
                description="最小相似度分数，默认0.0",
                required=False,
                default=0.0
            ),
            ToolParameter(
                name="document_id",
                type="string",
                description="文档ID（add_text操作可选）",
                required=False
            )
        ]

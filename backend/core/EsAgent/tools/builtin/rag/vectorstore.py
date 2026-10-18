"""Qdrant向量存储模块"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

# 尝试导入 settings，如果失败则回退到环境变量
try:
    from settings import settings
    HAS_SETTINGS = True
except ImportError:
    HAS_SETTINGS = False


class QdrantVectorStore:
    """
    Qdrant向量存储封装类

    提供向量数据库的CRUD操作和相似度搜索功能
    支持命名空间隔离和多collection管理
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: str = "esagent_rag",
        vector_size: int = 512,
        distance: str = "Cosine",
        rag_namespace: str = "default"
    ):
        """
        初始化Qdrant向量存储

        Args:
            url: Qdrant服务地址，默认从环境变量读取
            api_key: API密钥，默认从环境变量读取
            collection_name: 集合名称
            vector_size: 向量维度
            distance: 距离度量方式 (Cosine/Euclidean/Dot)
            rag_namespace: RAG命名空间，用于数据隔离
        """
        # 优先使用传入的 url，然后从 settings 读取，最后用环境变量
        if url:
            self.url = url
        elif HAS_SETTINGS and hasattr(settings, "QDRANT_URL") and settings.QDRANT_URL:
            self.url = settings.QDRANT_URL
        elif HAS_SETTINGS and hasattr(settings, "QDRANT_HOST") and hasattr(settings, "QDRANT_PORT"):
            self.url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
        else:
            self.url = os.getenv("QDRANT_URL", "http://localhost:6333")

        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance = distance
        self.rag_namespace = rag_namespace

        self._client = None

    @property
    def client(self):
        """延迟加载Qdrant客户端"""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models

                print(f"🔄 正在连接Qdrant服务: {self.url}")

                if self.api_key:
                    self._client = QdrantClient(url=self.url, api_key=self.api_key)
                else:
                    self._client = QdrantClient(url=self.url)

                self._ensure_collection()
                print(f"✅ Qdrant连接成功")

            except Exception as e:
                raise RuntimeError(f"❌ 连接Qdrant失败: {e}")

        return self._client

    def _ensure_collection(self):
        """确保collection存在"""
        from qdrant_client.http import models

        try:
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                print(f"📦 创建新collection: {self.collection_name}")
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance[self.distance.upper()]
                    )
                )
                print(f"✅ Collection创建成功")
            else:
                print(f"✅ 使用现有collection: {self.collection_name}")

        except Exception as e:
            raise RuntimeError(f"❌ Collection初始化失败: {e}")

    def add_vectors(
        self,
        vectors: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        添加向量到数据库

        Args:
            vectors: 向量列表
            metadata: 元数据列表
            ids: ID列表，如果不提供则自动生成

        Returns:
            添加的ID列表
        """
        from qdrant_client.http import models

        if not vectors:
            return []

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]

        if metadata is None:
            metadata = [{} for _ in vectors]

        for meta in metadata:
            meta["rag_namespace"] = self.rag_namespace
            meta["timestamp"] = datetime.now().isoformat()

        points = [
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=meta
            )
            for point_id, vector, meta in zip(ids, vectors, metadata)
        ]

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            print(f"✅ 成功添加 {len(vectors)} 个向量")
            return ids

        except Exception as e:
            raise RuntimeError(f"❌ 添加向量失败: {e}")

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            score_threshold: 分数阈值
            filter_conditions: 过滤条件

        Returns:
            搜索结果列表
        """
        from qdrant_client.http import models

        query_filter = None
        if filter_conditions or self.rag_namespace:
            must_conditions = []

            if self.rag_namespace:
                must_conditions.append(
                    models.FieldCondition(
                        key="rag_namespace",
                        match=models.MatchValue(value=self.rag_namespace)
                    )
                )

            if filter_conditions:
                for key, value in filter_conditions.items():
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                    )

            query_filter = models.Filter(must=must_conditions)

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter
            )

            formatted_results = []
            for result in results.points:
                formatted_results.append({
                    "id": str(result.id),
                    "score": result.score,
                    "metadata": result.payload or {}
                })

            return formatted_results

        except Exception as e:
            raise RuntimeError(f"❌ 搜索失败: {e}")

    def delete_by_ids(self, ids: List[str]) -> bool:
        """
        根据ID删除向量

        Args:
            ids: ID列表

        Returns:
            是否成功
        """
        try:
            from qdrant_client.http import models

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=ids
                )
            )
            print(f"✅ 成功删除 {len(ids)} 个向量")
            return True

        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return False

    def delete_by_filter(self, filter_conditions: Dict[str, Any]) -> bool:
        """
        根据条件删除向量

        Args:
            filter_conditions: 过滤条件

        Returns:
            是否成功
        """
        try:
            from qdrant_client.http import models

            must_conditions = []
            for key, value in filter_conditions.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )

            query_filter = models.Filter(must=must_conditions)

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=query_filter
                )
            )
            print(f"✅ 成功删除符合条件的向量")
            return True

        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取collection统计信息

        Returns:
            统计信息字典
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)

            return {
                "collection_name": self.collection_name,
                "vector_size": self.vector_size,
                "distance": self.distance,
                "points_count": collection_info.points_count,
                "rag_namespace": self.rag_namespace,
                "status": collection_info.status.value
            }

        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }

    def clear_namespace(self) -> bool:
        """
        清空当前命名空间的所有数据

        Returns:
            是否成功
        """
        return self.delete_by_filter({"rag_namespace": self.rag_namespace})

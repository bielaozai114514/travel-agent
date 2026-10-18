"""嵌入模型封装 - 使用bge-small-zh-v1.5"""

import os
from typing import List, Optional
import numpy as np


class EmbeddingModel:
    """
    嵌入模型封装类

    使用bge-small-zh-v1.5模型进行文本向量化
    支持批量处理和缓存优化
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化嵌入模型

        Args:
            model_path: 模型路径，默认使用models/bge-small-zh-v1.5
        """
        self.model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "models", "bge-small-zh-v1.5"
        )

        self._model = None
        self._dimension = 512
        self._cache = {}

    @property
    def model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                print(f"正在加载嵌入模型: {self.model_path}")
                self._model = SentenceTransformer(self.model_path)
                self._dimension = self._model.get_sentence_embedding_dimension()
                print(f"模型加载成功，向量维度: {self._dimension}")
            except Exception as e:
                raise RuntimeError(f"❌ 加载嵌入模型失败: {e}")
        return self._model

    @property
    def dimension(self) -> int:
        """获取向量维度"""
        return self._dimension

    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize: bool = True,
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        批量编码文本为向量

        Args:
            texts: 文本列表
            batch_size: 批处理大小
            show_progress_bar: 是否显示进度条
            normalize: 是否归一化向量
            use_cache: 是否使用缓存

        Returns:
            向量列表
        """
        if not texts:
            return []

        vectors = []
        texts_to_encode = []
        indices_to_encode = []

        if use_cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    vectors.append(self._cache[cache_key])
                else:
                    texts_to_encode.append(text)
                    indices_to_encode.append(i)
        else:
            texts_to_encode = texts
            indices_to_encode = list(range(len(texts)))

        if texts_to_encode:
            print(f" 正在向量化 {len(texts_to_encode)} 个文本块...")
            new_vectors = self.model.encode(
                texts_to_encode,
                batch_size=batch_size,
                show_progress_bar=show_progress_bar,
                normalize_embeddings=normalize
            )

            new_vectors_list = new_vectors.tolist() if hasattr(new_vectors, 'tolist') else list(new_vectors)

            for text, vector in zip(texts_to_encode, new_vectors_list):
                if use_cache:
                    cache_key = self._get_cache_key(text)
                    self._cache[cache_key] = vector
                vectors.append(vector)

        if use_cache and len(texts_to_encode) > 0:
            print(f" 向量化完成，缓存大小: {len(self._cache)}")

        return vectors

    def encode_single(self, text: str, normalize: bool = True) -> List[float]:
        """
        编码单个文本

        Args:
            text: 文本内容
            normalize: 是否归一化

        Returns:
            向量
        """
        vectors = self.encode([text], normalize=normalize)
        return vectors[0] if vectors else []

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return f"{hash(text)}_{len(text)}"

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        print(" 嵌入缓存已清空")

    def get_cache_size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


_embedding_model_instance = None


def get_embedding_model(model_path: Optional[str] = None) -> EmbeddingModel:
    """
    获取嵌入模型实例（单例模式）

    Args:
        model_path: 模型路径

    Returns:
        EmbeddingModel实例
    """
    global _embedding_model_instance

    if _embedding_model_instance is None:
        _embedding_model_instance = EmbeddingModel(model_path)

    return _embedding_model_instance

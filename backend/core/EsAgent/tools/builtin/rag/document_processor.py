"""文档处理器 - 支持多格式文档转换和智能分块"""

import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime


class DocumentProcessor:
    """
    文档处理器

    功能：
    1. 多格式文档统一转换为Markdown（使用MarkItDown）
    2. 基于Markdown结构的智能分块
    3. 中英文混合Token估算
    4. 元数据管理
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文档处理器

        Args:
            chunk_size: 分块大小（Token数）
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._markitdown = None

    @property
    def markitdown(self):
        """延迟加载MarkItDown"""
        if self._markitdown is None:
            try:
                from markitdown import MarkItDown
                self._markitdown = MarkItDown()
                print(" MarkItDown加载成功")
            except Exception as e:
                print(f"MarkItDown加载失败: {e}")
                self._markitdown = None
        return self._markitdown

    def process_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        处理文档：转换 -> 分块

        Args:
            file_path: 文档路径
            metadata: 额外元数据

        Returns:
            文档块列表
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        print(f"正在处理文档: {file_path}")

        markdown_text = self.convert_to_markdown(file_path)

        if not markdown_text.strip():
            print(f"文档内容为空: {file_path}")
            return []

        base_metadata = {
            "source": os.path.basename(file_path),
            "file_path": file_path,
            "processed_at": datetime.now().isoformat(),
            **(metadata or {})
        }

        chunks = self.chunk_text(markdown_text, base_metadata)

        print(f"文档处理完成，生成 {len(chunks)} 个文本块")
        return chunks

    def convert_to_markdown(self, file_path: str) -> str:
        """
        将文档转换为Markdown格式

        Args:
            file_path: 文档路径

        Returns:
            Markdown文本
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext in ['.md', '.markdown', '.txt']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"❌ 读取文件失败: {e}")
                return ""

        if self.markitdown:
            try:
                print(f"使用MarkItDown转换: {ext}")
                result = self.markitdown.convert(file_path)
                markdown_text = getattr(result, "text_content", "")
                if markdown_text:
                    print(f"转换成功，长度: {len(markdown_text)} 字符")
                    return markdown_text
            except Exception as e:
                print(f"MarkItDown转换失败: {e}")

        print(f"无法处理文件格式: {ext}，尝试作为纯文本读取")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"读取失败: {e}")
            return ""

    def chunk_text(
        self,
        text: str,
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        智能分块文本

        Args:
            text: 文本内容
            base_metadata: 基础元数据

        Returns:
            文档块列表
        """
        paragraphs = self._split_by_headings(text)

        chunks = self._merge_paragraphs(paragraphs)

        result = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **(base_metadata or {}),
                "chunk_index": i,
                "total_chunks": len(chunks),
                "heading_path": chunk.get("heading_path"),
                "char_count": len(chunk["content"])
            }

            result.append({
                "content": chunk["content"],
                "metadata": chunk_metadata
            })

        return result

    def _split_by_headings(self, text: str) -> List[Dict[str, Any]]:
        """
        根据Markdown标题层次分割段落

        Args:
            text: Markdown文本

        Returns:
            段落列表
        """
        lines = text.splitlines()
        heading_stack = []
        paragraphs = []
        current_paragraph = []

        for line in lines:
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if heading_match:
                if current_paragraph:
                    content = '\n'.join(current_paragraph).strip()
                    if content:
                        paragraphs.append({
                            "content": content,
                            "heading_path": ' > '.join(heading_stack) if heading_stack else None
                        })
                    current_paragraph = []

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                while len(heading_stack) >= level:
                    heading_stack.pop()

                heading_stack.append(title)
            else:
                if line.strip():
                    current_paragraph.append(line)
                elif current_paragraph:
                    content = '\n'.join(current_paragraph).strip()
                    if content:
                        paragraphs.append({
                            "content": content,
                            "heading_path": ' > '.join(heading_stack) if heading_stack else None
                        })
                    current_paragraph = []

        if current_paragraph:
            content = '\n'.join(current_paragraph).strip()
            if content:
                paragraphs.append({
                    "content": content,
                    "heading_path": ' > '.join(heading_stack) if heading_stack else None
                })

        return paragraphs

    def _merge_paragraphs(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        根据Token数量合并段落

        Args:
            paragraphs: 段落列表

        Returns:
            合并后的块列表
        """
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para["content"])

            if current_tokens + para_tokens <= self.chunk_size or not current_chunk:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                chunk_content = '\n\n'.join(p["content"] for p in current_chunk)
                heading_path = current_chunk[-1].get("heading_path")

                chunks.append({
                    "content": chunk_content,
                    "heading_path": heading_path
                })

                overlap_paras = self._get_overlap_paragraphs(current_chunk)
                current_chunk = overlap_paras + [para]
                current_tokens = sum(self._estimate_tokens(p["content"]) for p in current_chunk)

        if current_chunk:
            chunk_content = '\n\n'.join(p["content"] for p in current_chunk)
            heading_path = current_chunk[-1].get("heading_path")

            chunks.append({
                "content": chunk_content,
                "heading_path": heading_path
            })

        return chunks

    def _get_overlap_paragraphs(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        获取重叠段落

        Args:
            paragraphs: 段落列表

        Returns:
            重叠段落列表
        """
        if self.chunk_overlap <= 0:
            return []

        overlap_paras = []
        overlap_tokens = 0

        for para in reversed(paragraphs):
            para_tokens = self._estimate_tokens(para["content"])
            if overlap_tokens + para_tokens > self.chunk_overlap:
                break
            overlap_paras.insert(0, para)
            overlap_tokens += para_tokens

        return overlap_paras

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的Token数量（支持中英文混合）

        Args:
            text: 文本内容

        Returns:
            Token数量估算
        """
        cjk_count = sum(1 for char in text if self._is_cjk(char))

        non_cjk_text = ''.join(char for char in text if not self._is_cjk(char))
        word_count = len(non_cjk_text.split())

        return cjk_count + word_count

    def _is_cjk(self, char: str) -> bool:
        """
        判断字符是否为CJK字符

        Args:
            char: 字符

        Returns:
            是否为CJK字符
        """
        code = ord(char)
        return (
            0x4E00 <= code <= 0x9FFF or
            0x3400 <= code <= 0x4DBF or
            0x20000 <= code <= 0x2A6DF or
            0x2A700 <= code <= 0x2B73F or
            0x2B740 <= code <= 0x2B81F or
            0x2B820 <= code <= 0x2CEAF or
            0xF900 <= code <= 0xFAFF
        )

    def process_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        直接处理文本内容

        Args:
            text: 文本内容
            metadata: 元数据

        Returns:
            文档块列表
        """
        base_metadata = {
            "source": "direct_input",
            "processed_at": datetime.now().isoformat(),
            **(metadata or {})
        }

        return self.chunk_text(text, base_metadata)

"""解析器抽象基类.

按 .coderabbit.yaml 的 parsers 规则要求:
  - 大文件防御: PDF/Word 超过 100MB 必须分块 (具体实现见子类)
  - 恶意文档: 子类必须关闭 XXE / 拒绝可疑宏
  - 内存控制: 使用生成器/流式 API
  - 表格/OCR 错误必须有 fallback
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


class ParserError(Exception):
    """解析失败 - 上层应转 ReviewState.FAILED."""


@dataclass
class ParsedDocument:
    """解析结果 - 统一输出格式."""

    # 文档全文 (可能很长, 上层需要 chunker 切分)
    text: str
    # 页数 (PDF) 或段落数 (其他)
    page_count: int = 0
    # 从原文档抽取到的元信息 (title / author / ...)
    metadata: dict[str, str] = field(default_factory=dict)


class BaseParser(ABC):
    """解析器基类."""

    #: 支持的文件扩展名 (小写, 不含点)
    extensions: tuple[str, ...] = ()

    #: 单文件字节上限, 子类可覆盖
    max_bytes: int = 50 * 1024 * 1024  # 50 MB

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lstrip(".").lower() in self.extensions

    def check_size(self, path: Path) -> None:
        size = path.stat().st_size
        if size > self.max_bytes:
            raise ParserError(f"文件过大: {size} 字节 > 上限 {self.max_bytes} 字节 ({path.name})")

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """把路径指向的文档解析为 ParsedDocument."""

    @abstractmethod
    def iter_pages(self, path: Path) -> Iterator[str]:
        """流式按页/段输出纯文本, 避免一次性加载整个文档."""

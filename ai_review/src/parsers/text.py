"""纯文本 / Markdown 解析器 - 最简实现, 用于测试和简单场景."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from src.parsers.base import BaseParser, ParsedDocument, ParserError


class TextParser(BaseParser):
    """纯文本 / Markdown 解析器."""

    extensions = ("txt", "md", "markdown")

    def parse(self, path: Path) -> ParsedDocument:
        self.check_size(path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ParserError(f"UTF-8 解码失败: {path.name}") from e
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        return ParsedDocument(
            text=text,
            page_count=len(paragraphs),
            metadata={"format": path.suffix.lstrip(".")},
        )

    def iter_pages(self, path: Path) -> Iterator[str]:
        """按段落流式输出."""
        self.check_size(path)
        # 简化: 一次读但按段落切分, 用 yield 让上层能流式消费
        text = path.read_text(encoding="utf-8")
        for paragraph in text.split("\n\n"):
            if paragraph.strip():
                yield paragraph

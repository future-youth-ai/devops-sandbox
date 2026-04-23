"""文档解析器 - 把 PDF/Word/Markdown 统一转成纯文本 + 结构化元信息."""

from src.parsers.base import BaseParser, ParsedDocument, ParserError

__all__ = ["BaseParser", "ParsedDocument", "ParserError"]

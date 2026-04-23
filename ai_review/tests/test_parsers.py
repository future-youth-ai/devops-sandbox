"""文档解析器测试."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.parsers import ParserError
from src.parsers.text import TextParser


class TestTextParser:
    def test_can_parse_extensions(self, tmp_path: Path) -> None:
        p = TextParser()
        assert p.can_parse(tmp_path / "foo.txt")
        assert p.can_parse(tmp_path / "foo.md")
        assert p.can_parse(tmp_path / "foo.markdown")
        assert not p.can_parse(tmp_path / "foo.pdf")
        assert not p.can_parse(tmp_path / "foo.docx")

    def test_parse_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nBody paragraph 1.\n\nBody paragraph 2.", encoding="utf-8")
        doc = TextParser().parse(f)
        assert "Title" in doc.text
        assert doc.page_count == 3  # 3 段
        assert doc.metadata["format"] == "md"

    def test_iter_pages_yields_paragraphs(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("p1\n\np2\n\np3", encoding="utf-8")
        pages = list(TextParser().iter_pages(f))
        assert pages == ["p1", "p2", "p3"]

    def test_reject_oversized(self, tmp_path: Path) -> None:
        p = TextParser()
        p.max_bytes = 10
        f = tmp_path / "big.txt"
        f.write_text("a" * 100, encoding="utf-8")
        with pytest.raises(ParserError, match="文件过大"):
            p.parse(f)

    def test_reject_non_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "gbk.txt"
        f.write_bytes("中文".encode("gbk"))
        with pytest.raises(ParserError, match="UTF-8"):
            TextParser().parse(f)

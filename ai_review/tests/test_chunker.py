"""RAG chunker 测试."""

from __future__ import annotations

import dataclasses

import pytest

from src.rag.chunker import Chunk, chunk_text


class TestChunkText:
    def test_empty_returns_empty(self) -> None:
        assert chunk_text("") == []

    def test_short_text_single_chunk(self) -> None:
        chunks = chunk_text("hello world", chunk_size=100, chunk_overlap=10)
        assert len(chunks) == 1
        assert chunks[0].text == "hello world"
        assert chunks[0].start_offset == 0
        assert chunks[0].end_offset == 11

    def test_long_text_overlapped(self) -> None:
        text = "a" * 1000
        chunks = chunk_text(text, chunk_size=400, chunk_overlap=100)
        # step = 400 - 100 = 300; 到达末尾立即 break
        assert [(c.start_offset, c.end_offset) for c in chunks] == [
            (0, 400),
            (300, 700),
            (600, 1000),
        ]

    def test_chunks_are_indexed_sequentially(self) -> None:
        chunks = chunk_text("x" * 500, chunk_size=200, chunk_overlap=50)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_chunks_cover_all_text(self) -> None:
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        reconstructed_at_start = chunks[0].text
        assert text.startswith(reconstructed_at_start)
        assert chunks[-1].end_offset == len(text)

    def test_chunk_length_property(self) -> None:
        chunks = chunk_text("hello", chunk_size=3, chunk_overlap=1)
        assert chunks[0].length == 3


class TestChunkTextValidation:
    def test_reject_zero_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("x", chunk_size=0)

    def test_reject_negative_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("x", chunk_size=-1)

    def test_reject_overlap_ge_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text("x", chunk_size=100, chunk_overlap=100)

    def test_reject_negative_overlap(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text("x", chunk_size=100, chunk_overlap=-1)


def test_chunk_dataclass_is_frozen() -> None:
    c = Chunk(index=0, text="x", start_offset=0, end_offset=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.index = 99  # type: ignore[misc]

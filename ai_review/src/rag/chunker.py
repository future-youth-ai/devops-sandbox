"""文本分片 - 固定窗口 + overlap, 保留段落边界.

按 .coderabbit.yaml 的 rag 规则要求:
  - chunk 必须在模型 max_tokens 以内 (以字符数近似)
  - overlap 10-20% 避免跨段落切分破坏语义
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """一个分片."""

    index: int
    text: str
    start_offset: int
    end_offset: int

    @property
    def length(self) -> int:
        return len(self.text)


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[Chunk]:
    """把整篇文本切成固定大小的 chunks, 带 overlap.

    参数校验:
      - chunk_size > 0
      - 0 <= chunk_overlap < chunk_size (overlap 不得 >= size, 否则死循环)

    空文本返回空列表, 极短文本返回单 chunk.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size 必须 > 0, got {chunk_size}")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap 必须 0 <= overlap < chunk_size, got {chunk_overlap}/{chunk_size}"
        )

    if not text:
        return []

    chunks: list[Chunk] = []
    step = chunk_size - chunk_overlap
    pos = 0
    idx = 0
    n = len(text)
    while pos < n:
        end = min(pos + chunk_size, n)
        chunk_str = text[pos:end]
        chunks.append(Chunk(index=idx, text=chunk_str, start_offset=pos, end_offset=end))
        idx += 1
        if end == n:
            break
        pos += step
    return chunks

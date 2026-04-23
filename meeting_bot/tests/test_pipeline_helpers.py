"""Pipeline helpers 单元测试 (不启动完整 Pipeline)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from meeting_bot.pipeline import _normalize_ts, _parse_ts


class TestNormalizeTs:
    def test_none_returns_zero(self) -> None:
        assert _normalize_ts(None) == 0

    def test_empty_string_returns_zero(self) -> None:
        assert _normalize_ts("") == 0
        assert _normalize_ts("   ") == 0

    def test_int_seconds(self) -> None:
        assert _normalize_ts(1700000000) == 1700000000

    def test_int_milliseconds_normalized_to_seconds(self) -> None:
        # > 1e12 视作毫秒, 除以 1000
        assert _normalize_ts(1700000000000) == 1700000000

    def test_float_seconds(self) -> None:
        assert _normalize_ts(1700000000.5) == 1700000000

    def test_numeric_string(self) -> None:
        assert _normalize_ts("1700000000") == 1700000000

    def test_iso_string(self) -> None:
        # 2023-11-14 22:13:20 UTC -> 1700000000
        assert _normalize_ts("2023-11-14T22:13:20+00:00") == 1700000000

    def test_iso_with_z(self) -> None:
        assert _normalize_ts("2023-11-14T22:13:20Z") == 1700000000

    def test_invalid_string_returns_zero(self) -> None:
        # ISO 解析失败 -> 0 (走 skip 分支, 不抛异常)
        assert _normalize_ts("not-a-date") == 0
        assert _normalize_ts("abc123") == 0

    def test_negative_zero_returns_zero(self) -> None:
        assert _normalize_ts(0) == 0
        assert _normalize_ts(-1) == 0

    def test_bool_returns_zero(self) -> None:
        # True/False 虽然是 int 子类, 但语义不该当时间戳用
        assert _normalize_ts(True) == 0
        assert _normalize_ts(False) == 0

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, 0),
            ("", 0),
            ("1700000000", 1700000000),
            (1700000000, 1700000000),
            (1700000000000, 1700000000),  # ms
            ("not-a-date", 0),
        ],
    )
    def test_parametrized(self, value: object, expected: int) -> None:
        assert _normalize_ts(value) == expected


class TestParseTs:
    def test_none_returns_now(self) -> None:
        r = _parse_ts(None)
        assert isinstance(r, datetime)
        assert r.tzinfo is UTC

    def test_int_seconds(self) -> None:
        r = _parse_ts(1700000000)
        assert r.year == 2023
        assert r.tzinfo is UTC

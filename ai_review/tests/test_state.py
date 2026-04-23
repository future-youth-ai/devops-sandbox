"""审核状态机测试."""

from __future__ import annotations

import pytest

from src.review.state import (
    InvalidTransitionError,
    ReviewState,
    is_terminal,
    transition,
)


class TestTransition:
    def test_valid_happy_path(self) -> None:
        # PENDING -> PARSING -> REVIEWING -> APPROVED
        s = ReviewState.PENDING
        s = transition(s, ReviewState.PARSING)
        s = transition(s, ReviewState.REVIEWING)
        s = transition(s, ReviewState.APPROVED)
        assert s == ReviewState.APPROVED

    def test_reject_path(self) -> None:
        s = transition(ReviewState.REVIEWING, ReviewState.REJECTED)
        assert s == ReviewState.REJECTED

    def test_failed_from_any_non_terminal(self) -> None:
        for src in (ReviewState.PENDING, ReviewState.PARSING, ReviewState.REVIEWING):
            assert transition(src, ReviewState.FAILED) == ReviewState.FAILED

    def test_idempotent_same_state(self) -> None:
        # 允许 current == target, 支持重试幂等
        assert transition(ReviewState.REVIEWING, ReviewState.REVIEWING) == ReviewState.REVIEWING
        assert transition(ReviewState.APPROVED, ReviewState.APPROVED) == ReviewState.APPROVED

    def test_reject_invalid_transitions(self) -> None:
        # PENDING 不能直接到 APPROVED
        with pytest.raises(InvalidTransitionError, match="pending -> approved"):
            transition(ReviewState.PENDING, ReviewState.APPROVED)

    def test_terminal_states_are_frozen(self) -> None:
        # 终态不能跳出
        for terminal in (ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.FAILED):
            with pytest.raises(InvalidTransitionError):
                transition(terminal, ReviewState.REVIEWING)
            with pytest.raises(InvalidTransitionError):
                transition(terminal, ReviewState.PENDING)

    def test_backward_transitions_forbidden(self) -> None:
        # REVIEWING 不能回 PARSING
        with pytest.raises(InvalidTransitionError):
            transition(ReviewState.REVIEWING, ReviewState.PARSING)


class TestIsTerminal:
    def test_terminal_states(self) -> None:
        assert is_terminal(ReviewState.APPROVED)
        assert is_terminal(ReviewState.REJECTED)
        assert is_terminal(ReviewState.FAILED)

    def test_non_terminal_states(self) -> None:
        assert not is_terminal(ReviewState.PENDING)
        assert not is_terminal(ReviewState.PARSING)
        assert not is_terminal(ReviewState.REVIEWING)

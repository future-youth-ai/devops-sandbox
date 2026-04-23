"""审核任务状态机.

按 .coderabbit.yaml 的 review 规则要求:
  - 所有状态转移必须显式列出, 禁止隐式跳转
  - 审核任务重试必须幂等 (task_id + version 去重)
"""

from __future__ import annotations

from enum import Enum


class ReviewState(str, Enum):
    """审核状态。字符串 enum 便于直接 JSON 序列化."""

    PENDING = "pending"  # 已提交, 待进入审核队列
    PARSING = "parsing"  # 文档解析中
    REVIEWING = "reviewing"  # LLM 审核中
    APPROVED = "approved"  # 审核通过
    REJECTED = "rejected"  # 审核未通过
    FAILED = "failed"  # 系统错误 (解析失败/LLM 超时等)


# 显式列出所有合法转移, 其他转移一律抛 InvalidTransition
_ALLOWED_TRANSITIONS: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.PENDING: frozenset({ReviewState.PARSING, ReviewState.FAILED}),
    ReviewState.PARSING: frozenset({ReviewState.REVIEWING, ReviewState.FAILED}),
    ReviewState.REVIEWING: frozenset(
        {ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.FAILED}
    ),
    # 终态: approved / rejected / failed 不可再转移
    ReviewState.APPROVED: frozenset(),
    ReviewState.REJECTED: frozenset(),
    ReviewState.FAILED: frozenset(),
}


class InvalidTransitionError(ValueError):
    """非法状态转移."""


def transition(current: ReviewState, target: ReviewState) -> ReviewState:
    """校验并执行状态转移, 非法转移抛 InvalidTransitionError.

    幂等: 允许 current == target (例如重试时重复 mark_reviewing).
    """
    if current == target:
        return target
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"不允许的状态转移: {current.value} -> {target.value}; "
            f"允许: {[s.value for s in allowed] or '(终态)'}"
        )
    return target


def is_terminal(state: ReviewState) -> bool:
    """是否终态."""
    return state in {ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.FAILED}

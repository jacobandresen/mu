"""Tests for repair-loop degeneration detection (REPAIR_ESCALATE sentinel)."""

from unittest.mock import MagicMock, patch

import pytest
from mu.session import REPAIR_ESCALATE, Session, _FOCUS_LOOP_THRESHOLD


def _make_repair_session() -> Session:
    return Session(system_prompt="test")


def _stub_chat(*args, **kwargs):
    """Return a no-op Edit tool call so the repair loop makes progress without a real LLM."""
    msg = {
        'role': 'assistant',
        'content': '',
        'tool_calls': [{'id': 'x', 'type': 'function',
                        'function': {'name': 'Edit',
                                     'arguments': '{"file_path":"x","old_string":"a","new_string":"b"}'}}],
    }
    stats = MagicMock(prompt_tokens=1, generated_tokens=1)
    return msg, stats


def _run_loop(session: Session, test_outcomes: list[tuple[bool, str]]) -> tuple[bool, int]:
    """Drive repair_loop with scripted (passed, output) pairs; model calls are stubbed."""
    it = iter(test_outcomes)

    def run_test():
        try:
            return next(it)
        except StopIteration:
            return False, "no more outputs"

    with patch('mu.session.chat_or_retry', side_effect=_stub_chat):
        return session.repair_loop(
            model='stub', goal='test', max_iters=10,
            per_turn_timeout=30.0,
            run_test=run_test,
            reapply=None,
            context='',
        )


def _same_focus_outputs(focus_line: str, count: int) -> list[tuple[bool, str]]:
    """Produce `count` consecutive failing outputs with the same distillable error."""
    return [(False, focus_line)] * count


def test_escalate_fires_after_threshold():
    """Same distilled error for _FOCUS_LOOP_THRESHOLD+1 consecutive passes → REPAIR_ESCALATE."""
    sess = _make_repair_session()
    # The line "Jest: ESM/CJS parse error" matches a known diagnose rule.
    outputs = _same_focus_outputs("Jest encountered an unexpected token", _FOCUS_LOOP_THRESHOLD + 1)
    passed, iters = _run_loop(sess, outputs)
    assert not passed
    assert iters == REPAIR_ESCALATE


def test_no_escalate_before_threshold():
    """Fewer consecutive same-focus passes do not trigger escalation."""
    sess = _make_repair_session()
    # _FOCUS_LOOP_THRESHOLD - 1 same-focus passes, then a different output
    outputs = (
        _same_focus_outputs("Jest encountered an unexpected token", _FOCUS_LOOP_THRESHOLD - 1)
        + [(True, "all tests pass")]
    )
    passed, iters = _run_loop(sess, outputs)
    assert passed
    assert iters >= 0


def test_no_escalate_on_empty_focus():
    """Unrecognized output (empty FOCUS) does not count toward the loop threshold."""
    sess = _make_repair_session()
    # Unrecognized lines produce no FOCUS hint → loop runs to max without escalating
    outputs = [(False, "some unrecognized noise")] * (_FOCUS_LOOP_THRESHOLD + 2)
    passed, iters = _run_loop(sess, outputs)
    # Should not return REPAIR_ESCALATE — empty focus is never compared
    assert iters != REPAIR_ESCALATE


def test_escalate_resets_on_focus_change():
    """Counter resets when the distilled error changes — escalation requires consecutive same."""
    sess = _make_repair_session()
    outputs = [
        (False, "Jest encountered an unexpected token"),
        (False, "TypeError: Cannot read properties of undefined"),  # different error
        (False, "Jest encountered an unexpected token"),
        (False, "Jest encountered an unexpected token"),  # back to same, but counter reset
        (True, "pass"),
    ]
    passed, iters = _run_loop(sess, outputs)
    assert passed
    assert iters >= 0


def test_repair_escalate_constant_is_negative():
    """REPAIR_ESCALATE must be negative so max(iters, 0) safely sanitizes it."""
    assert REPAIR_ESCALATE < 0


def test_focus_loop_threshold_is_at_least_two():
    """Threshold must be ≥2 so a single bad repair pass can't trigger escalation."""
    assert _FOCUS_LOOP_THRESHOLD >= 2

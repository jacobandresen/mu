"""Regression: the repair prompt must stay inside the model's context budget.

2026-06-12 run 4: 31 'Context size has been exceeded' HTTP 400s — three
history units, each embedding ~8KB of file context plus test output plus
whole files inside Write tool-call arguments, overflow a 6000-token window.
"""

from mu.client import message_chars
from mu.session import _fit_prompt_budget
from mu.client import max_prompt_tokens

SYS = {'role': 'system', 'content': 'x' * 2000}


def _unit(size: int) -> list[dict]:
    return [
        {'role': 'user', 'content': 'u' * size},
        {'role': 'assistant', 'content': None,
         'tool_calls': [{'function': {'name': 'Write', 'arguments': 'a' * size}}]},
        {'role': 'tool', 'content': 'ok'},
    ]


def _total(msgs: list[dict]) -> int:
    return sum(message_chars(m) for m in msgs)


def test_oldest_units_dropped_first():
    user = {'role': 'user', 'content': 'fix it'}
    units = [_unit(8000), _unit(8000), _unit(8000)]
    units[0][0]['content'] = 'OLDEST' + units[0][0]['content']
    msgs = _fit_prompt_budget(SYS, units, user)
    assert _total(msgs) <= max_prompt_tokens() * 4
    flat = ' '.join(str(m.get('content')) for m in msgs)
    assert 'OLDEST' not in flat
    assert msgs[0] is SYS and msgs[-1] is user


def test_small_history_untouched():
    user = {'role': 'user', 'content': 'fix it'}
    units = [_unit(100), _unit(100)]
    msgs = _fit_prompt_budget(SYS, units, user)
    assert len(msgs) == 2 + 2 * 3  # system + 2 full units + user


def test_giant_user_message_trimmed():
    big = 'HEAD' + 'z' * (max_prompt_tokens() * 8) + 'TAIL'
    user = {'role': 'user', 'content': big}
    msgs = _fit_prompt_budget(SYS, [], user)
    out = msgs[-1]['content']
    assert _total(msgs) <= max_prompt_tokens() * 4
    assert out.startswith('HEAD') and out.endswith('TAIL')
    assert 'trimmed to fit' in out


def test_tool_call_arguments_counted():
    m = {'role': 'assistant', 'content': None,
         'tool_calls': [{'function': {'name': 'Write', 'arguments': 'a' * 5000}}]}
    assert message_chars(m) > 5000

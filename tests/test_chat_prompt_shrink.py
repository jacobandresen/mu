"""Regression: chat() must not send prompts the server will reject.

2026-06-12 run 5: 36 'Context size has been exceeded' HTTP 400s from
stage-planner and writer calls whose prompts approached the loaded window —
the window bounds prompt + generation together, so the prompt budget must
reserve generation room and oversized prompts must be shrunk client-side.
"""

from mu.client import (_GEN_RESERVE, _NUM_CTX, _est_tokens, _shrink_oversized,
                       max_prompt_tokens)


def test_budget_reserves_generation_room():
    assert max_prompt_tokens() == max(_NUM_CTX - _GEN_RESERVE, 1024)
    assert max_prompt_tokens() < _NUM_CTX


def test_small_prompt_untouched():
    msgs = [{'role': 'system', 'content': 'be terse'},
            {'role': 'user', 'content': 'hello'}]
    assert _shrink_oversized(msgs) is msgs


def test_oversized_prompt_shrunk_under_budget():
    big = 'INSTRUCTIONS.' + 'x' * (max_prompt_tokens() * 8) + '.NEWEST_ERROR'
    msgs = [{'role': 'system', 'content': 'sys'},
            {'role': 'user', 'content': big}]
    out = _shrink_oversized(msgs)
    assert _est_tokens(out) <= max_prompt_tokens()
    assert out[1]['content'].startswith('INSTRUCTIONS.')
    assert out[1]['content'].endswith('.NEWEST_ERROR')
    assert 'trimmed to fit context' in out[1]['content']
    # original list untouched (callers keep their own history)
    assert msgs[1]['content'] == big


def test_tool_call_arguments_count_toward_estimate():
    msgs = [{'role': 'assistant', 'content': None,
             'tool_calls': [{'function': {'name': 'Write',
                                          'arguments': 'a' * 4000}}]}]
    assert _est_tokens(msgs) >= 1000

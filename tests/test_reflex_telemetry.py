"""Reflex-improvement telemetry: firings from direct calls, pass diffs,
and the repair trace — the data improvement rounds mine for new reflexes."""

import json
from pathlib import Path

from mu.reflexes.core import (get_firings, get_reflex_diffs, note_reflex_diff,
                              noted, reset_firings, reset_reflex_diffs)
import mu.session as session
from mu.session import flush_repair_trace, reset_repair_trace


def test_noted_records_only_changes(tmp_path: Path):
    reset_firings()
    f = tmp_path / 'x.py'
    f.write_text('conn = sqlite3.connect(":memory:")\n')
    from mu.reflexes.python import fix_python_missing_stdlib_imports
    assert noted(fix_python_missing_stdlib_imports, str(f))      # fires
    assert not noted(fix_python_missing_stdlib_imports, str(f))  # idempotent
    fired = get_firings()
    assert len(fired) == 1
    assert fired[0]['reflex_id'] == 'fix_python_missing_stdlib_imports'
    assert fired[0]['file'] == str(f)


def test_noted_swallows_reflex_crash():
    reset_firings()
    def boom(_path):
        raise RuntimeError('reflex bug')
    assert noted(boom, 'whatever.py') is False
    assert get_firings() == []


def test_reflex_diff_recorded_and_capped():
    reset_reflex_diffs()
    note_reflex_diff('write_pass', 'a.py', 'x = 1\n', 'x = 1\n')  # no change
    assert get_reflex_diffs() == []
    note_reflex_diff('write_pass', 'a.py', 'x = 1\n', 'import os\nx = 1\n')
    big_before = '\n'.join(f'line {i}' for i in range(500)) + '\n'
    note_reflex_diff('write_pass', 'b.py', big_before, '')
    diffs = get_reflex_diffs()
    assert len(diffs) == 2
    assert '+import os' in diffs[0]['diff']
    assert 'truncated' in diffs[1]['diff']
    assert len(diffs[1]['diff']) < 2200


def test_repair_trace_flow():
    reset_repair_trace()
    session._REPAIR_TRACE.append(
        {'iter': 0, 'focus': 'CS0017: two Main entry points',
         'edited': True, 'diffs': ['--- a/P.cs'], 'stuck': False})
    session._REPAIR_TRACE[-1]['passed_after'] = True
    out = flush_repair_trace()
    assert out[0]['passed_after'] is True
    assert flush_repair_trace() == []
    entry = json.dumps(out[0])  # must be JSON-serializable for the archive
    assert 'CS0017' in entry

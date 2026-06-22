"""Cross-stage no-double-build: the inter-stage gate must not re-run the backend
test when the backend stage already proved that exact state green (the shared
staged BuildLedger). Deterministic — _test_passed and the C# reflexes are stubbed,
so no model is needed.
"""

import mu.agent as agent
from mu import incremental
from mu.plan import parse

_BACKEND_PLAN = """## Summary
backend API

## Files
- [x] Post.cs — model
- [x] PostsTests.cs — xunit test

## Test Command
dotnet test
"""


def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = tmp_path / 'PLAN.backend.md'
    pf.write_text(_BACKEND_PLAN)
    (tmp_path / 'Post.cs').write_text('public class Post {}')
    (tmp_path / 'PostsTests.cs').write_text('// test')
    calls = []
    monkeypatch.setattr(agent, '_test_passed', lambda *a, **k: calls.append(a) or True)
    monkeypatch.setattr(agent, '_fired', lambda *a, **k: False)   # stub C# reflexes
    return str(pf), calls


def _key(plan_file):
    p = parse(plan_file)
    return incremental.gate_key(incremental.gate_paths(p), p.test_command.strip())


def test_inter_stage_gate_skips_already_green_backend(tmp_path, monkeypatch):
    pf, calls = _setup(tmp_path, monkeypatch)
    led = incremental.BuildLedger()
    led.record_gate(_key(pf))                       # backend stage proved this state
    monkeypatch.setattr(agent, '_staged_ledger', led)
    assert agent._inter_stage_gate(pf, 'goal', 'model') == 0
    assert calls == []                              # not tested twice


def test_inter_stage_gate_runs_and_records_when_unproven(tmp_path, monkeypatch):
    pf, calls = _setup(tmp_path, monkeypatch)
    led = incremental.BuildLedger()
    monkeypatch.setattr(agent, '_staged_ledger', led)
    assert agent._inter_stage_gate(pf, 'goal', 'model') == 0
    assert len(calls) == 1                          # gate ran
    assert led.was_gated(_key(pf))                  # recorded for the next gate


def test_inter_stage_gate_unchanged_without_ledger(tmp_path, monkeypatch):
    # No staged ledger (flag off) ⇒ legacy behaviour: always runs the gate.
    pf, calls = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(agent, '_staged_ledger', None)
    assert agent._inter_stage_gate(pf, 'goal', 'model') == 0
    assert len(calls) == 1

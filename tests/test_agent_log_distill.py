"""Tests for the agent.log tee pipeline: pre-test failures must leave a
distillable record.

Collection run 2026-06-11 (3h): 40 of 45 failed sessions archived an empty
logs/ dir — the planner died on LM Studio HTTP 400 (model resident with a
4096 context while MU_NUM_CTX=6000) before any test ran, and observe could
only say "(no test log)". The fix tees log() into .mu/agent.log, archives it,
lets _distill_session fall back to it, and teaches diagnose the LM Studio
context-overflow grammar.
"""

import os

from mu.diagnose import distill_test_errors
from mu.observe import _distill_session

_OVERFLOW = ("Planner error: Client error '400 Bad Request' for url "
             "'http://localhost:1234/v1/chat/completions'\n"
             "  server detail: {\"error\":\"request (4708 tokens) exceeds the "
             "available context size (4096 tokens), try increasing it\"}")


def test_diagnose_context_overflow_specific_hint():
    focus = distill_test_errors(_OVERFLOW)
    assert '4708' in focus and '4096' in focus
    assert 'loaded context' in focus


def test_diagnose_http_400_weak_hint_alone():
    # Without a detail line, the weak rule still names the HTTP failure.
    focus = distill_test_errors(
        "Planner error: Client error '400 Bad Request' for url "
        "'http://localhost:1234/v1/chat/completions'")
    assert 'HTTP 400' in focus


def test_distill_session_falls_back_to_agent_log(tmp_path):
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'agent.log').write_text(_OVERFLOW + '\n')
    sig = _distill_session(str(tmp_path))
    assert sig != '(no test log)'
    assert 'context' in sig


def test_distill_session_prefers_test_log_over_agent_log(tmp_path):
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'tests-final.log').write_text(
        "E   NameError: name 'app' is not defined\n")
    (logs / 'agent.log').write_text(_OVERFLOW + '\n')
    sig = _distill_session(str(tmp_path))
    assert 'NameError' in sig


def test_log_tees_to_agent_log_and_session_truncates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from mu import agent
    from mu.archive import AgentSession
    agent.log("first event %d", 1)
    log_path = tmp_path / agent.LOG_DIR / 'agent.log'
    assert 'first event 1' in log_path.read_text()
    # New session truncates the tee so the archive holds only its own events.
    AgentSession('test goal', str(tmp_path / 'arch'), agent.LOG_DIR, max_iter=1)
    assert log_path.read_text() == ''
    agent.log("second event")
    assert log_path.read_text() == 'second event\n'

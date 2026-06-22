"""_run_cmd must reap the whole process group, not just the top-level shell.

A test/build command can spawn a server or a non-terminating binary that outlives
the shell (the dojo "zombie binary" problem: hung dotnet exes that pinned files and
RAM). _run_cmd runs every command in its own session and kills the group on exit,
so nothing it launched survives the call.
"""

import time

from mu import agent


def test_run_cmd_basic_success_failure(tmp_path):
    log = str(tmp_path / 'out.log')
    assert agent._run_cmd('exit 0', log) is True
    assert agent._run_cmd('exit 1', log) is False


def test_run_cmd_reaps_backgrounded_child(tmp_path):
    """A command that backgrounds a long sleep and returns 0 must still leave no
    survivor: the group-kill stops the orphan before it can touch the marker."""
    marker = tmp_path / 'orphan_ran'
    log = str(tmp_path / 'out.log')
    # `echo` returns 0 immediately; the backgrounded subshell would create the
    # marker after 10s if it were allowed to keep running.
    cmd = f'(sleep 10; touch "{marker}") & echo started'
    assert agent._run_cmd(cmd, log) is True
    time.sleep(2)
    assert not marker.exists(), "orphaned background child survived _run_cmd"


def test_kill_process_group_idempotent_on_dead_group():
    # A pid that is not a live group leader must not raise.
    agent._kill_process_group(2_000_000_000)

"""Incremental bottom-up building: weave the Makefile one target per slice and
remember what's built so nothing is built/tested twice. Pure functions, no model.
"""

import os
import time

from mu.plan import Plan, Task
from mu import incremental as inc


# ── per-unit checks ───────────────────────────────────────────────────────────

def test_unit_check_command_per_language():
    assert inc.unit_check_command('app.py') == 'python3 -m py_compile app.py'
    assert inc.unit_check_command('src/list.c') == 'cc -fsyntax-only -I. src/list.c'
    assert inc.unit_check_command('main.cpp').startswith('c++ -fsyntax-only')
    # languages with no standalone unit check
    assert inc.unit_check_command('main.go') is None
    assert inc.unit_check_command('lib.rs') is None
    assert inc.unit_check_command('Program.cs') is None


# ── incremental Makefile weaving ──────────────────────────────────────────────

def test_makefile_targets_skips_variables_and_phony():
    mk = "CC := gcc\n.PHONY: all test\nall:\n\t$(CC) -o app app.c\ntest: all\n\t./app\n"
    assert inc.makefile_targets(mk) == ['all', 'test']
    assert inc.has_target(mk, 'test') and not inc.has_target(mk, 'CC')


def test_add_target_appends_when_absent_and_is_idempotent():
    mk = "all:\n\tcc -o app app.c\n"
    out = inc.add_target(mk, 'clean', 'rm -f app', phony=True)
    assert 'clean:' in out and 'rm -f app' in out
    assert '.PHONY:' in out and 'clean' in out.split('.PHONY:')[1].splitlines()[0]
    assert inc.add_target(out, 'clean', 'rm -f app', phony=True) == out   # idempotent


def test_add_target_leaves_existing_target_untouched():
    mk = "test:\n\t./run-the-real-thing\n"
    assert inc.add_target(mk, 'test', 'echo nope') == mk


def test_append_check_creates_then_accretes_then_dedups():
    mk = "all:\n\tcc -o app *.c\n"
    s1 = inc.append_check(mk, 'cc -fsyntax-only -I. list.c')
    assert 'check:' in s1 and '.PHONY:' in s1
    s2 = inc.append_check(s1, 'cc -fsyntax-only -I. main.c')
    # both checks now live under the one growing `check` target
    body = s2.split('check:')[1]
    assert 'list.c' in body and 'main.c' in body
    # idempotent: re-adding an existing line changes nothing ('not built twice')
    assert inc.append_check(s2, 'cc -fsyntax-only -I. main.c') == s2


def test_append_check_preserves_top_variable_assignments():
    # Regression (p3-sdl2): weaving must NOT prepend .PHONY to the top, which made a
    # makefile reflex tab-indent the CFLAGS/LDFLAGS assignments → $(CFLAGS) empty →
    # `cc -o main main.c` with no sdl2 flags → 'SDL2/SDL.h not found'.
    mk = ("CFLAGS  = $(shell sdl2-config --cflags)\n"
          "LDFLAGS = $(shell sdl2-config --libs)\n\n"
          "all: main\n\nmain: main.c\n\tcc $(CFLAGS) -o main main.c $(LDFLAGS)\n")
    out = inc.append_check(mk, 'cc -fsyntax-only -I. main.c')
    assert out.startswith('CFLAGS  = $(shell sdl2-config --cflags)\n')  # top untouched
    assert '\n\tCFLAGS' not in out and '\n\tLDFLAGS' not in out          # never indented
    assert 'check:' in out and '.PHONY: check' in out                   # target still woven
    # the real recipe's flags survive intact
    assert 'cc $(CFLAGS) -o main main.c $(LDFLAGS)' in out


def test_append_check_inserts_within_recipe_not_after_next_target():
    mk = "check:\n\tcc -fsyntax-only a.c\nall:\n\tcc -o app *.c\n"
    out = inc.append_check(mk, 'cc -fsyntax-only b.c')
    lines = out.splitlines()
    # b.c check must sit before the `all:` target, inside check's recipe
    assert lines.index('\tcc -fsyntax-only b.c') < lines.index('all:')


# ── the ledger ────────────────────────────────────────────────────────────────

def test_ledger_records_and_queries():
    led = inc.BuildLedger()
    led.record_built('list.c'); led.record_target('check'); led.record_gate(('k', ()))
    assert led.is_built('list.c') and led.has_target('check') and led.was_gated(('k', ()))
    assert not led.is_built('main.c')


def test_ledger_from_plan_seeds_built_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'list.c').write_text('int x;')
    p = Plan(tasks=[
        Task('list.c', done=True), Task('main.c', done=False),
        Task('test_main.c', done=True), Task('Makefile', done=True),
    ])
    led = inc.BuildLedger.from_plan(p)
    assert led.is_built('list.c')          # done + on disk + source
    assert not led.is_built('main.c')      # not done
    assert not led.is_built('test_main.c') # test, not a build slice


def test_gate_key_changes_when_a_file_is_edited(tmp_path):
    f = tmp_path / 'a.py'
    f.write_text('x = 1')
    k1 = inc.gate_key([str(f)], 'make test')
    time.sleep(0.01)
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))   # simulate an edit
    k2 = inc.gate_key([str(f)], 'make test')
    assert k1 != k2                         # edited state ⇒ must re-gate
    assert inc.gate_key([str(f)], 'make test') == k2          # unchanged ⇒ same key


# ── forward-dependency guard ──────────────────────────────────────────────────

def test_verifiable_now_false_until_all_source_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'list.c').write_text('int x;')
    p = Plan(tasks=[Task('list.c', done=True), Task('main.c', done=False),
                    Task('test_main.c', done=False)])
    assert inc.verifiable_now(p) is False    # main.c (a dependency) not on disk yet
    (tmp_path / 'main.c').write_text('int main(){}')
    assert inc.verifiable_now(p) is True      # all non-test source present
    assert inc.source_paths(p) == ['list.c', 'main.c']   # modules only (tests excluded)


def test_gate_paths_includes_tests_for_keying(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for f in ('list.c', 'main.c', 'test_main.c'):
        (tmp_path / f).write_text('x')
    p = Plan(tasks=[Task('list.c'), Task('main.c'), Task('test_main.c'),
                    Task('Makefile')])
    # a test file changes what `make test` does, so the gate key must include it
    assert inc.gate_paths(p) == ['list.c', 'main.c', 'test_main.c']

"""Iteration 1 of the scaffolding plan (docs/plans/scaffolding.md): the detector
and the offline/graceful guarantees. No real toolchain is invoked — `run` and
`which` are injected.
"""

from pathlib import Path

import pytest

from mu import scaffold
from mu.scaffold import Signal, detect, scaffold as do_scaffold


def sig(goal="", toolchains=(), test_command="", files=()):
    return Signal(goal=goal, toolchains=frozenset(toolchains),
                  test_command=test_command, files=tuple(files))


# ── detection: capability-only, general across phrasings (the honesty boundary) ─

def test_detect_xunit_from_generic_goal():
    # A synthetic, non-dojo goal must select the same recipe a dojo problem would.
    r = detect(sig("write an xUnit test project for a calculator library",
                   toolchains=["dotnet"]))
    assert r and r.name == "dotnet-xunit"


def test_detect_xunit_from_plan_signals_only():
    # p4-style: the goal never says "xunit"; the plan's test command + a Tests.cs
    # task carry the signal.
    r = detect(sig("write the fibonacci sequence using C#", toolchains=["dotnet"],
                   test_command="dotnet test", files=["Program.cs", "FibonacciTests.cs"]))
    assert r and r.name == "dotnet-xunit"


def test_detect_webapi_takes_precedence_over_xunit():
    r = detect(sig("ASP.NET Core minimal API with EF Core and an xUnit test project",
                   toolchains=["dotnet"], test_command="dotnet test"))
    assert r and r.name == "dotnet-webapi"


def test_detect_vite_vitest():
    r = detect(sig("Vue 3 app built with Vite, tested with Vitest",
                   toolchains=["node"]))
    assert r and r.name == "vite-vitest" and r.tier == "online"


def test_detect_cargo():
    r = detect(sig("a Rust CLI built with cargo", toolchains=["cargo"]))
    assert r and r.name == "cargo-bin"


def test_detect_no_stack_signal_returns_none():
    assert detect(sig("write a hello world program in C", toolchains=["clang"])) is None
    # node present but no Vite/Vitest/Vue → no scaffold
    assert detect(sig("a Node CLI todo manager with Jest", toolchains=["node"])) is None


def test_detect_requires_the_toolchain():
    # The words are there but the toolchain isn't installed → no match.
    assert detect(sig("an xUnit test project", toolchains=[])) is None


# ── flags & gating ────────────────────────────────────────────────────────────

def _ok_run(*a, **k):
    class P: returncode = 0
    return P()


def test_disabled_by_default_is_noop(monkeypatch):
    monkeypatch.delenv("MU_SCAFFOLD", raising=False)
    calls = []
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      run=lambda *a, **k: calls.append(a) or _ok_run(),
                      which=lambda b: "/usr/bin/" + b)
    assert res is None and calls == []   # never even probed


def test_offline_recipe_runs_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    (tmp_path / "App.csproj").write_text("<Project/>")
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=_ok_run,
                      which=lambda b: "/usr/bin/" + b)
    assert res and res.recipe == "dotnet-xunit" and res.tier == "offline"
    assert "App.csproj" in res.files


def test_online_recipe_skipped_unless_online_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    monkeypatch.delenv("MU_SCAFFOLD_ONLINE", raising=False)
    ran = []
    res = do_scaffold(sig("Vue 3 + Vite + Vitest", toolchains=["node"]),
                      workdir=str(tmp_path),
                      run=lambda *a, **k: ran.append(1) or _ok_run(),
                      which=lambda b: "/usr/bin/" + b)
    assert res is None and ran == []          # offline guarantee: no network call
    monkeypatch.setenv("MU_SCAFFOLD_ONLINE", "1")
    res = do_scaffold(sig("Vue 3 + Vite + Vitest", toolchains=["node"]),
                      workdir=str(tmp_path), run=_ok_run,
                      which=lambda b: "/usr/bin/" + b)
    assert res and res.recipe == "vite-vitest"


def test_scoped_out(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    monkeypatch.setenv("MU_SCAFFOLD_STACKS", "cargo-bin")
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=_ok_run,
                      which=lambda b: "/usr/bin/" + b)
    assert res is None   # dotnet-xunit not in the allowed scope


# ── graceful degradation: never raises, never blocks ──────────────────────────

def test_missing_binary_degrades(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=_ok_run, which=lambda b: None)
    assert res is None


def test_command_failure_degrades(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    class Fail:
        returncode = 1
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=lambda *a, **k: Fail(),
                      which=lambda b: "/usr/bin/" + b)
    assert res is None


def test_command_exception_degrades(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    def boom(*a, **k):
        raise OSError("toolchain blew up")
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=boom, which=lambda b: "/usr/bin/" + b)
    assert res is None

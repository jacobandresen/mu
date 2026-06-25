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
    # The command creates the csproj (as `dotnet new` would); the pre-run guard sees no
    # project beforehand, so it proceeds.
    def _run(*a, **k):
        (tmp_path / "App.csproj").write_text("<Project/>")
        return _ok_run()
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=_run,
                      which=lambda b: "/usr/bin/" + b)
    assert res and res.recipe == "dotnet-xunit" and res.tier == "offline"
    assert "App.csproj" in res.files


def test_skips_when_project_already_scaffolded(monkeypatch, tmp_path):
    # A later stage re-entering the same work dir: the owned artifact already exists, so
    # scaffold() does not re-run `dotnet new` (which would collide).
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    (tmp_path / "App.csproj").write_text("<Project/>")
    ran = []
    res = do_scaffold(sig("an xUnit test project", toolchains=["dotnet"]),
                      workdir=str(tmp_path), run=lambda *a, **k: ran.append(1) or _ok_run(),
                      which=lambda b: "/usr/bin/" + b)
    assert res is None and ran == []


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


# ── stage-aware detection (§3.2: the frontend must not be captured by webapi) ──

def test_detect_stage_backend_yields_dotnet():
    s = sig("ASP.NET Core minimal API with EF Core and an xUnit test project",
            toolchains=["dotnet", "node"], test_command="dotnet test")
    assert detect(s, stage="backend").name == "dotnet-webapi"


def test_detect_stage_model_yields_dotnet():
    # The architect files p10's EF/.NET data layer under the *model* stage, not "backend";
    # the dotnet recipes must be eligible there or scaffolding never fires (the smoke bug).
    s = sig("blog data layer: EF Core entities + SQLite DbContext, ASP.NET Core",
            toolchains=["dotnet", "node"], test_command="dotnet test")
    assert detect(s, stage="model").name == "dotnet-webapi"


def test_detect_stage_frontend_excludes_dotnet():
    # A full-stack signal: at the frontend stage only the JS recipe is eligible, even
    # though the dotnet-webapi predicate would otherwise match the shared goal.
    s = sig("ASP.NET Core API plus a Vue 3 app built with Vite and Vitest",
            toolchains=["dotnet", "node"], test_command="dotnet test && npx vitest run")
    assert detect(s, stage="frontend").name == "vite-vitest"
    assert detect(s, stage="backend").name == "dotnet-webapi"


def test_detect_unknown_stage_matches_none():
    s = sig("an xUnit test project", toolchains=["dotnet"])
    assert detect(s, stage="deploy") is None       # a stage with no recipe mapping
    # stage=None keeps the original all-recipes behaviour
    assert detect(s).name == "dotnet-xunit"


# ── webapi post-step D1/D2/D3 ──────────────────────────────────────────────────

_WEB_CSPROJ = ('<Project Sdk="Microsoft.NET.Sdk.Web">\n  <PropertyGroup>\n'
               '    <TargetFramework>net10.0</TargetFramework>\n  </PropertyGroup>\n</Project>\n')


def _webapi_run(tmp_path, add_ok=True, calls=None, sdk="10.0.109"):
    """Fake `run`: `dotnet new webapi -o .` lays a Sdk.Web csproj (named after the dir,
    as the real CLI does) + a Program.cs; `dotnet --version` reports the (grounded) SDK;
    `dotnet add package` succeeds or fails."""
    csproj = tmp_path / f"{tmp_path.name}.csproj"

    def _run(argv, *a, **k):
        if calls is not None:
            calls.append(tuple(argv))
        if argv[:2] == ["dotnet", "new"]:
            csproj.write_text(_WEB_CSPROJ)
            (tmp_path / "Program.cs").write_text("var app = WebApplication.Create();\napp.Run();\n")
            class P: returncode = 0
            return P()
        if argv[:2] == ["dotnet", "--version"]:
            class P: returncode = 0; stdout = sdk
            return P()
        if argv[:3] == ["dotnet", "add", "package"]:
            class P: returncode = 0 if add_ok else 1
            return P()
        class P: returncode = 0
        return P()
    return _run, csproj


def _webapi_sig(ef=True):
    goal = "ASP.NET Core minimal API" + (" with EF Core and SQLite" if ef else "")
    return sig(goal, toolchains=["dotnet"], test_command="dotnet test")


def test_webapi_d1_adds_prune_property(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    run, csproj = _webapi_run(tmp_path)         # SDK 10 ⇒ NETSDK1226 applies
    res = do_scaffold(_webapi_sig(ef=False), workdir=str(tmp_path), run=run,
                      which=lambda b: "/usr/bin/" + b, stage="backend")
    assert res and res.recipe == "dotnet-webapi"
    assert "<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>" in csproj.read_text()
    assert csproj.name in res.files            # the csproj is owned


def test_webapi_d1_grounded_skips_on_old_sdk(monkeypatch, tmp_path):
    # D1 is grounded to the real SDK: net8 doesn't trip NETSDK1226, so no prune patch.
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    run, csproj = _webapi_run(tmp_path, sdk="8.0.404")
    res = do_scaffold(_webapi_sig(ef=False), workdir=str(tmp_path), run=run,
                      which=lambda b: "/usr/bin/" + b, stage="backend")
    assert res and res.recipe == "dotnet-webapi"
    assert "AllowMissingPrunePackageData" not in csproj.read_text()
    assert csproj.name in res.files            # still owned (csproj restores as-is on net8)


def test_webapi_d2_adds_ef_packages_when_signalled(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    calls = []
    run, _ = _webapi_run(tmp_path, calls=calls)
    res = do_scaffold(_webapi_sig(ef=True), workdir=str(tmp_path), run=run,
                      which=lambda b: "/usr/bin/" + b, stage="backend")
    added = {c[3] for c in calls if c[:3] == ("dotnet", "add", "package")}
    assert "Microsoft.EntityFrameworkCore.Sqlite" in added
    assert res is not None                       # complete: csproj owned


def test_webapi_d2_not_added_without_ef_signal(monkeypatch, tmp_path):
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    calls = []
    run, _ = _webapi_run(tmp_path, calls=calls)
    do_scaffold(_webapi_sig(ef=False), workdir=str(tmp_path), run=run,
                which=lambda b: "/usr/bin/" + b, stage="backend")
    assert not any(c[:3] == ("dotnet", "add", "package") for c in calls)


def test_webapi_offline_degrade_still_owns_csproj(monkeypatch, tmp_path):
    # D2's add-package fails (cold offline cache): the csproj is STILL owned (D1 made it
    # restore) — the degrade is informational, never an ownership drop (scaffolding.md §4).
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    run, csproj = _webapi_run(tmp_path, add_ok=False)
    res = do_scaffold(_webapi_sig(ef=True), workdir=str(tmp_path), run=run,
                      which=lambda b: "/usr/bin/" + b, stage="backend")
    assert res is not None and csproj.name in res.files
    assert "<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>" in csproj.read_text()


def test_scaffold_owned_files_match_plan_and_spare_program_cs(monkeypatch, tmp_path):
    # The owned-path/plan-name invariant (advisor): on a real `dotnet new` layout the
    # scaffold's csproj name matches the plan's auto-grounded `{dir}.csproj` task, so
    # reconcile marks it done; Program.cs is created-but-unowned, so it stays a model task.
    from mu.agent import reconcile_provided
    from mu.plan import parse
    monkeypatch.setenv("MU_SCAFFOLD", "1")
    run, csproj = _webapi_run(tmp_path, add_ok=False)
    res = do_scaffold(_webapi_sig(ef=True), workdir=str(tmp_path), run=run,
                      which=lambda b: "/usr/bin/" + b, stage="backend")
    pf = tmp_path / "PLAN.md"
    pf.write_text(f"## Files\n- [ ] {csproj.name} project file\n- [ ] Program.cs the host\n")
    done = {t.file_path: t.done
            for t in reconcile_provided(str(pf), parse(str(pf)), owned_paths=set(res.files)).tasks}
    assert done[csproj.name] is True            # scaffold-owned ⇒ writer skips it
    assert done["Program.cs"] is False          # D3: model authors the host body

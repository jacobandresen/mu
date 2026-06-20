"""Step 0.4 — S3 reconcile_provided (one provided-files routine) and S4
is_fullstack_dotnet_vue (the shared full-stack detector).

reconcile_provided with owned_paths=None must reproduce the legacy
fixture-detection exactly (I1: byte-identical); with an explicit set it marks
exactly those paths. The detector fires on a dotnet+vue goal, not on a trivial one.
"""
from mu.agent import reconcile_provided
from mu.plan import parse
from mu.scaffold import Signal, is_fullstack_dotnet_vue

PLAN = "- [ ] Makefile build it\n- [ ] app.py the app\n"


def _plan(tmp_path):
    pf = tmp_path / "PLAN.md"
    pf.write_text(PLAN)
    return str(pf)


def test_legacy_marks_existing_nonempty_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = _plan(tmp_path)
    (tmp_path / "Makefile").write_text("all:\n\techo hi\n")   # provided, non-empty
    done = {t.file_path: t.done for t in reconcile_provided(pf, parse(pf)).tasks}
    assert done["Makefile"] is True       # provided -> skipped
    assert done["app.py"] is False        # model still owns it


def test_legacy_empty_file_not_marked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = _plan(tmp_path)
    (tmp_path / "Makefile").write_text("")                    # empty != provided
    done = {t.file_path: t.done for t in reconcile_provided(pf, parse(pf)).tasks}
    assert done["Makefile"] is False


def test_explicit_owned_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = _plan(tmp_path)
    # explicit set marks those paths whether or not they exist on disk
    done = {t.file_path: t.done
            for t in reconcile_provided(pf, parse(pf), owned_paths={"app.py"}).tasks}
    assert done["app.py"] is True
    assert done["Makefile"] is False


def test_empty_owned_set_is_noop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = _plan(tmp_path)
    p = parse(pf)
    assert reconcile_provided(pf, p, owned_paths=set()) is p   # nothing marked -> same plan


def test_fullstack_detector_fires_on_dotnet_vue():
    fs = Signal(goal="ASP.NET Core minimal API plus a Vue 3 + Vite frontend",
                toolchains=frozenset({"dotnet", "node"}),
                test_command="dotnet test && npx vitest run")
    assert is_fullstack_dotnet_vue(fs) is True


def test_fullstack_detector_quiet_on_trivial_and_partial():
    assert is_fullstack_dotnet_vue(
        Signal(goal="hello world", toolchains=frozenset({"c"}))) is False
    # dotnet backend alone (no node/vue frontend) is not a full stack
    assert is_fullstack_dotnet_vue(
        Signal(goal="a dotnet web api", toolchains=frozenset({"dotnet"}))) is False
    # node+vue but no dotnet either
    assert is_fullstack_dotnet_vue(
        Signal(goal="a vue todo app", toolchains=frozenset({"node"}))) is False

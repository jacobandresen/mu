"""Project scaffolding from official templates (docs/plans/scaffolding.md, TOOLS.md §6.1).

When a goal targets a scaffold-able stack, an official template lays down the project
skeleton so the model fills only the logic — removing the *structural* failure classes
(CS0017/MSB1003/NU1202/NETSDK1226, Vitest config) by construction.

This module is the decision + execution core; `agent.run_staged` calls `scaffold()` at the
top of each stage behind `MU_SCAFFOLD` (opt-in, default off). The measured p10 A/B
(ablations.md) confirmed it clears the NU1202/NETSDK1226 restore wall (12/15 → 0/15). Two
principles hold throughout:

* **Offline-first.** `dotnet new` and `cargo new` ship with their SDK and need no
  network (tier ``"offline"``); the Vite recipe fetches a template (tier
  ``"online"``) and is gated behind a second opt-in flag. mu must run fully
  offline, so the online tier is never required.
* **Honesty.** Detection keys on *capabilities named in the goal/plan* (toolchain,
  framework, test command, filenames) — never a dojo problem id. Scaffolding a
  stack is general; scaffolding "problem p10" would measure the test author.

Default off: with ``MU_SCAFFOLD`` unset, `scaffold()` is a no-op and behaviour is
identical to today.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# ── recipe model ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Recipe:
    """A template invocation for one stack.

    ``signal`` is a compiled predicate over the detection signal (see
    :func:`detect`). ``command`` is the template command run in the work dir.
    ``owns`` are glob patterns the scaffold is authoritative for (config /
    manifest / entry wiring) — the writer is told these tasks are done; the
    model still authors the source/test files the scaffold does not own.
    """
    name: str
    tier: str                       # "offline" | "online"
    binary: str                     # the CLI that must be present (shutil.which)
    command: tuple[str, ...]        # argv run in the work dir
    owns: tuple[str, ...]           # glob patterns the scaffold owns
    detect: Callable[["Signal"], bool] = field(repr=False)
    # Optional post-`dotnet new` step (D1/D2): given (sig, workdir, run) it patches the
    # generated project so it actually restores. D1 (the prune-data property) is a local
    # edit that always succeeds and is what makes the csproj restorable, so the manifest
    # is **owned regardless** of the return. The bool only *reports* completeness: True =
    # fully ready; False = a degrade (e.g. D2's EF package un-addable on a cold offline
    # cache) — recorded/logged, never an ownership drop. On False the run falls back to the
    # baseline csproj (ground_plan rewrites the EF-less project), i.e. degrade ≈ a
    # non-scaffolded run (graceful degrade, scaffolding.md §4). Default None ⇒ none.
    post: Optional[Callable[["Signal", str, Callable], bool]] = field(
        default=None, repr=False)


@dataclass
class Signal:
    """What detection reads — capability facts about the task, never its id."""
    goal: str = ""
    toolchains: frozenset[str] = frozenset()
    test_command: str = ""
    files: tuple[str, ...] = ()

    @property
    def haystack(self) -> str:
        """Lower-cased goal + test command + filenames, for keyword matching."""
        return " ".join([self.goal, self.test_command, *self.files]).lower()


@dataclass(frozen=True)
class ScaffoldResult:
    recipe: str
    tier: str
    files: tuple[str, ...]          # files the scaffold created/owns, repo-relative


# ── detection signals (capability-only; the honesty boundary) ─────────────────

def _has(sig: "Signal", *terms: str) -> bool:
    return any(t in sig.haystack for t in terms)


def _is_dotnet_test(sig: "Signal") -> bool:
    # An xUnit/dotnet-test project: the SDK auto-generates a second entry point
    # (CS0017) unless the csproj is scaffolded correctly.
    if "dotnet" not in sig.toolchains:
        return False
    if "dotnet test" in sig.test_command.lower():
        return True
    if _has(sig, "xunit", "nunit", "mstest"):
        return True
    return any(re.search(r"(test|tests)\.cs$", f, re.I) for f in sig.files)


def _is_dotnet_web(sig: "Signal") -> bool:
    return "dotnet" in sig.toolchains and _has(
        sig, "asp.net", "aspnet", "minimal api", "web api", "webapi", "ef core",
        "entity framework")


def _is_cargo_bin(sig: "Signal") -> bool:
    return "cargo" in sig.toolchains and _has(sig, "cargo", "rust")


def _is_vite_vitest(sig: "Signal") -> bool:
    return "node" in sig.toolchains and "vite" in sig.haystack and _has(
        sig, "vitest", "vue", "@vue/test-utils")


# ── webapi post-step (D1/D2): make `dotnet new webapi` actually restore ────────

# The EF/SQLite package the blog backend needs but `dotnet new webapi` omits (D2).
# Sqlite only — it transitively brings EF Core itself; Design is migrations-only and
# every extra package is one more thing that must be cached to avoid the cold-cache
# degrade. Left unpinned: restore resolves a version against the installed SDK, rather
# than hard-coding a major that may not be in the local NuGet cache (scaffolding.md §2 D2).
_EF_PACKAGES: tuple[str, ...] = (
    "Microsoft.EntityFrameworkCore.Sqlite",
)


def _needs_ef(sig: "Signal") -> bool:
    """The goal names an EF/SQLite data layer (the only trigger for D2 — never an id)."""
    return _has(sig, "ef core", "entity framework", "entityframework", "sqlite", "dbcontext")


def _dotnet_sdk_major(run: Callable) -> Optional[int]:
    """Major version of the installed dotnet SDK (e.g. 10), or None if unknown.

    Grounds the scaffold in the *real* toolchain — the SDK that actually ran
    `dotnet new` decides which net version the csproj targets and whether the
    NETSDK1226 prune-data quirk applies. Mirrors
    ``fix_csharp_uninstalled_tfm._installed_sdk_major``; uses the injected ``run``
    so it stays testable and consistent with the rest of the post-step."""
    try:
        proc = run(["dotnet", "--version"], capture_output=True, text=True, timeout=10)
        major = (getattr(proc, "stdout", "") or "").strip().split(".")[0]
        return int(major) if major.isdigit() else None
    except Exception:
        return None


def _webapi_post(sig: "Signal", workdir: str, run: Callable) -> bool:
    """Make the `dotnet new webapi` project restorable + EF-ready (scaffolding.md §2).

    **D1** — add ``<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>`` to the
    ``Microsoft.NET.Sdk.Web`` project, but **only when the installed SDK major is ≥ 9** (the
    verified NETSDK1226 trigger — grounded in the real toolchain, `dotnet --version`, not
    assumed). A plain-Sdk test project, or an older SDK that doesn't trip NETSDK1226, is left
    untouched. A local edit that always succeeds, so the csproj restores at the SDK's net
    version (which `dotnet new` already targets — TFM is grounded too).

    **D2** — when the goal signals EF/SQLite, ``dotnet add package`` the EF package, letting
    the resolver pick the version. Returns True when complete; False when the add fails (cold
    NuGet cache, offline). On False the run falls back to the baseline: ``ground_plan``
    (plan.py) sees the EF-less csproj and rewrites it with the model-baseline EF project, so
    the slice degrades to a non-scaffolded run (§4's honest floor) rather than the scaffold's
    csproj surviving — the happy path (EF present ⇒ no rewrite) keeps this verified one.
    """
    base = Path(workdir)
    # D1 is SDK-grounded: the prune-data property only matters on net9+ SDKs. Query the real
    # SDK once; skip the patch entirely on older (or unknown) SDKs that never trip NETSDK1226.
    sdk_major = _dotnet_sdk_major(run)
    for csproj in base.rglob("*.csproj"):
        if any(part in csproj.parts for part in ("obj", "bin")):
            continue
        try:
            text = csproj.read_text()
        except OSError:
            continue
        if 'Sdk="Microsoft.NET.Sdk.Web"' not in text or "AllowMissingPrunePackageData" in text:
            continue
        if sdk_major is None or sdk_major < 9:
            continue   # grounded: no NETSDK1226 on this SDK ⇒ no patch needed
        prop = "<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>"
        if "</PropertyGroup>" in text:
            patched = text.replace("</PropertyGroup>", f"  {prop}\n  </PropertyGroup>", 1)
        else:  # no PropertyGroup (unusual) — add one right after the opening <Project> tag
            patched = re.sub(r"(<Project[^>]*>)", rf"\1\n  <PropertyGroup>{prop}</PropertyGroup>",
                             text, count=1)
        try:
            csproj.write_text(patched)
        except OSError:
            pass
    if _needs_ef(sig):
        for pkg in _EF_PACKAGES:
            try:
                proc = run(["dotnet", "add", "package", pkg], cwd=workdir,
                           capture_output=True, text=True, timeout=120)
            except Exception:
                return False
            if getattr(proc, "returncode", 1) != 0:
                return False
    return True


# Order matters: the more specific .NET web recipe is tried before the bare test
# recipe so an ASP.NET+xUnit goal scaffolds the web project, not just a test one.
RECIPES: tuple[Recipe, ...] = (
    Recipe("dotnet-webapi", "offline", "dotnet",
           ("dotnet", "new", "webapi", "-o", "."),
           owns=("*.csproj",), detect=_is_dotnet_web, post=_webapi_post),
    Recipe("dotnet-xunit", "offline", "dotnet",
           ("dotnet", "new", "xunit", "-o", "."),
           owns=("*.csproj",), detect=_is_dotnet_test),
    Recipe("cargo-bin", "offline", "cargo",
           ("cargo", "init", "--bin"),
           owns=("Cargo.toml",), detect=_is_cargo_bin),
    Recipe("vite-vitest", "online", "npm",
           ("npm", "create", "vite@latest", ".", "--", "--template", "vue-ts"),
           owns=("package.json", "vite.config.ts", "vite.config.js", "tsconfig.json"),
           detect=_is_vite_vitest),
)


def is_fullstack_dotnet_vue(sig: Signal) -> bool:
    """A staged full-stack goal: a .NET backend **and** a Vite/Vue frontend (p10's
    shape). The shared capability check (S4) that gates the full-stack contract and
    the four-layer board — keyed on toolchains/keywords, never a problem id."""
    return ("dotnet" in sig.toolchains and "node" in sig.toolchains
            and any(k in sig.haystack for k in ("vue", "vite")))


# Which recipes each stage may use (stage-aware detect, scaffolding.md §3.2). The rule is
# simply: the **frontend** stage gets the JS app only — so a dotnet-* recipe can never
# capture it (the bug that sank the first wiring) — and **every other** stage gets the
# native/offline recipes. The architect names p10's .NET/EF layer the *model* stage (the
# "data layer", which for a blog is the EF + SQLite + backend-test project), not "backend",
# so the dotnet recipes must be eligible there too or scaffolding never fires (verified:
# p10's csproj + ApiTests.cs build under PLAN-model.md). webapi still takes precedence over
# the bare test project per RECIPES order; xunit fires for a test-only dotnet goal (p4).
_OFFLINE_NATIVE = ("dotnet-webapi", "dotnet-xunit", "cargo-bin")
_STAGE_RECIPES: dict[str, tuple[str, ...]] = {
    "model": _OFFLINE_NATIVE,
    "backend": _OFFLINE_NATIVE,
    "frontend": ("vite-vitest",),
}


def detect(sig: Signal, stage: Optional[str] = None) -> Optional[Recipe]:
    """The first recipe whose capability predicate matches, or None.

    Pure and side-effect-free — the honesty-critical core. A synthetic, non-dojo
    goal for the same stack must select the same recipe; a goal with no stack
    signal must select none.

    With ``stage`` set, only recipes eligible for that stage are considered, so the
    frontend stage is never captured by ``dotnet-webapi`` (scaffolding.md §3.2); an
    unrecognised stage matches nothing. ``stage=None`` considers all recipes (a
    non-staged run), preserving the original behaviour.
    """
    eligible = RECIPES
    if stage is not None:
        allowed = _STAGE_RECIPES.get(stage, ())
        eligible = tuple(r for r in RECIPES if r.name in allowed)
    return next((r for r in eligible if r.detect(sig)), None)


# ── flags ─────────────────────────────────────────────────────────────────────

def enabled() -> bool:
    """Master switch. Off by default ⇒ scaffolding is a no-op."""
    return os.environ.get("MU_SCAFFOLD") == "1"


def online_enabled() -> bool:
    """Whether the network tier may run. Off by default; the offline tier is
    unaffected by this flag."""
    return os.environ.get("MU_SCAFFOLD_ONLINE") == "1"


def _scoped_out(recipe: Recipe) -> bool:
    """MU_SCAFFOLD_STACKS (comma-separated) restricts which recipes may fire,
    for A/B scoping. Empty ⇒ all recipes eligible."""
    scope = {s.strip() for s in os.environ.get("MU_SCAFFOLD_STACKS", "").split(",") if s.strip()}
    return bool(scope) and recipe.name not in scope


# ── execution (graceful: never raises, never blocks a run) ────────────────────

def scaffold(sig: Signal, workdir: str = ".",
             run: Callable = subprocess.run,
             which: Callable[[str], Optional[str]] = shutil.which,
             stage: Optional[str] = None) -> Optional[ScaffoldResult]:
    """Lay down the template for ``sig``'s stack into ``workdir``, or return None.

    Returns None (and changes nothing) when: scaffolding is disabled, no recipe
    matches (for ``stage``), the recipe is scoped out, its CLI is absent, the online
    tier is needed but not enabled, or the command fails. Every one of these degrades
    to the baseline path — the model writes the structure itself. Scaffolding can only
    add a head start, never block a run.
    """
    if not enabled():
        return None
    recipe = detect(sig, stage)
    if recipe is None or _scoped_out(recipe):
        return None
    if recipe.tier == "online" and not online_enabled():
        return None
    if which(recipe.binary) is None:
        return None
    # Already scaffolded — a later stage (e.g. backend after model) re-entering the same
    # work dir. Re-running `dotnet new` over an existing project would error or collide, so
    # leave the laid-down project in place and let the legacy reconcile path handle it.
    if _owned_files(recipe, workdir):
        return None
    try:
        proc = run(list(recipe.command), cwd=workdir,
                   capture_output=True, text=True, timeout=120)
        if getattr(proc, "returncode", 1) != 0:
            return None
    except Exception:
        return None
    # Post-step (D1/D2): patch the generated project so it actually restores. D1 always
    # succeeds, so the manifest is owned either way; a False return is the offline EF
    # degrade — reported, never an ownership change (scaffolding.md §4).
    if recipe.post is not None:
        try:
            complete = recipe.post(sig, workdir, run)
        except Exception:
            complete = False
        if not complete:
            print(f"==> [mu-agent] scaffold: {recipe.name} degraded — packages un-addable "
                  f"(offline cache); falling back to the baseline project.", flush=True)
    created = _owned_files(recipe, workdir)
    return ScaffoldResult(recipe.name, recipe.tier, created)


def _owned_files(recipe: Recipe, workdir: str) -> tuple[str, ...]:
    """Files matching the recipe's ``owns`` globs that now exist in ``workdir``."""
    base = Path(workdir)
    found: list[str] = []
    for pattern in recipe.owns:
        found += [str(p.relative_to(base)) for p in base.rglob(pattern) if p.is_file()]
    return tuple(sorted(set(found)))

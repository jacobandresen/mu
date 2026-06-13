"""Project scaffolding from official templates — iteration 1: detection + recipes.

Implements the offline-first core of [docs/plans/scaffolding.md] (TOOLS.md §6.1):
when a goal targets a scaffold-able stack, an official template can lay down the
project skeleton so the model fills only the logic — removing the *structural*
failure classes (CS0017/MSB1003/NU1202, Vitest config) by construction.

This module is the decision + execution core. It is **not yet wired** into the
agent (that is iteration 2); nothing in the hot path imports it. Two principles
hold from the start:

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


# Order matters: the more specific .NET web recipe is tried before the bare test
# recipe so an ASP.NET+xUnit goal scaffolds the web project, not just a test one.
RECIPES: tuple[Recipe, ...] = (
    Recipe("dotnet-webapi", "offline", "dotnet",
           ("dotnet", "new", "webapi", "-o", "."),
           owns=("*.csproj",), detect=_is_dotnet_web),
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


def detect(sig: Signal) -> Optional[Recipe]:
    """The first recipe whose capability predicate matches, or None.

    Pure and side-effect-free — the honesty-critical core. A synthetic, non-dojo
    goal for the same stack must select the same recipe; a goal with no stack
    signal must select none.
    """
    return next((r for r in RECIPES if r.detect(sig)), None)


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
             which: Callable[[str], Optional[str]] = shutil.which) -> Optional[ScaffoldResult]:
    """Lay down the template for ``sig``'s stack into ``workdir``, or return None.

    Returns None (and changes nothing) when: scaffolding is disabled, no recipe
    matches, the recipe is scoped out, its CLI is absent, the online tier is
    needed but not enabled, or the command fails. Every one of these degrades to
    the baseline path — the model writes the structure itself. Scaffolding can
    only add a head start, never block a run.
    """
    if not enabled():
        return None
    recipe = detect(sig)
    if recipe is None or _scoped_out(recipe):
        return None
    if recipe.tier == "online" and not online_enabled():
        return None
    if which(recipe.binary) is None:
        return None
    try:
        proc = run(list(recipe.command), cwd=workdir,
                   capture_output=True, text=True, timeout=120)
        if getattr(proc, "returncode", 1) != 0:
            return None
    except Exception:
        return None
    created = _owned_files(recipe, workdir)
    return ScaffoldResult(recipe.name, recipe.tier, created)


def _owned_files(recipe: Recipe, workdir: str) -> tuple[str, ...]:
    """Files matching the recipe's ``owns`` globs that now exist in ``workdir``."""
    base = Path(workdir)
    found: list[str] = []
    for pattern in recipe.owns:
        found += [str(p.relative_to(base)) for p in base.rglob(pattern) if p.is_file()]
    return tuple(sorted(set(found)))

"""Incremental, bottom-up building — the *runtime* side of the build-order design
criterion (``plan.build_order`` is the *ordering* side).

As each slice lands, weave its check into the Makefile (grown one target per step,
never an up-front blob or a trailing task) and gate it — while a :class:`BuildLedger`
remembers what is already built and verified so nothing is built or tested twice
(§0.2 composition: slice N rests on slices 1..N-1).

Everything here is pure and idempotent; ``agent.run`` drives it behind the
``MU_BUILD_ORDER`` flag, so with the flag off the agent is byte-identical (I1).
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# A target definition line `name:` — not a variable assignment (`:=`, `=`) nor `::`.
_TARGET_LINE_RE = re.compile(r'^([A-Za-z_.][A-Za-z0-9._-]*)\s*:(?![=:])')

# Cheap, dependency-free per-unit checks: verify the slice you just built in
# isolation, without needing a not-yet-written sibling (no forward dependency).
# Languages whose unit can't be checked alone (Go/Rust/C# build the whole package)
# are absent — their existing lint/test gates stay the authority.
_UNIT_CHECK = {
    '.py': 'python3 -m py_compile {f}',
    '.c': 'cc -fsyntax-only -I. {f}',
    '.cpp': 'c++ -fsyntax-only -I. {f}',
    '.cc': 'c++ -fsyntax-only -I. {f}',
    '.cxx': 'c++ -fsyntax-only -I. {f}',
}


def unit_check_command(path: str) -> str | None:
    """A cheap, dependency-free check that the slice at *path* is well-formed, or
    None when the language has no standalone unit check."""
    tmpl = _UNIT_CHECK.get(Path(path).suffix.lower())
    return tmpl.format(f=path) if tmpl else None


# ── incremental Makefile: weave one target per slice, idempotently ────────────

def makefile_targets(text: str) -> list[str]:
    """Target names defined in *text* (excludes variable assignments and .PHONY)."""
    return [m.group(1) for line in text.splitlines()
            if (m := _TARGET_LINE_RE.match(line)) and m.group(1) != '.PHONY']


def has_target(text: str, name: str) -> bool:
    return name in makefile_targets(text)


def _extend_phony(text: str, name: str) -> tuple[str, bool]:
    """Add *name* to an EXISTING .PHONY line, in place. Returns (text, handled);
    handled is False when there is no .PHONY line to extend — in which case the
    caller appends a fresh `.PHONY: name` at the END (never prepends to the top:
    a top-of-file .PHONY made a makefile reflex tab-indent the following variable
    assignments, breaking $(CFLAGS) — the p3-sdl2 regression)."""
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('.PHONY:'):
            if name in ln.split(':', 1)[1].split():
                return text, True
            lines[i] = ln.rstrip('\n').rstrip() + f' {name}\n'
            return ''.join(lines), True
    return text, False


def add_target(text: str, name: str, recipe, *, prereqs=(), phony=False) -> str:
    """Append a target with *recipe* (a str or a list of recipe lines) if it is
    absent. Idempotent: an existing target is left untouched. Recipe lines get a
    leading tab. With phony=True the target is registered in .PHONY — extending an
    existing .PHONY line in place, else adding `.PHONY: name` with the target block
    at the END so the file's existing structure (top-level variable assignments)
    is never disturbed."""
    if has_target(text, name):
        return text
    recipe_lines = [recipe] if isinstance(recipe, str) else list(recipe)
    body = ''.join(f'\t{ln}\n' for ln in recipe_lines)
    prereq_str = (' ' + ' '.join(prereqs)) if prereqs else ''
    out, phony_prefix = text, ''
    if phony:
        out, handled = _extend_phony(out, name)
        if not handled:
            phony_prefix = f'.PHONY: {name}\n'
    if out and not out.endswith('\n'):
        out += '\n'
    if out and not out.endswith('\n\n'):
        out += '\n'
    return out + phony_prefix + f'{name}:{prereq_str}\n{body}'


def append_check(text: str, recipe_line: str, target: str = 'check') -> str:
    """Accrete *recipe_line* into a phony *target* (default 'check'), creating it on
    first use. Idempotent — a recipe line already present is never added twice
    ('not built twice'). This is how the Makefile grows one step per slice."""
    if not has_target(text, target):
        return add_target(text, target, recipe_line, phony=True)
    if any(ln.rstrip('\n') == f'\t{recipe_line}' for ln in text.splitlines()):
        return text                                  # already present — idempotent
    lines = text.splitlines(keepends=True)
    ti = next((i for i, l in enumerate(lines)
               if (m := _TARGET_LINE_RE.match(l)) and m.group(1) == target), None)
    if ti is None:
        return add_target(text, target, recipe_line, phony=True)
    j = ti + 1
    while j < len(lines) and lines[j].startswith('\t'):
        j += 1
    lines.insert(j, f'\t{recipe_line}\n')
    return ''.join(lines)


# ── the ledger: what this run has already built / verified ────────────────────

@dataclass
class BuildLedger:
    """Per-run memory so a later slice rests on earlier ones instead of redoing
    them. ``built`` = source files written; ``targets`` = Makefile targets present;
    ``gated`` = (command, build-state) keys already verified green."""
    built: set = field(default_factory=set)
    targets: set = field(default_factory=set)
    gated: set = field(default_factory=set)

    def record_built(self, path: str) -> None:
        self.built.add(path)

    def is_built(self, path: str) -> bool:
        return path in self.built

    def record_target(self, name: str) -> None:
        self.targets.add(name)

    def has_target(self, name: str) -> bool:
        return name in self.targets

    def record_gate(self, key) -> None:
        self.gated.add(key)

    def was_gated(self, key) -> bool:
        return key in self.gated

    @classmethod
    def from_plan(cls, p, makefile: str = 'Makefile') -> 'BuildLedger':
        from mu.plan import is_test_file, is_build_file
        built = {t.file_path for t in p.tasks
                 if t.done and not is_test_file(t.file_path)
                 and not is_build_file(t.file_path) and Path(t.file_path).exists()}
        try:
            targets = set(makefile_targets(Path(makefile).read_text()))
        except OSError:
            targets = set()
        return cls(built=built, targets=targets)


def gate_key(paths, cmd: str) -> tuple:
    """A content-sensitive key for 'this command over this build state': each path's
    mtime is included, so a repair edit invalidates the prior green (forcing a
    re-gate) while an unchanged state is recognised and skipped ('not built twice')."""
    stamp = []
    for pth in sorted(set(paths)):
        try:
            stamp.append((pth, round(os.path.getmtime(pth), 3)))
        except OSError:
            stamp.append((pth, None))
    return (cmd, tuple(stamp))


def verifiable_now(p) -> bool:
    """True when every non-test, non-build source task is already on disk — so
    building or testing the composition can't hit a forward dependency (a module a
    later slice will write). The precondition for gating the composed slice early."""
    from mu.plan import is_test_file, is_build_file
    for t in p.tasks:
        if t.done or is_test_file(t.file_path) or is_build_file(t.file_path):
            continue
        if not Path(t.file_path).exists():
            return False
    return True


def source_paths(p):
    """Existing non-test, non-build source files — the modules a later slice may
    depend on (used by verifiable_now)."""
    from mu.plan import is_test_file, is_build_file
    return [t.file_path for t in p.tasks
            if not is_test_file(t.file_path) and not is_build_file(t.file_path)
            and Path(t.file_path).exists()]


def gate_paths(p):
    """Existing non-build files (source *and* tests) — everything a test-command
    result depends on, so the gate_key over this set re-gates when a test file is
    added or any input edited, but not when nothing relevant changed."""
    from mu.plan import is_build_file
    return [t.file_path for t in p.tasks
            if not is_build_file(t.file_path) and Path(t.file_path).exists()]

"""Problem representation: PLAN.md parsing and manipulation.

In AIMA terms ``PLAN.md`` is the agent's **plan** — a goal (``## Summary``), an
action sequence (``## Files`` checklist), and a goal test (``## Test Command``).
``plan.parse`` is the problem reader; ``next_task`` selects the next action;
``mark_task_done`` updates the state after execution. The normalizers
(``strip_thinking_artifacts``, ``normalize_embedded_files``, etc.) are plan
hygiene that keeps the problem representation well-formed.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_TASK_RE = re.compile(r'^- \[([ x~])\] (\S+)(.*)$')
_THINKING_RE = re.compile(r'\s?/think\s?|\s?</?think(ing)?>\s?')
_RUNTIME_EXTS = {'db', 'sqlite', 'sqlite3', 'o', 'obj', 'pyc', 'class', 'bin'}
_BUILD_NAMES = {
    'Makefile', 'CMakeLists.txt', 'setup.py', 'Cargo.toml',
    'build.sh', 'package.json', 'pyproject.toml', 'meson.build', 'go.mod',
}
_EXT_LANGUAGE: dict[str, str] = {
    '.py': 'Python',
    '.go': 'Go',
    '.rs': 'Rust',
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++', '.hpp': 'C++',
    '.cs': 'C#',
    '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    '.rb': 'Ruby',
    '.java': 'Java',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.pas': 'Pascal', '.pp': 'Pascal',
    '.lua': 'Lua',
    '.php': 'PHP',
    '.ex': 'Elixir', '.exs': 'Elixir',
    '.hs': 'Haskell',
    '.ml': 'OCaml', '.mli': 'OCaml',
    '.fs': 'F#', '.fsx': 'F#',
    '.scala': 'Scala',
    '.nim': 'Nim',
    '.zig': 'Zig',
}


@dataclass
class Task:
    file_path: str
    description: str = ''
    done: bool = False
    in_progress: bool = False


@dataclass
class Plan:
    tasks: list[Task] = field(default_factory=list)
    test_command: str = ''
    plan_context: str = ''


def parse(path: str) -> Plan:
    """Read and parse a PLAN.md file; return an empty Plan on missing file."""
    try:
        return parse_content(Path(path).read_text())
    except OSError:
        return Plan()


_MALFORMED_TASK_RE = re.compile(r'^[\s-]+(\[[ x~]\]\s+\S+.*)')


def _clean_filename_token(token: str) -> str:
    """Strip markdown emphasis/code markers a planner may wrap a filename in.

    Granite and other small models often emit ``- [ ] **package.json** — …`` or
    ``*main.go*``; the bold/italic markers must come off or the writer tries to
    create a literally-named ``**package.json**`` file. Only *paired* surrounding
    markers are removed, longest first, so legitimate names survive — e.g.
    ``__init__.py`` (no trailing ``__``) and ``_private.py`` are untouched.
    """
    s = token.strip()
    for marker in ('**', '__', '*', '_', '`'):
        while len(s) > 2 * len(marker) and s.startswith(marker) and s.endswith(marker):
            s = s[len(marker):-len(marker)].strip()
    return s.strip('`')


def parse_content(content: str) -> Plan:
    """Parse PLAN.md text into a Plan dataclass."""
    lines = content.splitlines()
    plan = Plan()
    for line in lines:
        # Normalize malformed task lines like '- - [ ] file' or '  - [ ] file'
        # where leading noise prevents the standard regex from matching.
        m = _MALFORMED_TASK_RE.match(line)
        if m and not line.startswith('- ['):
            line = '- ' + m.group(1)
        task_match = _TASK_RE.match(line)
        if not task_match:
            continue
        status, file_path, raw_desc = (
            task_match.group(1),
            task_match.group(2),
            task_match.group(3).strip(),
        )
        # Planners sometimes wrap the filename in backticks or markdown emphasis
        # (`file`, **file**, *file*) because the prompt encourages markup for
        # entity names. Strip so the captured token is a real path the writer
        # can open.
        file_path = _clean_filename_token(file_path)
        desc = ''
        if '—' in raw_desc:
            desc = raw_desc[raw_desc.index('—') + 1:].strip()
        elif '-' in raw_desc:
            desc = raw_desc[raw_desc.index('-') + 1:].strip()
        plan.tasks.append(Task(file_path, desc, done=(status == 'x'), in_progress=(status == '~')))
    plan.test_command = _extract_test_command(lines)
    plan.plan_context = _extract_plan_context(lines)
    return plan


def _extract_test_command(lines: list[str]) -> str:
    in_section = False
    for line in lines:
        if re.match(r'^##\s+Test Command\s*$', line):
            in_section = True
            continue
        if in_section and line.startswith('## '):
            break
        if in_section:
            stripped = line.strip()
            if stripped.startswith('```'):  # skip fence open/close markers
                continue
            t = stripped.strip('`').strip()
            if t:
                return t
    return ''


def _extract_plan_context(lines: list[str]) -> str:
    want = {'Summary', 'Files', 'Test Command', 'Dependencies', 'Notes'}
    buf = []
    in_section = False
    for line in lines:
        m = re.match(r'^## ([A-Za-z ]+)\s*$', line)
        if m:
            in_section = m.group(1).strip() in want
        if in_section:
            buf.append(line)
    return '\n'.join(buf)


def next_task(p: Plan) -> Optional[Task]:
    """Return the first pending (not done, not in-progress) task, or None."""
    return next((t for t in p.tasks if not t.done and not t.in_progress), None)


def tasks_remaining(p: Plan) -> bool:
    """Return True if the plan has at least one task that isn't done."""
    return next_task(p) is not None


def count_tasks(p: Plan) -> tuple[int, int]:
    """Return (total_tasks, completed_tasks) for the plan."""
    return len(p.tasks), sum(1 for t in p.tasks if t.done)


def mark_task_done(path: str, file_path: str) -> None:
    """Rewrite the PLAN.md at *path*, flipping the first pending task for
    *file_path* from ``- [ ]`` to ``- [x]``."""
    try:
        lines = Path(path).read_text().splitlines(keepends=True)
    except OSError:
        return
    for i, line in enumerate(lines):
        m = _TASK_RE.match(line.rstrip('\n'))
        if m and m.group(1) == ' ' and _clean_filename_token(m.group(2)) == file_path:
            lines[i] = '- [x] ' + _clean_filename_token(m.group(2)) + m.group(3) + '\n'
            break
    Path(path).write_text(''.join(lines))


def is_build_file(name: str) -> bool:
    return Path(name).name in _BUILD_NAMES or name.endswith('.csproj')


def is_test_file(f: str) -> bool:
    base = Path(f).name
    return (f.startswith('tests/') or f.startswith('test/') or
            base.startswith('test_') or '_test.' in base)


def has_pending_build_file(p: Plan) -> bool:
    return any(not t.done and is_build_file(t.file_path) for t in p.tasks)


# ── dependency build order (design criterion: build bottom-up) ─────────────────
# A complex plan must be built smallest-part-first: a module that is *called by*
# another is written before its caller, and tests come after the code they verify
# (cascade control — an early mistake can't compound). We can't read imports at
# plan time (no source yet), so we approximate the dependency DAG with file-role
# layers. Lower rank = fewer prerequisites = built earlier.
#
#   0  manifests / build files   prerequisites of every compile+install
#   1  declarations              headers, type/model/schema — depended-upon
#   2  core modules              library/domain code (the default)
#   3  wiring / entry points     main, app, routes — they CALL layers 1–2
#   4  tests                     verify the code, so they run last
#
# The Makefile sits at rank 0 (set up early, never a dangling final task) — the
# criterion also asks it be woven incrementally, handled by ground_plan, not here.

_HEADER_EXTS = {'.h', '.hpp', '.hh', '.hxx', '.pyi'}
_ENTRY_STEMS = {'main', 'program', 'index', 'app', 'server', 'cli',
                '__main__', 'startup', 'wsgi', 'asgi'}
_WIRING_HINTS = {'controller', 'route', 'router', 'handler', 'endpoint',
                 'middleware', 'view'}
_DECL_HINTS = {'model', 'schema', 'entity', 'type', 'interface', 'dto',
               'domain', 'contract', 'context'}
# decl words clear enough to spot in freeform task descriptions (drop the short
# ambiguous ones — 'type' would match 'prototype' in prose).
_DECL_DESC_HINTS = ('model', 'schema', 'entity', 'interface', 'domain', 'context')
_TEST_DIR_RE = re.compile(r'(?i)(^|[._-])tests?$')


def _tokens(name: str) -> set[str]:
    """Lowercased word tokens of a filename stem, split on separators and
    camelCase: 'BlogContext'→{blog,context}, 'user_controller'→{user,controller}."""
    return {w.lower() for w in re.findall(r'[A-Za-z][a-z0-9]*|[0-9]+', name)}


def _tok_hits(tokens: set, hints: set) -> bool:
    """True if any token matches a hint, plural-tolerant: models→model, routes→route."""
    return any(t in hints or t.rstrip('s') in hints for t in tokens)


def _seg_hits(parts, hints: set) -> bool:
    """True if any directory segment matches a hint (plural-tolerant: routes→route)."""
    return _tok_hits({seg.lower() for seg in parts}, hints)


def _looks_like_test(path: str) -> bool:
    """Broader test detection than is_test_file, for ordering only: also catches
    xUnit-style `FooTests.cs`, a `Backend.Tests/` project dir, and `*.test.`/
    `*.spec.` JS/TS specs that the strict predicate misses."""
    name = Path(path).name.lower()
    stem = Path(path).stem.lower()
    if is_test_file(path) or '.test.' in name or '.spec.' in name:
        return True
    if stem.endswith('test') or stem.endswith('tests'):
        return True
    return any(_TEST_DIR_RE.search(seg) for seg in Path(path).parts[:-1])


def _is_manifest(name: str) -> bool:
    n = name.lower()
    if n in {b.lower() for b in _BUILD_NAMES}:
        return True
    return (n.endswith('.csproj') or n.endswith('.sln') or n.endswith('.fsproj')
            or (n.startswith('requirements') and n.endswith('.txt'))
            or (n.startswith('tsconfig') and n.endswith('.json'))
            or n in {'vite.config.ts', 'vite.config.js', 'vitest.config.ts',
                     'vitest.config.js', 'jest.config.js', 'jest.config.ts',
                     'go.sum', 'cmakelists.txt', 'meson.build'})


def build_rank(task: Task) -> int:
    """The dependency build layer (0–4, earlier first) for one task. Pure and
    deterministic; see the table above. First matching rule wins; a filename
    signal outranks a directory signal (the file's own name is more specific)."""
    path = task.file_path
    name = Path(path).name
    stem = Path(path).stem.lower()
    ext = Path(path).suffix.lower()
    desc = (task.description or '').lower()
    tokens = _tokens(Path(path).stem)
    parent_parts = Path(path).parts[:-1]

    if _looks_like_test(path):
        return 4
    if name.lower() == 'makefile' or _is_manifest(name):
        return 0
    if ext in _HEADER_EXTS:
        return 1
    # filename signals (most specific to the file's own role)
    if stem in _ENTRY_STEMS or _tok_hits(tokens, _WIRING_HINTS):
        return 3
    if _tok_hits(tokens, _DECL_HINTS) or any(h in desc for h in _DECL_DESC_HINTS):
        return 1
    # directory signals (a routes/ or models/ dir tells the role when the name doesn't)
    if _seg_hits(parent_parts, _WIRING_HINTS):
        return 3
    if _seg_hits(parent_parts, _DECL_HINTS):
        return 1
    return 2


def build_order(tasks: list[Task]) -> list[Task]:
    """Return *tasks* reordered bottom-up by dependency layer (build_rank), stable
    within a layer (planner order preserved). Pure — does not mutate the input."""
    return [t for _, t in sorted(enumerate(tasks),
                                 key=lambda it: (build_rank(it[1]), it[0]))]


def reorder_plan(plan_path: str) -> list[str]:
    """Rewrite the ``## Files`` checklist of a PLAN.md in dependency build order
    (build_order): manifests + callee modules first, tests last. Preserves each
    task line's *exact* text (status `[ ]`/`[x]`/`[~]`, description) and the
    position of any non-task lines in the section — only the task lines are
    permuted among their own slots. Idempotent: a plan already in build order is
    left byte-identical. Returns the new file-path order, or [] if nothing moved.
    """
    try:
        lines = Path(plan_path).read_text().splitlines(keepends=True)
    except OSError:
        return []
    start = next((i + 1 for i, ln in enumerate(lines)
                  if re.match(r'^##\s+Files\s*$', ln.rstrip('\n'))), None)
    if start is None:
        return []
    end = next((j for j in range(start, len(lines)) if lines[j].startswith('## ')),
               len(lines))
    slots, entries = [], []                    # entries: (original_line, Task)
    for k in range(start, end):
        parsed = parse_content(lines[k]).tasks  # reuse the canonical line parser
        if parsed:
            slots.append(k)
            entries.append((lines[k], parsed[0]))
    if len(entries) < 2:
        return []
    order = sorted(range(len(entries)),
                   key=lambda idx: (build_rank(entries[idx][1]), idx))
    if order == list(range(len(entries))):
        return []                              # already in build order — no-op
    for slot, idx in zip(slots, order):
        lines[slot] = entries[idx][0]
    Path(plan_path).write_text(''.join(lines))
    return [entries[idx][1].file_path for idx in order]


def strip_thinking_artifacts(path: str) -> bool:
    try:
        data = Path(path).read_text()
    except OSError:
        return False
    cleaned = _THINKING_RE.sub('', data)
    if cleaned == data:
        return False
    Path(path).write_text(cleaned)
    return True


def normalize_test_command(path: str) -> bool:
    try:
        data = Path(path).read_text()
    except OSError:
        return False
    updated = data
    for old, new in [('\npython ', '\npython3 '), ('&& python ', '&& python3 '),
                     ('| python ', '| python3 ')]:
        updated = updated.replace(old, new)
    # pytest on Rust source files is wrong — use cargo test.
    p = parse_content(updated)
    if p.test_command and re.match(r'pytest\s+.*\.rs\b', p.test_command):
        updated = _set_test_command(updated, 'cargo test')
    # A Go plan whose test command would start a blocking server (bare `./binary`,
    # e.g. `make && ./main`) hangs the test gate forever. The planner reliably
    # re-emits this even when asked to fix it, so rewrite it deterministically to
    # the non-blocking canonical Go check (matches the agent's go fallback):
    # `go test ./...` exits 0 when the package builds with no/passing tests and
    # non-zero when it fails to compile.
    p = parse_content(updated)
    if (p.test_command and re.search(r'\b\w+\.go\b', updated)
            and 'go test' not in p.test_command
            and re.search(r'(^|&&\s*|;\s*|\|\s*)\./', p.test_command)):
        updated = _set_test_command(updated, 'go test ./...')
    # dotnet ef migration/database commands are not test commands — replace with dotnet test.
    p = parse_content(updated)
    if p.test_command and re.match(r'dotnet\s+ef\s+', p.test_command):
        updated = _set_test_command(updated, 'dotnet test')
    # Quote unquoted --filter arguments that contain shell-special chars like () * ~.
    # Example: dotnet test --filter FullyQualifiedName~*.Foo()
    #       → dotnet test --filter "FullyQualifiedName~*.Foo()"
    p_tmp = parse_content(updated)
    if p_tmp.test_command:
        def _quote_filter(m: re.Match) -> str:
            val = m.group(1)
            if val and val[0] not in ('"', "'") and re.search(r'[()~*]', val):
                return f'--filter "{val}"'
            return m.group(0)
        new_cmd = re.sub(r'--filter\s+(\S+)', _quote_filter, p_tmp.test_command)
        if new_cmd != p_tmp.test_command:
            updated = _set_test_command(updated, new_cmd)
    # C/Makefile: `make && ./binary` where the Makefile has a `test` target.
    # The planner guesses the output binary name (e.g. `./sdl2_line`) but the
    # fixture Makefile's `test` target already runs the binary correctly, so
    # `make test` is simpler and always correct. Only rewrite when a Makefile
    # exists AND has a `test:` rule.
    p_c = parse_content(updated)
    if (p_c.test_command
            and re.search(r'^make\b.*&&\s*\./', p_c.test_command)
            and Path('Makefile').exists()):
        mk = Path('Makefile').read_text(errors='replace')
        if re.search(r'^test\s*:', mk, re.MULTILINE):
            updated = _set_test_command(updated, 'make test')

    # dotnet test <foo>.csproj where foo.csproj doesn't exist — find the real one.
    # If the found .csproj has no test references, use 'dotnet build' instead.
    p2 = parse_content(updated)
    if p2.test_command:
        m = re.match(r'(dotnet\s+test)\s+(\S+\.csproj)(.*)', p2.test_command)
        if m and not Path(m.group(2)).exists():
            real = list(Path('.').glob('*.csproj'))
            if real:
                csproj_text = real[0].read_text(errors='ignore')
                has_tests = any(pkg in csproj_text for pkg in (
                    'xunit', 'MSTest', 'NUnit', 'Microsoft.NET.Test.Sdk'))
                verb = 'test' if has_tests else 'build'
                updated = _set_test_command(updated, f'dotnet {verb} {real[0]}{m.group(3)}')
            else:
                # No .csproj at all — strip the bad path so dotnet auto-discovers
                updated = _set_test_command(updated, f'{m.group(1)}{m.group(3)}')
    # dotnet test <dir> that resolves to no project file — redirect to the root
    # project (or bare `dotnet test` for auto-discovery). Fires when the LLM writes
    # `dotnet test tests/` but tests/ holds only .cs files, OR doesn't exist yet at
    # grounding time (the writer creates it later without a .csproj) — the dominant
    # p10 MSB1003 bottleneck. `glob` on a missing or non-dir path is empty, so the
    # single check covers "dir absent", "path is a file", and "dir without .csproj";
    # an existing dir that *does* hold a .csproj is left untouched.
    # fix_csharp_xunit_packages will add xunit to the root csproj during reapply().
    p3 = parse_content(updated)
    if p3.test_command:
        m3 = re.match(r'dotnet\s+test\s+([^\s-]\S*)\s*$', p3.test_command)
        if m3 and not m3.group(1).endswith('.csproj'):
            arg_path = Path(m3.group(1).rstrip('/'))
            if not list(arg_path.glob('*.csproj')):
                real = sorted(Path('.').glob('*.csproj'))
                if real:
                    updated = _set_test_command(updated, f'dotnet test {real[0]}')
                else:
                    updated = _set_test_command(updated, 'dotnet test')
    if updated == data:
        return False
    Path(path).write_text(updated)
    return True


def normalize_embedded_files(plan_path: str) -> list[str]:
    try:
        data = Path(plan_path).read_text()
    except OSError:
        return []
    known = {
        'makefile': 'Makefile', 'cmakelists.txt': 'CMakeLists.txt',
        'cargo.toml': 'Cargo.toml', 'build.sh': 'build.sh',
        'package.json': 'package.json', 'pyproject.toml': 'pyproject.toml',
    }
    h2_re = re.compile(r'^## ([A-Za-z0-9._\-]+)\s*$')
    fence_re = re.compile(r'^```[a-zA-Z]*\s*$')
    lines, extracted = data.splitlines(), []
    current_section, in_fence, fence_buf = '', False, []
    for line in lines:
        m = h2_re.match(line)
        if m:
            current_section = known.get(m.group(1).lower(), '')
            in_fence, fence_buf = False, []
            continue
        if not current_section:
            continue
        if not in_fence and fence_re.match(line):
            in_fence = True
            continue
        if in_fence and line.strip() == '```':
            extracted.append((current_section, '\n'.join(fence_buf)))
            current_section, in_fence, fence_buf = '', False, []
            continue
        if in_fence:
            fence_buf.append(line)
    if not extracted:
        return []
    names, plan_text = [], data
    for name, content in extracted:
        try:
            Path(name).write_text(content)
            names.append(name)
        except OSError:
            continue
        if f'- [ ] {name}' not in plan_text and f'- [x] {name}' not in plan_text:
            plan_text = plan_text.replace(
                '## Files\n', f'## Files\n- [x] {name} — auto-extracted from plan\n', 1)
        else:
            plan_text = plan_text.replace(f'- [ ] {name}', f'- [x] {name}')
    Path(plan_path).write_text(plan_text)
    return names


def drop_runtime_artifacts(plan_path: str, p: Plan) -> list[str]:
    dropped = [t.file_path for t in p.tasks
               if Path(t.file_path).suffix.lstrip('.').lower() in _RUNTIME_EXTS]
    if not dropped:
        return []
    try:
        lines = Path(plan_path).read_text().splitlines(keepends=True)
    except OSError:
        return []
    out = [ln for ln in lines
           if not (_TASK_RE.match(ln.rstrip('\n')) and
                   Path(_clean_filename_token(_TASK_RE.match(ln.rstrip('\n')).group(2))).suffix.lstrip('.').lower()
                   in _RUNTIME_EXTS)]
    Path(plan_path).write_text(''.join(out))
    return dropped


def plan_languages(p: Plan) -> dict[str, list[str]]:
    """Return {language: [file_paths]} for all non-build tasks with a known language."""
    langs: dict[str, list[str]] = {}
    for task in p.tasks:
        if is_build_file(task.file_path):
            continue
        lang = _EXT_LANGUAGE.get(Path(task.file_path).suffix.lower(), '')
        if lang:
            langs.setdefault(lang, []).append(task.file_path)
    return langs


def drop_minority_languages(plan_path: str, p: Plan) -> list[str]:
    """Remove minority-language tasks from PLAN.md, keeping only the dominant language.

    When a plan spans multiple source languages the dominant language (most task
    files) wins and all others are stripped. Returns the list of dropped paths.
    Idempotent — does nothing when the plan is already single-language.
    """
    langs = plan_languages(p)
    if len(langs) <= 1:
        return []
    dominant = max(langs, key=lambda k: len(langs[k]))
    to_drop = {fp for lang, fps in langs.items() if lang != dominant for fp in fps}
    if not to_drop:
        return []
    try:
        lines = Path(plan_path).read_text().splitlines(keepends=True)
    except OSError:
        return []
    out = []
    for line in lines:
        m = _TASK_RE.match(line.rstrip('\n'))
        if m and _clean_filename_token(m.group(2)) in to_drop:
            continue
        out.append(line)
    Path(plan_path).write_text(''.join(out))
    return sorted(to_drop)


def _dotnet_target_framework() -> str:
    """Ask the installed dotnet SDK its version → matching target framework moniker.

    Grounds the .csproj's TargetFramework in the real toolchain rather than guessing.
    """
    try:
        out = subprocess.run(['dotnet', '--version'], capture_output=True,
                             text=True, timeout=10)
        major = out.stdout.strip().split('.')[0]
        if major.isdigit():
            return f"net{major}.0"
    except Exception:
        pass
    return "net8.0"  # last LTS fallback when the SDK can't be queried


def _csproj_content(include_ef_core: bool = False) -> str:
    """A minimal, canonical SDK-style console project. SDK-style projects glob all
    .cs files in the directory, so no source files need to be listed explicitly."""
    ef_packages = (
        '  <ItemGroup>\n'
        '    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />\n'
        '    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.0" />\n'
        '    <PackageReference Include="Microsoft.AspNetCore.OpenApi" Version="8.0.0" />\n'
        '  </ItemGroup>\n'
    ) if include_ef_core else ''
    return (
        '<Project Sdk="Microsoft.NET.Sdk.Web">\n'
        '  <PropertyGroup>\n'
        f'    <TargetFramework>{_dotnet_target_framework()}</TargetFramework>\n'
        '    <ImplicitUsings>enable</ImplicitUsings>\n'
        '    <Nullable>disable</Nullable>\n'
        '  </PropertyGroup>\n'
        + ef_packages
        + '</Project>\n'
    ) if include_ef_core else (
        '<Project Sdk="Microsoft.NET.Sdk">\n'
        '  <PropertyGroup>\n'
        '    <OutputType>Exe</OutputType>\n'
        f'    <TargetFramework>{_dotnet_target_framework()}</TargetFramework>\n'
        '    <ImplicitUsings>enable</ImplicitUsings>\n'
        '    <Nullable>disable</Nullable>\n'
        '  </PropertyGroup>\n'
        '</Project>\n'
    )


def _dotnet_run_malformed(tc: str) -> bool:
    """True if a dotnet test command points at a .cs source instead of a project.
    `dotnet run --project X.cs` is rejected by the SDK (it wants a .csproj/dir)."""
    if 'dotnet' not in tc:
        return False
    return bool(re.search(r'\.cs(\b|$)', tc)) and '.csproj' not in tc


def _set_test_command(text: str, new_cmd: str) -> str:
    """Replace the body of the `## Test Command` section with a single command."""
    out, in_sec, wrote = [], False, False
    for line in text.splitlines():
        if re.match(r'^##\s+Test Command\s*$', line):
            out.append(line)
            out.append(new_cmd)
            in_sec, wrote = True, True
            continue
        if in_sec:
            if line.startswith('## ') or line.strip() == '':
                in_sec = False
                out.append(line)
            # else: drop the stale command line(s)
            continue
        out.append(line)
    result = '\n'.join(out)
    if text.endswith('\n'):
        result += '\n'
    return result if wrote else text


def ground_plan(plan_path: str, p: Plan) -> list[str]:
    """Validate plan details against the real toolchain before any code is written.

    These are all programming problems, so the build system is a deterministic,
    problem-agnostic oracle: it knows the *language*, never the test. Currently:
      - Level 2 (project shape): C# can't build without a .csproj — add one.
      - Level 3 (build command): rewrite a dotnet command that targets a .cs
        source (which the SDK rejects) to the canonical `dotnet run`.
    Returns a list of human-readable grounding changes. Idempotent.
    """
    try:
        data = Path(plan_path).read_text()
    except OSError:
        return []
    text, changes = data, []
    exts = {Path(t.file_path).suffix.lower() for t in p.tasks}
    names = [Path(t.file_path).name.lower() for t in p.tasks]

    # Level 2 — Rust multi-file plans need a Cargo.toml; without one the lint
    # command falls back to `rustc file.rs` which fails for module files.
    rs_files = [t.file_path for t in p.tasks if t.file_path.endswith('.rs')]
    if (len(rs_files) > 1 and 'cargo.toml' not in names
            and not Path('Cargo.toml').exists()):
        proj = Path(os.getcwd()).name or 'app'
        # Detect root-level main.rs so Cargo finds it without an `src/` move.
        main_rs = next((f for f in rs_files if Path(f).name == 'main.rs'), None)
        bin_section = (
            f'\n[[bin]]\nname = "{proj}"\npath = "{main_rs}"\n' if main_rs else ''
        )
        cargo_content = (
            '[package]\n'
            f'name = "{proj}"\n'
            'version = "0.1.0"\n'
            'edition = "2021"\n'
            + bin_section
        )
        try:
            Path('Cargo.toml').write_text(cargo_content)
            if '] Cargo.toml' not in text:
                text = text.replace(
                    '## Files\n',
                    '## Files\n- [x] Cargo.toml — auto-grounded (Rust needs a project file)\n', 1)
            changes.append('Rust: added Cargo.toml (multi-file Rust needs a project file)')
        except OSError:
            pass

    # Level 2 — C# needs a project file to compile.
    _ef_keywords = ('entityframework', 'ef core', 'dbcontext', 'webapplicationfactory',
                    'asp.net', 'aspnetcore', 'minimal api')
    plan_lower = data.lower()
    needs_ef = any(kw in plan_lower for kw in _ef_keywords)
    if '.cs' in exts and not any(n.endswith('.csproj') for n in names):
        proj = Path(os.getcwd()).name or 'app'
        csproj = f"{proj}.csproj"
        try:
            if not Path(csproj).exists():
                Path(csproj).write_text(_csproj_content(include_ef_core=needs_ef))
            elif needs_ef and 'EntityFrameworkCore' not in Path(csproj).read_text():
                Path(csproj).write_text(_csproj_content(include_ef_core=True))
            if f'] {csproj}' not in text:
                text = text.replace(
                    '## Files\n',
                    f'## Files\n- [x] {csproj} — auto-grounded (C# needs a project file)\n', 1)
            changes.append(f"C#: added {csproj} (dotnet cannot build loose .cs files)")
        except OSError:
            pass

    # Level 2b — ASP.NET API completeness. A minimal-API goal whose integration test
    # references `Program`/WebApplicationFactory needs an entry-point file, or the host
    # type never exists and the test fails to compile (CS0246 — the dominant
    # backend_build first-error once MSB1003 is cleared, archive scan 2026-06-23). The
    # architect routinely plans Models/DbContext/Controllers but omits the entry point.
    # We add the *task* — the writer authors the code (no pregenerated code, §0.2) — at
    # the top of ## Files so it is written before the test under default order.
    # Gated behind MU_ASPNET_ENTRYPOINT (I1: off ⇒ byte-identical).
    _entry_names = {'program.cs', 'startup.cs', 'app.cs', 'host.cs', 'main.cs'}
    if (os.environ.get('MU_ASPNET_ENTRYPOINT') == '1'
            and '.cs' in exts and needs_ef
            and not any(n in _entry_names for n in names)
            and '] Program.cs' not in text):
        entry_desc = (
            'minimal API entry point: build the WebApplication host, register EF Core '
            '(SQLite) + the DbContext, map GET /api/posts returning the seeded posts '
            "(seed one Title='Hello World'); end the file with "
            '`public partial class Program { }` so WebApplicationFactory<Program> in '
            'the tests can reference it')
        text = text.replace(
            '## Files\n', f'## Files\n- [ ] Program.cs — {entry_desc}\n', 1)
        changes.append('ASP.NET: added Program.cs entry-point task '
                       '(WebApplicationFactory needs a Program host)')
        p = parse_content(text)

    # Level 3 — a dotnet run command must target a project, not a source file.
    if _dotnet_run_malformed(p.test_command):
        text = _set_test_command(text, 'dotnet run')
        changes.append("rewrote Test Command to canonical 'dotnet run'")

    # Level 2c — dotnet + Vue fullstack: test command, Makefile, and frontend files.
    has_vue = any(t.file_path.endswith('.vue') for t in p.tasks)
    has_cs = '.cs' in exts
    if has_cs and has_vue:
        if p.test_command and p.test_command.strip() != 'make test':
            text = _set_test_command(text, 'make test')
            p = parse_content(text)
            changes.append("corrected test command to 'make test' (dotnet+vue fullstack)")

        # Ensure frontend/package.json and frontend/vite.config.ts are in the plan.
        existing_paths = {t.file_path for t in p.tasks}
        for fp, desc in [
            ('frontend/package.json', 'Vue 3 + Vite devDependencies'),
            ('frontend/vite.config.ts', 'Vite configuration with jsdom + globals'),
        ]:
            if fp not in existing_paths:
                text = text.replace('## Files\n', f'## Files\n- [ ] {fp} — {desc}\n', 1)
                changes.append(f"added missing {fp} (dotnet+vue fullstack)")
        p = parse_content(text)

        has_makefile_now = any(Path(t.file_path).name.lower() == 'makefile' for t in p.tasks)
        if not has_makefile_now:
            test_dirs = [Path(t.file_path).parent.name
                         for t in p.tasks if t.file_path.endswith('.csproj')
                         and 'test' in t.file_path.lower()]
            tests_dir = test_dirs[0] if test_dirs else 'backend-tests'
            frontend_dirs = [str(Path(t.file_path).parent)
                             for t in p.tasks if t.file_path.endswith('package.json')]
            frontend_dir = frontend_dirs[0] if frontend_dirs else 'frontend'
            makefile_content = (
                '.PHONY: install test\n\n'
                'install:\n'
                f'\tcd {frontend_dir} && npm install\n\n'
                'test: install\n'
                f'\tdotnet test {tests_dir}/\n'
                f'\tcd {frontend_dir} && npx vitest run\n'
            )
            try:
                if not Path('Makefile').exists():
                    Path('Makefile').write_text(makefile_content)
                if '- [ ] Makefile' not in text and '- [x] Makefile' not in text:
                    text = text.replace(
                        '## Files\n',
                        '## Files\n- [x] Makefile — auto-grounded (dotnet+vue fullstack)\n', 1)
                changes.append("added Makefile for dotnet+vue fullstack")
            except OSError:
                pass

    # Level 2b — only a C/C++ project (real C sources) whose `make` test command
    # ships no Makefile gets the synthesized `cc -o` rule. A Python/other project
    # must NOT: its stray `pytest` recipe gets hoisted away, leaving `make test`
    # with no rule (the p7-flask failure). Those fall through to Level 4a below.
    has_makefile = any(Path(t.file_path).name.lower() == 'makefile' for t in p.tasks)
    c_sources = [t.file_path for t in p.tasks
                 if Path(t.file_path).suffix.lower() in ('.c', '.cpp', '.cc', '.cxx')]
    if not has_makefile and 'make' in p.test_command and not has_cs and c_sources:
        # Infer the binary from the test command (e.g. 'make && ./hello' → 'hello').
        bin_match = re.search(r'&&\s+\.?/?([\w.-]+)\s*$', p.test_command)
        binary = bin_match.group(1) if bin_match else 'main'
        src = c_sources[0]
        makefile_content = (
            f'{binary}: {src}\n'
            f'\tcc -o {binary} {src} $(CFLAGS) $(LDFLAGS)\n\n'
            f'clean:\n\trm -f {binary}\n'
        )
        try:
            if not Path('Makefile').exists():
                Path('Makefile').write_text(makefile_content)
            if '- [ ] Makefile' not in text and '- [x] Makefile' not in text:
                text = text.replace(
                    '## Files\n',
                    '## Files\n- [x] Makefile — auto-grounded (test command uses make)\n', 1)
            has_makefile = True
            changes.append(f"added Makefile for '{binary}' (test command uses make)")
        except OSError:
            pass

    # Level 2d — xUnit test files in a Tests/ subdirectory need their own .csproj.
    # `dotnet test ./Tests` fails with "no project file found" unless Tests/Tests.csproj
    # exists and references the main project.
    if '.cs' in exts:
        test_cs_files = [t.file_path for t in p.tasks
                         if t.file_path.startswith('Tests/') and t.file_path.endswith('.cs')]
        tests_csproj = Path('Tests/Tests.csproj')
        has_tests_csproj = any(
            t.file_path == 'Tests/Tests.csproj' or t.file_path.startswith('Tests/') and t.file_path.endswith('.csproj')
            for t in p.tasks
        )
        if test_cs_files and not has_tests_csproj and not tests_csproj.exists():
            proj_name = Path(os.getcwd()).name or 'app'
            main_csproj = f'{proj_name}.csproj'
            tests_csproj_content = (
                '<Project Sdk="Microsoft.NET.Sdk">\n'
                '  <PropertyGroup>\n'
                f'    <TargetFramework>{_dotnet_target_framework()}</TargetFramework>\n'
                '    <ImplicitUsings>enable</ImplicitUsings>\n'
                '    <Nullable>disable</Nullable>\n'
                '    <IsPackable>false</IsPackable>\n'
                '  </PropertyGroup>\n'
                '  <ItemGroup>\n'
                '    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.9.0" />\n'
                '    <PackageReference Include="xunit" Version="2.7.0" />\n'
                '    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.7" />\n'
                '    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.0.0" />\n'
                '  </ItemGroup>\n'
                '  <ItemGroup>\n'
                f'    <ProjectReference Include="../{main_csproj}" />\n'
                '  </ItemGroup>\n'
                '</Project>\n'
            )
            try:
                Path('Tests').mkdir(exist_ok=True)
                tests_csproj.write_text(tests_csproj_content)
                if '- [ ] Tests/Tests.csproj' not in text and '- [x] Tests/Tests.csproj' not in text:
                    text = text.replace(
                        '## Files\n',
                        '## Files\n- [x] Tests/Tests.csproj — auto-grounded (xUnit needs a project file)\n', 1)
                changes.append('C#: added Tests/Tests.csproj (xUnit tests need a project file)')
                # Rewrite test command to target the test project
                if p.test_command and 'Tests' in p.test_command and 'dotnet test' in p.test_command:
                    text = _set_test_command(text, 'dotnet test Tests/')
            except OSError:
                pass

    # Level 4 — bare 'pytest' without an install step won't find third-party packages.
    # If the plan has a Makefile and the goal mentions Flask/packages, the test command
    # must run make first so the venv is created before pytest is invoked.
    has_makefile = any(Path(t.file_path).name.lower() == 'makefile' for t in p.tasks)
    has_py_test = any(is_test_file(t.file_path) for t in p.tasks)
    has_py_src = any(Path(t.file_path).suffix == '.py' and not is_test_file(t.file_path)
                     for t in p.tasks)
    tc = p.test_command.strip()
    _bare_pytest = re.compile(r'(?<![/\w])pytest\b')
    # Level 4a — if no Makefile but there are Python src+test files, add a default Makefile.
    if not has_makefile and has_py_test and has_py_src:
        req_line = '\t.venv/bin/pip install -r requirements.txt pytest' \
                   if any(Path(t.file_path).name == 'requirements.txt' for t in p.tasks) \
                   else '\t.venv/bin/pip install flask pytest'
        makefile_content = (
            'install:\n'
            '\tpython3 -m venv .venv\n'
            f'{req_line}\n\n'
            'test: install\n'
            '\t.venv/bin/pytest\n'
        )
        try:
            if not Path('Makefile').exists():
                Path('Makefile').write_text(makefile_content)
            if '- [ ] Makefile' not in text and '- [x] Makefile' not in text:
                text = text.replace(
                    '## Files\n',
                    '## Files\n- [x] Makefile — auto-grounded (Python project needs venv)\n', 1)
            has_makefile = True
            changes.append("added Makefile for Python venv setup")
        except OSError:
            pass
    # Level 4b — normalize bare/unvenv-ed pytest to use the venv.
    if has_makefile and has_py_test and _bare_pytest.search(tc):
        new_tc = _bare_pytest.sub('.venv/bin/pytest', tc)
        if not new_tc.startswith('make'):
            new_tc = 'make && ' + new_tc
        if new_tc != tc:
            text = _set_test_command(text, new_tc)
            changes.append(f"normalized test command to use venv: {new_tc}")

    if text != data:
        Path(plan_path).write_text(text)
    return changes


def check_goal_alignment(p: Plan, goal: str) -> tuple[bool, list[str]]:
    stopwords = {
        'and', 'the', 'via', 'with', 'for', 'from', 'that', 'this', 'are', 'not',
        'make', 'into', 'also', 'both', 'each', 'just', 'like', 'more', 'only',
        'over', 'some', 'such', 'then', 'when', 'will', 'have', 'must', 'been',
        'your', 'them', 'than', 'even', 'write', 'using', 'create', 'show',
        'include', 'returns', 'support', 'runs', 'provide', 'list', 'uses', 'call',
        'print', 'read', 'take', 'back', 'work', 'build', 'adds', 'does', 'writes',
        'again', 'program', 'table', 'contains', 'inserted', 'entry', 'given',
        'should', 'store', 'data', 'able',
    }
    plan_text = p.plan_context.lower()
    missing, found = [], False
    for w in re.findall(r'[a-z0-9]+', goal.lower()):
        if len(w) < 4 or w in stopwords:
            continue
        if w in plan_text:
            found = True
        else:
            missing.append(w)
    return found, missing


_RELEVANT_FILES_CHAR_BUDGET = 3000


def relevant_files_context(p: Plan, target: str) -> str:
    target_dir = str(Path(target).parent)
    module_stem = Path(target).stem.removeprefix('test_')
    buf, count, total_chars = [], 0, 0
    for t in p.tasks:
        if count >= 6 or not t.done:
            continue
        fp = Path(t.file_path)
        if not fp.exists():
            continue
        if not (fp.suffix.lstrip('.') in ('h', 'hpp') or
                str(fp.parent) == target_dir or fp.stem == module_stem):
            continue
        try:
            content = fp.read_text()
            entry = f'### {t.file_path}\n```\n{content}\n```\n'
            if total_chars + len(entry) > _RELEVANT_FILES_CHAR_BUDGET:
                break
            buf.append(entry)
            total_chars += len(entry)
            count += 1
        except OSError:
            pass
    return '\n'.join(buf)


def pending_source_files(p: Plan, current: str) -> str:
    lines, found = [], False
    for t in p.tasks:
        if t.done or t.in_progress:
            continue
        if t.file_path == current:
            found = True
            continue
        if found:
            lines.append('  ' + t.file_path)
    return '\n'.join(lines)


def _sketch_comment(ext: str, lines: list[str]) -> str:
    if ext in ('.c', '.h', '.cpp', '.cc', '.cxx', '.hpp',
               '.go', '.rs', '.ts', '.tsx', '.js', '.jsx',
               '.cs', '.java', '.swift', '.kt'):
        body = '\n'.join(f' * {line}' for line in lines)
        return f'/*\n{body}\n */\n'
    if ext in ('.html', '.xml', '.svg'):
        body = '\n'.join(f'  {line}' for line in lines)
        return f'<!--\n{body}\n-->\n'
    return '\n'.join(f'# {line}' for line in lines) + '\n'


def write_sketches(p: 'Plan', goal: str) -> list[str]:
    """Create stub files for every pending, non-build task in `p`.

    Each stub contains only a comment block describing the file's role so the
    agent writer can fill it in. Skips files that already exist.
    Returns the list of paths created.
    """
    created = []
    for task in p.tasks:
        if task.done or is_build_file(task.file_path):
            continue
        path = Path(task.file_path)
        if path.exists():
            continue
        ext = path.suffix.lower()
        lines: list[str] = [f'PLAN: {task.file_path}', f'GOAL: {goal}']
        if task.description:
            lines.append(f'PURPOSE: {task.description}')
        comment = _sketch_comment(ext, lines)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(comment)
            created.append(task.file_path)
        except OSError:
            pass
    return created


def extract_plan_content(s: str) -> str:
    s = s.strip()
    if '</think>' in s:
        s = s[s.index('</think>') + len('</think>'):].strip()
    if s.startswith('```'):
        nl = s.find('\n')
        if nl >= 0:
            inner = s[nl + 1:]
            end = inner.rfind('```')
            s = inner[:end].strip() if end >= 0 else inner
    if '## Summary' in s:
        return s[s.index('## Summary'):]
    if '## Files' in s:
        return s[s.index('## Files'):]
    return s if '- [ ]' in s else ''


def record_failed_repair(label: str, error_snippet: str,
                         plan_file: str = 'PLAN.md') -> None:
    try:
        content = Path(plan_file).read_text()
    except OSError:
        return
    snippet = '\n'.join(error_snippet.strip().splitlines()[:5]).replace('\n', '\n  ')
    entry = f'- {label} — still failing. Error:\n  ```\n  {snippet}\n  ```\n'
    header = '\n## Repair History\n'
    if header in content:
        idx = content.index(header)
        content = content[:idx + len(header)] + entry + content[idx + len(header):]
    else:
        content = content.rstrip('\n') + '\n' + header + entry
    Path(plan_file).write_text(content)


def repair_history(plan_file: str = 'PLAN.md') -> str:
    try:
        data = Path(plan_file).read_text()
    except OSError:
        return ''
    header = '## Repair History'
    if header not in data:
        return ''
    return f'\n\n{data[data.index(header):].strip()}\n\nDo NOT repeat approaches listed in Repair History above.'


def record_challenge(label: str, snippet: str = '',
                     plan_file: str = 'PLAN.md') -> None:
    try:
        content = Path(plan_file).read_text()
    except OSError:
        return
    if snippet.strip():
        lines = snippet.strip().splitlines()[:5]
        snippet_text = '\n'.join(lines).replace('\n', '\n  ')
        entry = f'- {label}\n  ```\n  {snippet_text}\n  ```\n'
    else:
        entry = f'- {label}\n'
    header = '\n## Challenges\n'
    if header in content:
        idx = content.index(header)
        content = content[:idx + len(header)] + entry + content[idx + len(header):]
    else:
        content = content.rstrip('\n') + '\n' + header + entry
    Path(plan_file).write_text(content)


def get_challenges(plan_file: str = 'PLAN.md') -> str:
    try:
        data = Path(plan_file).read_text()
    except OSError:
        return ''
    header = '## Challenges'
    if header not in data:
        return ''
    start = data.index(header)
    rest = data[start:]
    m = re.search(r'\n## ', rest[3:])
    section = rest[:m.start() + 1] if m else rest
    return section.strip()


def clear_challenges(plan_file: str = 'PLAN.md') -> None:
    try:
        content = Path(plan_file).read_text()
    except OSError:
        return
    header = '\n## Challenges\n'
    if header not in content:
        return
    start = content.index(header)
    rest = content[start + len(header):]
    m = re.search(r'^## ', rest, re.MULTILINE)
    if m:
        content = content[:start] + '\n' + rest[m.start():]
    else:
        content = content[:start]
    Path(plan_file).write_text(content.rstrip('\n') + '\n')

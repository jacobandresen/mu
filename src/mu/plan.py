"""PLAN.md parsing and manipulation."""

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
    try:
        return parse_content(Path(path).read_text())
    except OSError:
        return Plan()


def parse_content(content: str) -> Plan:
    lines = content.splitlines()
    p = Plan()
    for line in lines:
        m = _TASK_RE.match(line)
        if not m:
            continue
        status, fp, rest = m.group(1), m.group(2), m.group(3).strip()
        desc = ''
        if '—' in rest:
            desc = rest[rest.index('—') + 1:].strip()
        elif '-' in rest:
            desc = rest[rest.index('-') + 1:].strip()
        p.tasks.append(Task(fp, desc, done=(status == 'x'), in_progress=(status == '~')))
    p.test_command = _extract_test_command(lines)
    p.plan_context = _extract_plan_context(lines)
    return p


def _extract_test_command(lines: list[str]) -> str:
    in_section = False
    for line in lines:
        if re.match(r'^##\s+Test Command\s*$', line):
            in_section = True
            continue
        if in_section and line.startswith('## '):
            break
        if in_section:
            t = line.strip().strip('`').strip()
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
    return next((t for t in p.tasks if not t.done and not t.in_progress), None)


def tasks_remaining(p: Plan) -> bool:
    return next_task(p) is not None


def count_tasks(p: Plan) -> tuple[int, int]:
    return len(p.tasks), sum(1 for t in p.tasks if t.done)


def mark_task_done(path: str, file_path: str) -> None:
    try:
        lines = Path(path).read_text().splitlines(keepends=True)
    except OSError:
        return
    for i, line in enumerate(lines):
        m = _TASK_RE.match(line.rstrip('\n'))
        if m and m.group(1) == ' ' and m.group(2) == file_path:
            lines[i] = '- [x] ' + m.group(2) + m.group(3) + '\n'
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
                   Path(_TASK_RE.match(ln.rstrip('\n')).group(2)).suffix.lstrip('.').lower()
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
        if m and m.group(2) in to_drop:
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


def _csproj_content() -> str:
    """A minimal, canonical SDK-style console project. SDK-style projects glob all
    .cs files in the directory, so no source files need to be listed explicitly."""
    return (
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

    # Level 2 — C# needs a project file to compile.
    if '.cs' in exts and not any(n.endswith('.csproj') for n in names):
        proj = Path(os.getcwd()).name or 'app'
        csproj = f"{proj}.csproj"
        try:
            if not Path(csproj).exists():
                Path(csproj).write_text(_csproj_content())
            if f'] {csproj}' not in text:
                text = text.replace(
                    '## Files\n',
                    f'## Files\n- [x] {csproj} — auto-grounded (C# needs a project file)\n', 1)
            changes.append(f"C#: added {csproj} (dotnet cannot build loose .cs files)")
        except OSError:
            pass

    # Level 3 — a dotnet run command must target a project, not a source file.
    if _dotnet_run_malformed(p.test_command):
        text = _set_test_command(text, 'dotnet run')
        changes.append("rewrote Test Command to canonical 'dotnet run'")

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


def relevant_files_context(p: Plan, target: str) -> str:
    target_dir = str(Path(target).parent)
    module_stem = Path(target).stem.removeprefix('test_')
    buf, count = [], 0
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
            buf.append(f'### {t.file_path}\n```\n{fp.read_text()}\n```\n')
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
        body = '\n'.join(f' * {l}' for l in lines)
        return f'/*\n{body}\n */\n'
    if ext in ('.html', '.xml', '.svg'):
        body = '\n'.join(f'  {l}' for l in lines)
        return f'<!--\n{body}\n-->\n'
    return '\n'.join(f'# {l}' for l in lines) + '\n'


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


def record_failed_repair(label: str, error_snippet: str) -> None:
    plan_file = 'PLAN.md'
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


def repair_history() -> str:
    try:
        data = Path('PLAN.md').read_text()
    except OSError:
        return ''
    header = '## Repair History'
    if header not in data:
        return ''
    return f'\n\n{data[data.index(header):].strip()}\n\nDo NOT repeat approaches listed in Repair History above.'


def record_challenge(label: str, snippet: str = '') -> None:
    plan_file = 'PLAN.md'
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


def get_challenges() -> str:
    try:
        data = Path('PLAN.md').read_text()
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


def clear_challenges() -> None:
    plan_file = 'PLAN.md'
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

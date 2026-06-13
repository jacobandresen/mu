import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_executable_prerequisites(f: str) -> bool:
    """Remove executable names mistakenly used as Makefile prerequisites.

    The LLM writes `venv: pip` or `test: pytestmain` putting shell command names
    in the prerequisites list. Since pip/pytestmain are not Makefile targets, make
    fails with "No rule to make target 'pip'". Removes such tokens from any rule
    where they appear but have no corresponding target definition.
    General: any Makefile with this structural mistake.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False

    _EXECUTABLES: frozenset[str] = frozenset({
        'pip', 'pip3', 'pip2',
        'python', 'python3', 'python2',
        'node', 'npm', 'npx',
        'pytest',
    })
    # Longest-match first so 'python3' beats 'python', 'pip3' beats 'pip'
    _EXE_PREFIXES = ('pytest', 'python3', 'python', 'pip3', 'pip', 'npm', 'node')

    declared: set[str] = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', content, re.MULTILINE))

    def _is_executable_prereq(tok: str) -> bool:
        if tok in declared:
            return False
        if tok in _EXECUTABLES:
            return True
        # Mangled token: starts with exe prefix + more alpha chars (e.g. 'pytestmain')
        # Exclude filesystem paths (contain '/' or '.') and version suffixes like 'python3.11'
        for pfx in _EXE_PREFIXES:
            rest = tok[len(pfx):]
            if tok.startswith(pfx) and rest and rest[0].isalpha() and '/' not in tok and '.' not in tok:
                return True
        return False

    # Match rule headers: `target: prereqs...` — exclude := and :: variants
    rule_re = re.compile(
        r'^(?P<target>[A-Za-z0-9_.%-]+)\s*:(?![=:+?])(?P<prereqs>[^#\\\n]*)(?P<comment>.*)$'
    )

    lines = content.splitlines(keepends=True)
    result = []
    changed = False

    for line in lines:
        m = rule_re.match(line)
        if m:
            target = m.group('target')
            prereq_str = (m.group('prereqs') or '').strip()
            if target not in ('.PHONY', 'PHONY') and prereq_str:
                prereqs = prereq_str.split()
                bad = [p for p in prereqs if _is_executable_prereq(p)]
                if bad:
                    good = [p for p in prereqs if not _is_executable_prereq(p)]
                    comment = m.group('comment') or ''
                    eol = '\n' if line.endswith('\n') else ''
                    if good:
                        line = f"{target}: {' '.join(good)}{comment}{eol}"
                    else:
                        line = f"{target}:{comment}{eol}"
                    changed = True
        result.append(line)

    if not changed:
        return False
    Path(f).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: removed executable prerequisites from {f}")
    return True

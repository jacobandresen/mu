import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_missing_compile_rule(f: str) -> bool:
    """Add a missing compile rule when all: depends on a binary with no build recipe.

    Pattern: `all: hello_world` exists but no `hello_world:` target. This leaves
    Make unable to build the binary. Adds a minimal `NAME: *.c` rule using the
    source files present in the current directory.
    General: applies to any C project missing a binary target, not hello-world-specific.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Find all declared targets
    declared = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', text, re.MULTILINE))
    # Find all: prerequisites that look like binary names (not source files, not .PHONY)
    all_match = re.search(r'^all\s*:\s*(.+)$', text, re.MULTILINE)
    if not all_match:
        return False
    prereqs = all_match.group(1).split()
    # Bail if the `all:` line is malformed — i.e. any token is not a plausible
    # prerequisite (clean name, source file, or make variable). A line like
    # `all: int main(void) {` means the model spilled code onto it; editing such
    # a Makefile does more harm than good, so leave it for other reflexes/repair.
    _VALID_PREREQ = re.compile(
        r'(?:[A-Za-z_][A-Za-z0-9_-]*|[A-Za-z0-9_./-]+\.[A-Za-z0-9]+|\$[({][A-Za-z_]\w*[)}])$')
    if not all(_VALID_PREREQ.match(p) for p in prereqs):
        return False
    # A real binary target is a clean identifier. This guard rejects:
    #   - make variables ($(TARGET), ${PROG}) — they expand to a name defined
    #     elsewhere, so they are never "missing"; treating them as missing made
    #     this reflex re-append a bogus rule on every repair iteration.
    #   - garbage tokens scraped from a corrupted `all:` line (e.g. `\`,
    #     `main(void)`, `{`) when the model emitted C code or escapes onto it.
    _IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*$')
    missing_binaries = [p for p in prereqs
                        if p not in declared and _IDENT.match(p)]
    if not missing_binaries:
        return False
    # Find C source files to use as dependencies. If there are no .c files this
    # Makefile is not for a C project — don't add a bogus compile rule.
    c_sources = list(Path(f).parent.glob('*.c'))
    if not c_sources:
        return False
    src_dep = ' '.join(s.name for s in c_sources)
    additions = []
    for binary in missing_binaries:
        # Idempotency guard: never append a rule for a binary that already has a
        # `binary:` target. Without this the reflex duplicates the rule each time
        # it runs across repair iterations, wedging the loop on "duplicate edit".
        if re.search(rf'^{re.escape(binary)}\s*:', text, re.MULTILINE):
            continue
        additions.append(f'\n{binary}: {src_dep}')
        additions.append(f'\tcc -o {binary} {src_dep} $(CFLAGS) $(LDFLAGS)')
    if not additions:
        return False
    Path(f).write_text(text.rstrip() + '\n' + '\n'.join(additions) + '\n')
    print(f"==> [mu-agent] Reflex: added missing compile rule(s) for {missing_binaries} in {f}")
    return True

import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

# An explicit user entry point: `static [async] void|int|Task[<int>] Main(...)`. This is the
# *only* thing that conflicts with the test SDK's generated Main (CS0017). Top-level
# statements take precedence over the generated Main silently (CS7022 warning, not an error),
# and a pure test project has no Main at all — both NEED the generated one, so neither must
# trip this reflex.
_USER_MAIN = re.compile(r'\bstatic\s+(?:async\s+)?(?:void|int|Task(?:\s*<\s*int\s*>)?)\s+Main\s*\(')
_SKIP_DIRS = {'obj', 'bin', '.git', 'node_modules', '.venv'}


def _has_user_main(search_root: Path) -> bool:
    for cs in search_root.rglob('*.cs'):
        if any(part in _SKIP_DIRS for part in cs.parts):
            continue
        try:
            if _USER_MAIN.search(cs.read_text(errors='replace')):
                return True
        except OSError:
            continue
    return False


def fix_csharp_test_program_conflict(project_dir: str) -> bool:
    """Disable the test SDK's auto-generated entry point only when the project has its
    own ``Main``.

    In the single-project layout the dojo model favors, the csproj is an Exe AND references
    Microsoft.NET.Test.Sdk, which generates a second entry point at build — CS0017 'Program
    has more than one entry point'. The repair model never fixes this (19 FOCUS-hint
    occurrences, 0 resolved, 2026-06-12 run 7); the deterministic fix is
    `<GenerateProgramFile>false</GenerateProgramFile>`.

    It must fire *only* when a user ``Main`` actually exists — else disabling the generated
    entry point leaves the Exe with no entry point at all (**CS5001** 'no Main', observed ×4
    on p4: `fix_csharp_xunit_packages` adds Test.Sdk, then this reflex stripped the generated
    Main the model never replaced). Pure test projects and top-level-statement files keep
    their generated Main.
    """
    changed = False
    for csproj in Path(project_dir).rglob('*.csproj'):
        try:
            text = csproj.read_text()
        except OSError:
            continue
        if 'Microsoft.NET.Test.Sdk' not in text:
            continue
        if '<OutputType>Exe</OutputType>' not in text.replace(' ', ''):
            continue
        if 'GenerateProgramFile' in text:
            continue
        if not _has_user_main(csproj.parent):
            continue  # no user Main ⇒ the generated entry point is needed (avoid CS5001)
        m = re.search(r'(<PropertyGroup>\s*\n)', text)
        if not m:
            continue
        insert = '    <GenerateProgramFile>false</GenerateProgramFile>\n'
        csproj.write_text(text[:m.end()] + insert + text[m.end():])
        print(f"==> [mu-agent] Reflex: disabled test SDK auto entry point in "
              f"{csproj} (GenerateProgramFile=false)")
        changed = True
    return changed

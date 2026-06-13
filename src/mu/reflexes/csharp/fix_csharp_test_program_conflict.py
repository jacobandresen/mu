import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_test_program_conflict(project_dir: str) -> bool:
    """Disable the test SDK's auto-generated entry point when the project has
    its own Main.

    In the single-project layout the dojo model favors, the csproj is an Exe
    (user Main / top-level statements) AND references Microsoft.NET.Test.Sdk,
    which generates a second entry point at build — CS0017 'Program has more
    than one entry point'. The repair model never fixes this (19 FOCUS-hint
    occurrences, 0 resolved, 2026-06-12 run 7); the deterministic fix is
    `<GenerateProgramFile>false</GenerateProgramFile>`. Only fires when both
    conditions hold, so pure test projects keep their generated Main.
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
        m = re.search(r'(<PropertyGroup>\s*\n)', text)
        if not m:
            continue
        insert = '    <GenerateProgramFile>false</GenerateProgramFile>\n'
        csproj.write_text(text[:m.end()] + insert + text[m.end():])
        print(f"==> [mu-agent] Reflex: disabled test SDK auto entry point in "
              f"{csproj} (GenerateProgramFile=false)")
        changed = True
    return changed

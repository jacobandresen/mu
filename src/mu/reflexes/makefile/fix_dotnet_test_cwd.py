import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_dotnet_test_cwd(f: str) -> bool:
    """Add a project/solution path to bare or dir-only `dotnet test` in a Makefile.

    When `dotnet test` is run from the repo root without a project argument,
    or with a directory argument that contains no .csproj, MSBuild fails with
    MSB1003. This reflex finds a .sln (preferred) or test .csproj in the directory
    tree and replaces the command with an explicit project path.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    base = Path(f).parent

    # Match bare `dotnet test` (no argument) OR `dotnet test <dir>` where <dir>
    # has no .csproj in it. The latter appears when the LLM writes `dotnet test tests/`
    # but puts code in tests/ without creating a test .csproj.
    bare_m = re.search(r'\bdotnet\s+test\b(?!\s+\S)', content)
    dir_m = re.search(r'\bdotnet\s+test\s+([\w./\-]+/)', content)

    if not bare_m and not dir_m:
        return False

    # If there's a directory argument, only proceed when that dir has no .csproj
    if dir_m and not bare_m:
        dir_arg = dir_m.group(1).rstrip('/')
        dir_path = base / dir_arg
        if dir_path.exists() and list(dir_path.glob('*.csproj')):
            return False  # dir has a project file — correct already

    # Find best project file in the tree
    sln_files = sorted(base.rglob('*.sln'))
    if sln_files:
        target = sln_files[0]
    else:
        csproj_files = sorted(base.rglob('*.csproj'))
        if not csproj_files:
            return False
        test_csproj = [c for c in csproj_files if 'test' in c.stem.lower()]
        target = test_csproj[0] if test_csproj else csproj_files[0]
    try:
        rel = target.relative_to(base)
    except ValueError:
        return False

    # Replace both patterns with the explicit project path
    new_content = re.sub(
        r'\bdotnet\s+test\b(?:\s+[\w./\-]+/)?\s*',
        f'dotnet test {rel} ',
        content,
    )
    # Clean up trailing spaces introduced by the replacement
    new_content = re.sub(r'dotnet test (\S+) \n', r'dotnet test \1\n', new_content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: added project path to dotnet test in {f}: {rel}")
    return True

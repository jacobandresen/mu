import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_xunit_packages(project_dir: str) -> bool:
    """Add xunit NuGet package references to a .csproj that hosts test files.

    The LLM frequently writes a single-project layout where test files (using
    Xunit; / [Fact] / [Theory]) are compiled into the main .csproj but the xunit
    packages are absent, causing CS0246 'Xunit could not be found' errors on every
    build.

    Fires when: a .csproj exists with no xunit PackageReference, AND at least one
    .cs file anywhere in the project tree contains Xunit markers.  Adds
    Microsoft.NET.Test.Sdk, xunit, and xunit.runner.visualstudio into the first
    <ItemGroup> (or a new one before </Project>).  Skips csproj files that already
    have the packages, or where no .cs test files exist.
    """
    base = Path(project_dir)
    csproj_files = list(base.rglob('*.csproj'))
    if not csproj_files:
        return False

    _XUNIT_MARKERS = re.compile(r'using\s+Xunit\b|\[Fact\]|\[Theory\]|IClassFixture\s*<')
    _SKIP_DIRS = {'obj', 'bin', '.git', 'node_modules', '.venv'}

    changed = False
    for csproj in csproj_files:
        csproj_text = csproj.read_text()
        if 'xunit' in csproj_text.lower():
            continue  # already has xunit package

        # Check whether any .cs file in scope uses xunit
        search_root = csproj.parent
        has_xunit_cs = False
        for cs in search_root.rglob('*.cs'):
            if any(part in _SKIP_DIRS for part in cs.parts):
                continue
            try:
                if _XUNIT_MARKERS.search(cs.read_text(errors='replace')):
                    has_xunit_cs = True
                    break
            except OSError:
                continue
        if not has_xunit_cs:
            continue

        # Add the packages — insert before the first </ItemGroup> or before </Project>
        # Mvc.Testing versions in lockstep with the runtime: its major MUST
        # match the csproj TargetFramework major or restore fails with NU1202
        # ("Package … 8.x is not compatible with net7.0") — 2 stalled
        # p4 sessions per collection run before this followed the TFM.
        tfm = re.search(r'<TargetFramework>\s*net(\d+)\.0', csproj_text)
        mvc_major = tfm.group(1) if tfm else '8'
        new_packages = (
            '  <ItemGroup>\n'
            '    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />\n'
            '    <PackageReference Include="xunit" Version="2.*" />\n'
            '    <PackageReference Include="xunit.runner.visualstudio" Version="2.*" />\n'
            f'    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="{mvc_major}.*" />\n'
            '  </ItemGroup>\n'
        )
        if '</ItemGroup>' in csproj_text:
            # Insert after the last </ItemGroup>
            idx = csproj_text.rfind('</ItemGroup>') + len('</ItemGroup>')
            new_text = csproj_text[:idx] + '\n' + new_packages + csproj_text[idx:]
        elif '</Project>' in csproj_text:
            idx = csproj_text.rfind('</Project>')
            new_text = csproj_text[:idx] + new_packages + csproj_text[idx:]
        else:
            continue
        csproj.write_text(new_text)
        print(f"==> [mu-agent] Reflex: added xunit packages to {csproj}")
        changed = True
    return changed

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403


@lru_cache(maxsize=1)
def _installed_sdk_major() -> int | None:
    """Major version of the installed dotnet SDK (e.g. 10), or None if unknown.

    Grounds the fix in the *real* toolchain: the SDK we actually have decides which
    TargetFrameworks can resolve a runtime."""
    try:
        out = subprocess.run(['dotnet', '--version'], capture_output=True,
                             text=True, timeout=10)
        major = out.stdout.strip().split('.')[0]
        return int(major) if major.isdigit() else None
    except Exception:
        return None


# Microsoft.* runtime-versioned packages AND EntityFrameworkCore (which the sibling
# fix_csharp_package_tfm_mismatch misses): all version in lockstep with the runtime.
_PKG_MAJOR_RE = re.compile(
    r'<PackageReference\s+Include="(?:Microsoft\.(?:AspNetCore|Extensions|EntityFrameworkCore)'
    r'[^"]*|Microsoft\.EntityFrameworkCore)"\s+Version="(\d+)')


def fix_csharp_uninstalled_tfm(project_dir: str) -> bool:
    """Raise a .csproj TargetFramework to the installed SDK when it targets an
    uninstalled framework with newer packages (NU1202 before compilation).

    The model reflexively writes ``<TargetFramework>net5.0</TargetFramework>`` (a
    framework whose runtime is not installed) while referencing e.g.
    ``Microsoft.EntityFrameworkCore`` 8.0.0 — which requires net8.0+. Restore then
    fails with NU1202 *before* any code compiles, masking the real first error
    (archive scan 2026-06-24: 59/61 p10 runs). The sibling
    fix_csharp_package_tfm_mismatch *lowers* packages to the TFM, but that can't help
    when the TFM's runtime isn't installed (only the newer SDK is) and it skips
    EntityFrameworkCore entirely.

    Fires when, for a csproj: TFM major < installed SDK major AND some
    Microsoft.*/EntityFrameworkCore package major exceeds the TFM major AND the
    installed SDK can satisfy that package. Raises TFM to the installed SDK major
    (the one we can actually build) and adds AllowMissingPrunePackageData for net9+
    targets, where SDK 10 otherwise trips NETSDK1226.

    Gated behind ``MU_TFM_GROUNDING`` (default-off) so the p10 A/B keeps a
    byte-identical OFF arm — the NU1202 restore wall masks 97% of backend_build
    runs (archive scan 2026-06-24), so this lever's lift must be measured before
    it ships on by default. Mirrors MU_ASPNET_ENTRYPOINT / MU_S2_TYPE_REFLEXES.
    """
    if os.environ.get('MU_TFM_GROUNDING') != '1':
        return False
    sdk_major = _installed_sdk_major()
    if sdk_major is None:
        return False

    changed = False
    for csproj in Path(project_dir).rglob('*.csproj'):
        if any(s in csproj.parts for s in ('obj', 'bin')):
            continue
        try:
            text = csproj.read_text()
        except OSError:
            continue
        tfm = re.search(r'<TargetFramework>\s*net(\d+)\.0\s*</TargetFramework>', text)
        if not tfm:
            continue
        tfm_major = int(tfm.group(1))
        if tfm_major >= sdk_major:
            continue  # already at/above the installed SDK — nothing to raise
        pkg_majors = [int(m) for m in _PKG_MAJOR_RE.findall(text)]
        max_pkg = max(pkg_majors, default=0)
        if max_pkg <= tfm_major or max_pkg > sdk_major:
            continue  # no offending package, or a package even newer than our SDK

        new_text = re.sub(
            r'(<TargetFramework>\s*)net\d+\.0(\s*</TargetFramework>)',
            rf'\g<1>net{sdk_major}.0\g<2>', text, count=1)
        if sdk_major >= 9 and 'AllowMissingPrunePackageData' not in new_text:
            # Regex (not literal .replace) so internal whitespace in the
            # <TargetFramework> tag can't silently no-op the insertion.
            new_text = re.sub(
                r'(<TargetFramework>\s*net\d+\.0\s*</TargetFramework>)',
                r'\g<1>\n    '
                r'<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>',
                new_text, count=1)
        if new_text != text:
            csproj.write_text(new_text)
            print(f"==> [mu-agent] Reflex: raised TargetFramework net{tfm_major}.0 → "
                  f"net{sdk_major}.0 (installed SDK; packages required ≥ net{max_pkg}.0) in {csproj}")
            changed = True
    return changed

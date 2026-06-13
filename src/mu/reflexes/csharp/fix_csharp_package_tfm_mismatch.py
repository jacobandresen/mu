import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_package_tfm_mismatch(project_dir: str) -> bool:
    """Align runtime-versioned Microsoft.* package majors with the TFM.

    Microsoft.AspNetCore.* and Microsoft.Extensions.* packages version in
    lockstep with the runtime: referencing major N from a TargetFramework
    below netN.0 fails restore with NU1202 ("not compatible"). The model
    routinely mixes e.g. net7.0 with Version="8.*" (or "8.0.28"). Lower the
    package major to the TFM major — general .NET versioning convention,
    independent of any particular problem.
    """
    changed = False
    for csproj in Path(project_dir).rglob('*.csproj'):
        try:
            text = csproj.read_text()
        except OSError:
            continue
        tfm = re.search(r'<TargetFramework>\s*net(\d+)\.0', text)
        if not tfm:
            continue
        tfm_major = int(tfm.group(1))

        def _align(m: re.Match) -> str:
            pkg_major = int(m.group('major'))
            if pkg_major <= tfm_major:
                return m.group(0)
            return f'{m.group("head")}{tfm_major}.*{m.group("tail")}'

        new_text = re.sub(
            r'(?P<head><PackageReference\s+Include="Microsoft\.(?:AspNetCore|Extensions)\.[^"]*"\s+'
            r'Version=")(?P<major>\d+)(?:\.[\d*][^"]*)?(?P<tail>")',
            _align, text)
        if new_text != text:
            csproj.write_text(new_text)
            print(f"==> [mu-agent] Reflex: aligned Microsoft.* package major(s) "
                  f"with net{tfm_major}.0 in {csproj}")
            changed = True
    return changed

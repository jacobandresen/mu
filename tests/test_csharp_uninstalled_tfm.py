"""Regression: raise a model-authored uninstalled TFM to the installed SDK.

2026-06-24 archive scan: 59/61 p10 backend_build runs die at NuGet restore
(NU1202) *before* compilation — the model writes
``<TargetFramework>net5.0</TargetFramework>`` (runtime not installed) while
referencing e.g. EntityFrameworkCore 8.0.0 (needs net8.0+). The sibling
fix_csharp_package_tfm_mismatch *lowers* packages to the TFM, which can't help
when the TFM's runtime isn't installed and skips EntityFrameworkCore entirely.

Gated behind MU_TFM_GROUNDING so the p10 A/B keeps a byte-identical OFF arm.
"""

import importlib
from pathlib import Path

import pytest

from mu.reflexes.csharp import fix_csharp_uninstalled_tfm

# The package re-exports the function under this name, shadowing the submodule;
# import_module returns the actual module so _installed_sdk_major can be patched.
mod = importlib.import_module('mu.reflexes.csharp.fix_csharp_uninstalled_tfm')

CSPROJ_NET5_EFCORE8 = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net5.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.0.0" />
  </ItemGroup>
</Project>
"""


@pytest.fixture
def gate_on(monkeypatch):
    """Enable the lever; the gate is the default-off A/B switch."""
    monkeypatch.setenv('MU_TFM_GROUNDING', '1')


def _patch_sdk(monkeypatch, major):
    monkeypatch.setattr(mod, '_installed_sdk_major', lambda: major)


def test_gate_off_no_change(monkeypatch, tmp_path: Path):
    """Default-off: untouched even with a clear offender (byte-identical OFF arm)."""
    monkeypatch.delenv('MU_TFM_GROUNDING', raising=False)
    _patch_sdk(monkeypatch, 10)
    (tmp_path / 'app.csproj').write_text(CSPROJ_NET5_EFCORE8)
    assert not fix_csharp_uninstalled_tfm(str(tmp_path))
    assert (tmp_path / 'app.csproj').read_text() == CSPROJ_NET5_EFCORE8


def test_raises_tfm_to_sdk_and_adds_prune_flag(monkeypatch, gate_on, tmp_path: Path):
    """net5.0 + EFCore 8 → net10.0, and SDK 10 (>=9) gets the prune flag."""
    _patch_sdk(monkeypatch, 10)
    (tmp_path / 'app.csproj').write_text(CSPROJ_NET5_EFCORE8)
    assert fix_csharp_uninstalled_tfm(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert '<TargetFramework>net10.0</TargetFramework>' in text
    assert '<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>' in text


def test_prune_flag_inserted_despite_tag_whitespace(monkeypatch, gate_on, tmp_path: Path):
    """Whitespace inside the <TargetFramework> tag must not no-op the flag insertion."""
    _patch_sdk(monkeypatch, 10)
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET5_EFCORE8.replace(
            '<TargetFramework>net5.0</TargetFramework>',
            '<TargetFramework>\n      net5.0\n    </TargetFramework>'))
    assert fix_csharp_uninstalled_tfm(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert 'net10.0' in text
    assert '<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>' in text


def test_sdk8_raise_without_prune_flag(monkeypatch, gate_on, tmp_path: Path):
    """SDK 8 (<9) raises the TFM but does not emit the net9+ prune flag."""
    _patch_sdk(monkeypatch, 8)
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET5_EFCORE8.replace('Version="8.0.0"', 'Version="7.0.0"'))
    assert fix_csharp_uninstalled_tfm(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert '<TargetFramework>net8.0</TargetFramework>' in text
    assert 'AllowMissingPrunePackageData' not in text


def test_tfm_at_or_above_sdk_left_alone(monkeypatch, gate_on, tmp_path: Path):
    """Nothing to raise when the TFM already meets the installed SDK."""
    _patch_sdk(monkeypatch, 10)
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET5_EFCORE8.replace('net5.0', 'net10.0'))
    assert not fix_csharp_uninstalled_tfm(str(tmp_path))


def test_no_offending_package_left_alone(monkeypatch, gate_on, tmp_path: Path):
    """An old TFM with only TFM-compatible packages is not the NU1202 case."""
    _patch_sdk(monkeypatch, 10)
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET5_EFCORE8.replace('Version="8.0.0"', 'Version="5.0.0"'))
    assert not fix_csharp_uninstalled_tfm(str(tmp_path))


def test_package_newer_than_sdk_left_alone(monkeypatch, gate_on, tmp_path: Path):
    """If a package needs a framework newer than our SDK, raising can't satisfy it."""
    _patch_sdk(monkeypatch, 8)
    # Package (net9) needs a framework newer than the installed SDK (net8); the
    # max_pkg > sdk_major guard must leave it alone rather than raise to net8.
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET5_EFCORE8.replace('Version="8.0.0"', 'Version="9.0.0"'))
    assert not fix_csharp_uninstalled_tfm(str(tmp_path))


def test_unknown_sdk_left_alone(monkeypatch, gate_on, tmp_path: Path):
    """No installed SDK detected → no change (can't ground the fix)."""
    _patch_sdk(monkeypatch, None)
    (tmp_path / 'app.csproj').write_text(CSPROJ_NET5_EFCORE8)
    assert not fix_csharp_uninstalled_tfm(str(tmp_path))

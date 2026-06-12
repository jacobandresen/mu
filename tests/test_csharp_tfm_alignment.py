"""Regression: Microsoft.* package majors must follow the csproj TFM.

2026-06-12 collection runs: fix_csharp_xunit_packages injected
Mvc.Testing Version="8.*" into csprojs targeting net7.0 → NU1202 restore
failure ("Package … is not compatible with net7.0"), 2 stalled p4 sessions
per run. fix_csharp_package_tfm_mismatch covers model-written mismatches.
"""

from pathlib import Path

from mu.reflexes.csharp import (fix_csharp_package_tfm_mismatch,
                                fix_csharp_xunit_packages)

CSPROJ_NET7 = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.*" />
    <PackageReference Include="Microsoft.Extensions.Logging" Version="8.0.28" />
    <PackageReference Include="xunit" Version="2.*" />
  </ItemGroup>
</Project>
"""

XUNIT_TEST_CS = """using Xunit;

public class FibTests
{
    [Fact]
    public void Works() { Assert.True(true); }
}
"""


def test_mismatched_majors_lowered_to_tfm(tmp_path: Path):
    (tmp_path / 'app.csproj').write_text(CSPROJ_NET7)
    assert fix_csharp_package_tfm_mismatch(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert '"Microsoft.AspNetCore.Mvc.Testing" Version="7.*"' in text
    assert '"Microsoft.Extensions.Logging" Version="7.*"' in text
    assert '"xunit" Version="2.*"' in text  # non-runtime package untouched


def test_matching_major_left_alone(tmp_path: Path):
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET7.replace('net7.0', 'net8.0'))
    assert not fix_csharp_package_tfm_mismatch(str(tmp_path))


def test_lower_major_left_alone(tmp_path: Path):
    (tmp_path / 'app.csproj').write_text(
        CSPROJ_NET7.replace('net7.0', 'net9.0'))
    assert not fix_csharp_package_tfm_mismatch(str(tmp_path))


def test_xunit_injection_follows_tfm(tmp_path: Path):
    (tmp_path / 'app.csproj').write_text(
        '<Project Sdk="Microsoft.NET.Sdk">\n'
        '  <PropertyGroup>\n'
        '    <TargetFramework>net7.0</TargetFramework>\n'
        '  </PropertyGroup>\n'
        '</Project>\n')
    (tmp_path / 'FibTests.cs').write_text(XUNIT_TEST_CS)
    assert fix_csharp_xunit_packages(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert '"Microsoft.AspNetCore.Mvc.Testing" Version="7.*"' in text

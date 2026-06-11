"""Tests for fix_csharp_xunit_packages: adds xunit NuGet packages to a .csproj
that hosts test files using Xunit but lacks the package references."""
import textwrap
from pathlib import Path

import pytest

from mu.reflexes.csharp import fix_csharp_xunit_packages


@pytest.fixture()
def project(tmp_path):
    return tmp_path


def _csproj(include_ef=False):
    packages = ''
    if include_ef:
        packages = (
            '  <ItemGroup>\n'
            '    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.*" />\n'
            '  </ItemGroup>\n'
        )
    return textwrap.dedent(f"""\
        <Project Sdk="Microsoft.NET.Sdk.Web">
          <PropertyGroup>
            <TargetFramework>net8.0</TargetFramework>
          </PropertyGroup>
        {packages}</Project>
        """)


def _test_cs():
    return textwrap.dedent("""\
        using Xunit;
        using Microsoft.AspNetCore.Mvc.Testing;

        public class ApiTests : IClassFixture<WebApplicationFactory<Program>> {
            [Fact]
            public void Test() { }
        }
        """)


def test_adds_xunit_packages_when_missing(project):
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj())
    (project / 'tests').mkdir()
    (project / 'tests' / 'ApiTests.cs').write_text(_test_cs())

    result = fix_csharp_xunit_packages(str(project))

    assert result is True
    content = csproj.read_text()
    assert '<PackageReference Include="xunit"' in content
    assert '<PackageReference Include="xunit.runner.visualstudio"' in content
    assert '<PackageReference Include="Microsoft.NET.Test.Sdk"' in content


def test_no_fire_when_xunit_already_present(project):
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj() + '<!-- xunit already here somehow -->')
    (project / 'ApiTests.cs').write_text(_test_cs())

    result = fix_csharp_xunit_packages(str(project))

    assert result is False


def test_no_fire_when_no_test_cs(project):
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj())
    (project / 'Program.cs').write_text('// no xunit here\nvar app = WebApplication.Create();\n')

    result = fix_csharp_xunit_packages(str(project))

    assert result is False


def test_no_fire_when_no_csproj(project):
    (project / 'ApiTests.cs').write_text(_test_cs())

    result = fix_csharp_xunit_packages(str(project))

    assert result is False


def test_idempotent(project):
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj())
    (project / 'ApiTests.cs').write_text(_test_cs())

    fix_csharp_xunit_packages(str(project))
    content_after_first = csproj.read_text()
    fix_csharp_xunit_packages(str(project))
    content_after_second = csproj.read_text()

    assert content_after_first == content_after_second


def test_preserves_existing_item_group(project):
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj(include_ef=True))
    (project / 'ApiTests.cs').write_text(_test_cs())

    fix_csharp_xunit_packages(str(project))

    content = csproj.read_text()
    assert 'EntityFrameworkCore.Sqlite' in content
    assert '<PackageReference Include="xunit"' in content


def test_detects_fact_attribute_without_using_xunit(project):
    """[Fact] alone (implicit using) should also trigger the fix."""
    csproj = project / 'app.csproj'
    csproj.write_text(_csproj())
    tests_dir = project / 'tests'
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / 'MyTests.cs').write_text('[Fact]\npublic void T() { }\n')

    result = fix_csharp_xunit_packages(str(project))

    assert result is True

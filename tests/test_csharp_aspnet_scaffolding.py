"""Tests for csharp-aspnet-scaffolding challenge."""
from pathlib import Path

import pytest


class TestCSharpAspNetScaffolding:
    """ASP.NET scaffolding issues."""

    def test_missing_test_csproj(self, tmp_path):
        """Missing test project file."""
        (tmp_path / 'WebApp').mkdir()
        (tmp_path / 'WebApp' / 'WebApp.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
        (tmp_path / 'WebApp' / 'Tests').mkdir()
        (tmp_path / 'WebApp' / 'Tests' / 'UnitTest1.cs').write_text('using Xunit;\nnamespace WebApp.Tests { public class UnitTest1 { [Fact] public void Test1() { Assert.True(true); } } }')
        
        assert (tmp_path / 'WebApp' / 'WebApp.csproj').exists()
        assert not (tmp_path / 'WebApp' / 'Tests' / 'WebApp.Tests.csproj').exists()

    def test_missing_entry_point(self, tmp_path):
        """Missing Program.cs."""
        (tmp_path / 'WebApp').mkdir()
        (tmp_path / 'WebApp' / 'WebApp.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>')
        (tmp_path / 'WebApp' / 'Controllers').mkdir()
        (tmp_path / 'WebApp' / 'Controllers' / 'HomeController.cs').write_text('using Microsoft.AspNetCore.Mvc;\nnamespace WebApp.Controllers { public class HomeController : Controller { public IActionResult Index() { return View(); } } }')
        
        assert (tmp_path / 'WebApp' / 'WebApp.csproj').exists()
        assert not (tmp_path / 'WebApp' / 'Program.cs').exists()

    def test_duplicate_types_across_files(self, tmp_path):
        """Duplicate class definitions."""
        (tmp_path / 'File1.cs').write_text('namespace MyApp { public class MyService { public void DoWork() { } } }')
        (tmp_path / 'File2.cs').write_text('namespace MyApp { public class MyService { public void DoOtherWork() { } } }')
        
        content1 = (tmp_path / 'File1.cs').read_text()
        content2 = (tmp_path / 'File2.cs').read_text()
        assert 'public class MyService' in content1
        assert 'public class MyService' in content2

    def test_ef_core_scaffolding_issues(self, tmp_path):
        """EF Core DbContext issues."""
        (tmp_path / 'MyDbContext.cs').write_text('using Microsoft.EntityFrameworkCore;\nnamespace MyApp.Data { public class MyDbContext : DbContext { public MyDbContext(DbContextOptions<MyDbContext> options) : base(options) { } } }')
        (tmp_path / 'appsettings.json').write_text('{"ConnectionStrings": {"DefaultConnection": "Server=localhost;Database=MyDb;"}}')
        
        assert (tmp_path / 'MyDbContext.cs').exists()
        assert (tmp_path / 'appsettings.json').exists()
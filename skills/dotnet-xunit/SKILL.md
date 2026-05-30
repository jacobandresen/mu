---
name: dotnet-xunit
description: xUnit + WebApplicationFactory test rules for ASP.NET Core — test .csproj setup, in-memory SQLite, no real server. Apply to any ASP.NET Core API that needs tests.
---

## 1. Test .csproj — reference the API project

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />
    <PackageReference Include="xunit" Version="2.*" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.*" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.*" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../backend/backend.csproj" />
  </ItemGroup>
</Project>
```

Adjust `ProjectReference` path to match your project layout.

## 2. Test class — WebApplicationFactory with in-memory SQLite

```csharp
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using System.Net.Http.Json;

public class ApiTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ApiTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.WithWebHostBuilder(b =>
            b.ConfigureServices(s =>
            {
                s.AddDbContext<AppDb>(o => o.UseSqlite("Data Source=:memory:"));
            }))
            .CreateClient();
    }

    [Fact]
    public async Task GetItems_ReturnsSeededData()
    {
        var items = await _client.GetFromJsonAsync<List<Item>>("/api/items");
        Assert.NotNull(items);
        Assert.NotEmpty(items);
    }
}
```

**Critical rules:**
- Always override the DbContext to use `"Data Source=:memory:"` in tests — never use the production `.db` file.
- `WebApplicationFactory<Program>` requires `public partial class Program {}` in Program.cs.
- Do NOT start a real HTTP server. `factory.CreateClient()` runs the app in-process with no port.
- Test command: `dotnet test` — never `dotnet run`.

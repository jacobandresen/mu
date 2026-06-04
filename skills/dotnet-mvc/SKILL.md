---
name: dotnet-mvc
description: ASP.NET Core Web API rules — EF Core SQLite, Models/Controllers layout, Program.cs wiring, and xUnit + WebApplicationFactory tests with in-memory SQLite. Apply to any ASP.NET Core API task.
---

## Folder layout
```
backend/  Models/ (entities)  Infrastructure/ (AppDb)  Controllers/  Program.cs  backend.csproj
tests/    ApiTests.cs  tests.csproj
```

## backend.csproj — EF Core + SQLite
```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.*" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.*" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.*" />
  </ItemGroup>
</Project>
```

## Program.cs — wire controllers + EF Core
```csharp
using Microsoft.EntityFrameworkCore;
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDb>(o => o.UseSqlite("Data Source=app.db"));
builder.Services.AddControllers();
var app = builder.Build();
using (var scope = app.Services.CreateScope())
    scope.ServiceProvider.GetRequiredService<AppDb>().Database.EnsureCreated();  // never EF migrations
app.MapControllers();
app.Run();
public partial class Program { }   // MUST be last line — WebApplicationFactory needs it
```
- Never use EF migrations — call `db.Database.EnsureCreated()`.
- All routes go in `Controllers/` classes (`[ApiController]`, `[Route("api/[controller]")]`), not inline `app.MapGet`.

## Entities & DbContext
```csharp
// Models/Item.cs
public class Item { public int Id { get; set; } public string Name { get; set; } = ""; }
// Infrastructure/AppDb.cs
using Microsoft.EntityFrameworkCore;
public class AppDb : DbContext {
    public AppDb(DbContextOptions<AppDb> o) : base(o) { }
    public DbSet<Item> Items => Set<Item>();
}
```
Inject `AppDb` into controllers via the constructor.

## tests.csproj — reference the API project
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><IsPackable>false</IsPackable></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />
    <PackageReference Include="xunit" Version="2.*" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.*" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.*" />
  </ItemGroup>
  <ItemGroup><ProjectReference Include="../backend/backend.csproj" /></ItemGroup>
</Project>
```

## xUnit test — in-process, in-memory SQLite
```csharp
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using System.Net.Http.Json;

public class ApiTests : IClassFixture<WebApplicationFactory<Program>> {
    private readonly HttpClient _client;
    public ApiTests(WebApplicationFactory<Program> f) =>
        _client = f.WithWebHostBuilder(b => b.ConfigureServices(s =>
            s.AddDbContext<AppDb>(o => o.UseSqlite("Data Source=:memory:")))).CreateClient();

    [Fact]
    public async Task GetItems_Works() {
        var items = await _client.GetFromJsonAsync<List<Item>>("/api/items");
        Assert.NotNull(items);
    }
}
```
- Override the DbContext to `Data Source=:memory:` in tests — never the production `.db`.
- Do NOT start a real server. `factory.CreateClient()` runs in-process. Test command: `dotnet test` — never `dotnet run`.

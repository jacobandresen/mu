---
name: dotnet-mvc
description: ASP.NET Core Web API rules — EF Core SQLite, Models/ folder for entities, Controllers/ folder for controllers, Program.cs wiring. Apply to any ASP.NET Core API task.
---

## Folder layout

```
backend/
  Models/          ← entities, one file per entity (model phase)
  Infrastructure/  ← AppDb DbContext              (model phase)
  Controllers/     ← API controllers              (backend phase)
  Program.cs
  backend.csproj
tests/
  ApiTests.cs
  tests.csproj
```

## 1. .csproj — EF Core + SQLite packages

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.*" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.*" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.*" />
  </ItemGroup>
</Project>
```

## 2. Program.cs — wire up controllers and EF Core

```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDb>(opt =>
    opt.UseSqlite("Data Source=app.db"));
builder.Services.AddCors(o => o.AddDefaultPolicy(p =>
    p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));
builder.Services.AddControllers();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDb>();
    db.Database.EnsureCreated();   // never use EF migrations
    // seed data here if needed
    db.SaveChanges();
}

app.UseCors();
app.MapControllers();
app.Run();

public partial class Program { }   // required for WebApplicationFactory
```

**Critical rules:**
- Never use EF Core migrations (`dotnet ef migrations add`). Call `db.Database.EnsureCreated()` instead.
- The `public partial class Program {}` line must be the last line — WebApplicationFactory needs it.
- All routes go in controller classes in `Controllers/`. Do NOT use inline `app.MapGet` / `app.MapPost`.

## 3. Models/ — entities

Place each entity in `Models/`, one file per class. Example:

```csharp
// Models/Item.cs
public class Item
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
}
```

## 4. Infrastructure/ — DbContext

Place `AppDb` in `Infrastructure/`. Example:

```csharp
// Infrastructure/AppDb.cs
using Microsoft.EntityFrameworkCore;

public class AppDb : DbContext
{
    public AppDb(DbContextOptions<AppDb> options) : base(options) { }
    public DbSet<Item> Items => Set<Item>();
}
```

## 5. Controllers/ — API controllers

Place each controller in `Controllers/`. Inject AppDb via the constructor. Example:

```csharp
// Controllers/ItemsController.cs
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

[ApiController]
[Route("api/[controller]")]
public class ItemsController : ControllerBase
{
    private readonly AppDb _db;
    public ItemsController(AppDb db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> GetAll() =>
        Ok(await _db.Items.ToListAsync());

    [HttpPost]
    public async Task<IActionResult> Create(Item item)
    {
        _db.Items.Add(item);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(GetAll), new { id = item.Id }, item);
    }
}
```

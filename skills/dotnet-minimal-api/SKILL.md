---
name: dotnet-minimal-api
description: ASP.NET Core minimal API rules — EF Core SQLite setup, Program.cs structure, seed data, .csproj packages. Apply to any ASP.NET Core minimal API task.
---

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

## 2. Program.cs — minimal API with EF Core and seed data

```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDb>(opt =>
    opt.UseSqlite("Data Source=app.db"));
builder.Services.AddCors(o => o.AddDefaultPolicy(p =>
    p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDb>();
    db.Database.EnsureCreated();   // never use EF migrations in dojo tasks
    // seed data here if needed
    db.SaveChanges();
}

app.UseCors();
app.MapGet("/api/items", async (AppDb db) => await db.Items.ToListAsync());
app.Run();

public partial class Program { }   // required for WebApplicationFactory
```

**Critical rules:**
- Never use EF Core migrations (`dotnet ef migrations add`). Call `db.Database.EnsureCreated()` instead.
- The `public partial class Program {}` line must be the last line — WebApplicationFactory needs it.
- Do NOT use controller classes. Map all routes inline with `app.MapGet`, `app.MapPost`, etc.

## 3. DbContext and model — one file

```csharp
using Microsoft.EntityFrameworkCore;

public class Item
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
}

public class AppDb : DbContext
{
    public AppDb(DbContextOptions<AppDb> options) : base(options) { }
    public DbSet<Item> Items => Set<Item>();
}
```

Keep the model and DbContext in a single file alongside Program.cs.

---
name: task-planner-csharp
description: C#/dotnet-specific planning rules for PLAN.md. Loaded alongside task-planner when the goal involves C#, dotnet, or csharp.
---

# C# / dotnet Planning Rules

Every dotnet project requires a `.csproj` file. Without it, `dotnet run` and `dotnet test` fail immediately with MSB1003. List the `.csproj` **first** in ## Files, before any `.cs` files.

- Lint tool: `dotnet format` (built-in with SDK — list in ## Dependencies).

## File layout

**Simple program** (no separate test project):
```
- [ ] fibonacci.csproj
- [ ] Program.cs
```
Test Command: `dotnet run --project fibonacci.csproj`

**With tests** (separate test project):
```
- [ ] src/app.csproj
- [ ] src/Program.cs
- [ ] tests/tests.csproj
- [ ] tests/Tests.cs
```
Test Command: `dotnet test tests/tests.csproj`

## Critical rule

**NEVER** put `dotnet test` or `dotnet run` in Test Command unless the referenced `.csproj` appears in ## Files.

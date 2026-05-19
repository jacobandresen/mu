---
name: task-planner-csharp
description: C#/dotnet-specific planning rules. Loaded when goal involves C#, dotnet, or csharp.
---

- List `.csproj` FIRST in ## Files — without it, `dotnet run`/`dotnet test` fail with MSB1003.
- Simple program: `fibonacci.csproj` then `Program.cs`. Test: `dotnet run --project fibonacci.csproj`
- With tests: `src/app.csproj`, `src/Program.cs`, `tests/tests.csproj`, `tests/Tests.cs`. Test: `dotnet test tests/tests.csproj`
- NEVER use `dotnet run`/`dotnet test` unless the `.csproj` appears in ## Files.
- Lint: `dotnet format` (built-in)

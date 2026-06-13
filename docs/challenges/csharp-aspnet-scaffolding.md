# C# / ASP.NET scaffolding

_‹ [All challenges](README.md)_

- **ID:** `csharp-aspnet-scaffolding`
- **Group:** Full-stack orchestration / multi-file
- **Open list:** [item 8](README.md#open)
- **Status:** partial — many reflexes; p10 still 0-pass

## What it is

Multi-project .NET needs scaffolding a minimal SDK template lacks: a test csproj, EF Core/SQLite/ASP.NET package refs, a single entry point, no duplicate types, and `dotnet test` run where a project file exists.

## Problems affected

- [p4-fibonacci](../problems/p4-fibonacci.md) — CS0017 two `Main` entry points (run 7 ×19) — the test SDK auto-generates a second
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — CS0101 duplicate types ×14, MSB1003 no project ×8, CS0053 inconsistent accessibility ×8 (run 7; 0/12)

## Relevant reflexes & mechanisms

- `fix_csharp_xunit_packages` — adds the xunit package set, version following the TFM
- `fix_csharp_package_tfm_mismatch` — aligns `Microsoft.*` package majors with the TargetFramework (NU1202)
- `fix_csharp_test_program_conflict` — sets `GenerateProgramFile=false` when an Exe also references the test SDK (CS0017)
- `fix_dotnet_test_cwd` — points `dotnet test` at a dir that has a csproj (MSB1003)
- `run_staged orphan cleanup` — deletes stale duplicate `.cs` across stages (CS0101)

## Residual / notes

p10 is **the open problem**: cascading errors across backend/test/frontend stages where repair oscillates. See [TODO.md](../../TODO.md) item 1.

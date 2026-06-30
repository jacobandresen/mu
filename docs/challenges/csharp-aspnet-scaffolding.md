# C# / ASP.NET scaffolding

_‹ [All challenges](README.md)_

- **ID:** `csharp-aspnet-scaffolding`
- **Group:** Full-stack orchestration / multi-file
- **Status:** partial — many reflexes

## What it is

Multi-project .NET needs scaffolding a minimal SDK template lacks: a test csproj, EF Core/SQLite/ASP.NET package refs, a single entry point, no duplicate types, and `dotnet test` run where a project file exists.

## Problems affected

- [p4-fibonacci](../problems/p4-fibonacci.md) — CS0017 two `Main` entry points
- [p14-fullstack-js-blog](../problems/p14-fullstack-js-blog.md) — CS0101 duplicate types, MSB1003 no project
- [p15-dotnet-vue-blog](../problems/p15-dotnet-vue-blog.md) — CS0017 two `Main` entry points, CS0101 duplicate types, MSB1003 no project, CS0053 inconsistent accessibility

## Relevant reflexes & mechanisms

- [`fix_csharp_xunit_packages`](../../src/mu/reflexes/csharp/fix_csharp_xunit_packages.py) — adds the xunit package set, version following the TFM
- [`fix_csharp_package_tfm_mismatch`](../../src/mu/reflexes/csharp/fix_csharp_package_tfm_mismatch.py) — aligns `Microsoft.*` package majors with the TargetFramework (NU1202)
- [`fix_csharp_test_program_conflict`](../../src/mu/reflexes/csharp/fix_csharp_test_program_conflict.py) — sets `GenerateProgramFile=false` when an Exe also references the test SDK (CS0017)
- [`fix_dotnet_test_cwd`](../../src/mu/reflexes/makefile/fix_dotnet_test_cwd.py) — points `dotnet test` at a dir that has a csproj (MSB1003)
- `run_staged orphan cleanup` — deletes stale duplicate `.cs` across stages (CS0101)

## Residual / notes

The .NET ladder (p4 simple, p14 full-stack JS, p15 full-stack Vue/TS) is addressed via the
prototype-then-refine layer split and the C# reflex suite.

# p4-fibonacci — C# Fibonacci

**Toolchains:** dotnet · **Difficulty:** moderate

## Problem statement

> write the fibonacci sequence using C#. Use the dotnet command to compile
> C#.

## What it does

A C# console program that prints the Fibonacci sequence, with an xUnit
test file compiled into the same project. Single-project `dotnet test`
exercises the C# toolchain end to end: csproj generation, package
restore, and the interplay between a `Main` entry point and a test host.

## Major challenges

- **Entry-point conflicts** — `Program.cs` and the test file both defining
  `Main` (CS0017), or top-level statements mixed with declarations
  (CS8803/CS1022). Diagnose emits actionable FOCUS hints for both.
- **Stuttered generation** — the same method-signature opener emitted 3–4
  times with orphaned `[Fact]` attributes between (dominant bucket of the
  2026-06-12 run-4 collection; [CHALLENGES.md](../CHALLENGES.md) items 4, 17).
- **Package/TFM mismatch** — `Microsoft.AspNetCore.Mvc.Testing 8.*`
  injected into a `net7.0` project fails restore with NU1202.

## Related reflexes

- `fix_csharp_consecutive_duplicate_signatures` — collapses stuttered
  signature openers.
- `fix_csharp_xunit_packages` — adds the xunit package set to a csproj
  hosting test files (version now follows the TFM);
  `fix_csharp_package_tfm_mismatch` — aligns `Microsoft.*` package majors
  with the TargetFramework.
- `fix_csharp_missing_braces`, `fix_csharp_duplicate_classes`,
  `fix_csharp_missing_using`, `fix_csharp_keyword_prefix_artifacts`,
  `fix_csharp_verbatim_string_escape`.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 6/12 |
| Median tokens / run | 11,278 prompt · 617 generated |
| Median repair iters | 6 |
| Heaviest phase | repair |

**Dominant errors this run:**
- **CS0017: two Main entry points** (×19 across iterations) — the test SDK auto-generates a second `Main`. The FOCUS hint never resolved it; round 7 added `fix_csharp_test_program_conflict` (GenerateProgramFile=false).
- `CS1519: Invalid token 'for' in a member declaration` (×3) — malformed method body.
- Outcomes: final test gate failed (×6).

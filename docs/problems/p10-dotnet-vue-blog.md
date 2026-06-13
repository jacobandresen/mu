# p10-dotnet-vue-blog — ASP.NET + Vue full-stack blog

**Toolchains:** dotnet, node · **Difficulty:** hard

## Problem statement

> write a blog application with an ASP.NET Core minimal API backend and a
> Vue 3 TypeScript frontend. Backend: use EF Core with SQLite, define a
> Post model with Id, Title, and Content, seed one example post titled
> 'Hello World' on startup, expose GET /api/posts returning JSON. Include
> an xUnit test project using WebApplicationFactory that calls GET
> /api/posts and asserts the 'Hello World' post is present. Frontend: Vue
> 3 TypeScript app built with Vite that fetches and displays posts, with a
> Vitest test that mocks fetch and asserts the post is rendered. Provide a
> Makefile with an install target (npm install in frontend/) and a test
> target that runs dotnet test and npx vitest run.

## What it does

The capstone: two coordinated projects — an EF Core/SQLite minimal API
with a WebApplicationFactory integration test, and a Vue 3 frontend with a
fetch-mocking Vitest test — driven by one Makefile. It usually runs in
architect (staged) mode, which plans backend, frontend, and integration as
separate stages, each spawning its own session.

## Major challenges

- **Multi-project ceiling** — cascading CS errors across `Program.cs`,
  the test project, and shared types; repair oscillates between them
  ([lessons](../challenges/lessons.md) item 8). The strongest residual
  model-limited problem in the set.
- **Scaffolding completeness** — Tests.csproj (auto-created by
  `ground_plan`), EF Core/SQLite/ASP.NET package references, occasional
  malformed `.csproj` XML (MSB4067), package majors above the TFM
  (NU1202).
- **Stage hygiene** — stale `.cs` duplicates from earlier stages cause
  CS0101/CS0260; long staged prompts pressed against the context window
  until budget enforcement (item 11).

## Related reflexes

- The full C# family of [p4](p4-fibonacci.md), plus
  `fix_csharp_package_tfm_mismatch` and `fix_dotnet_test_cwd`.
- The test-gate reapply hook deletes orphaned `.cs` duplicates that the
  root csproj would otherwise compile twice.
- The Vue/Vitest family of [p9](p9-vue-todo.md) for the frontend stage.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 0/12 |
| Median tokens / run | 32,914 prompt · 1,597 generated |
| Median repair iters | 6 |
| Heaviest phase | writer |

**Dominant errors this run:**
- **CS0101: duplicate definition in global namespace** (×14) — the multi-project layout duplicates types (`AppDb`, controllers) across files.
- **MSB1003: no project/solution file** (×8) — `dotnet test` run from a directory with no csproj.
- `CS0053: inconsistent accessibility` (×8) — public API exposing a less-accessible EF type.
- Outcomes: final test gate failed (×7), tests still failing after repair (×5). **0/12 — the open problem.**

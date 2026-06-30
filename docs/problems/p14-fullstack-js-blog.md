# p14-fullstack-js-blog

_‹ [All problems](../README.md)_

- **Goal:** build a full-stack blog application. Backend: an ASP.NET Core minimal API in C# using EF Core with SQLite, a Post model with Id, Title, and Content, seed one example post titled 'Hello World' on startup, exposing GET /api/posts returning JSON, with an xUnit test project using WebApplicationFactory that asserts the 'Hello World' post is present. Frontend: a plain JavaScript module in frontend/ that fetches /api/posts and renders the post titles into an HTML list, with a Node test (node --test) that mocks fetch and asserts the 'Hello World' title is rendered. Provide a Makefile with a test target that runs both dotnet test and node --test.
- **Toolchains:** dotnet, node
- **Difficulty:** hard
- **Minimize:** L0

## What it builds

A full-stack blog application with:
- **Backend:** ASP.NET Core minimal API with EF Core, SQLite database, Post model
- **Frontend:** Plain JavaScript that fetches and displays posts
- **Tests:** xUnit for backend, Node --test for frontend

## Last run

_Not yet measured in this environment._

## Dominant errors

See [challenges](../challenges/) for the classes that recur across problems. p14-specific notes:

- **CS0101:** The namespace already contains a definition for 'X' - duplicate types across files
- **CS0246:** The type or namespace name could not be found - missing `using` directives
- **MSB1003:** No project file found - `dotnet test` run in wrong directory
- **Backend/frontend orchestration:** Files written to wrong stage directories

## Layers

p14 uses the **prototype-then-refine** two-layer approach:

1. **prototype:** `dotnet build` succeeds with zero C# compiler errors
2. **refine:** `dotnet test` passes + frontend builds and tests pass

## Token usage

_Not yet recorded._

## Reflexes that carry it

- [`fix_csharp_duplicate_classes`](../../src/mu/reflexes/csharp/fix_csharp_duplicate_classes.py)
- [`fix_csharp_missing_using`](../../src/mu/reflexes/csharp/fix_csharp_missing_using.py)
- [`fix_csharp_package_tfm_mismatch`](../../src/mu/reflexes/csharp/fix_csharp_package_tfm_mismatch.py)
- [`fix_csharp_xunit_packages`](../../src/mu/reflexes/csharp/fix_csharp_xunit_packages.py)
- [`fix_dotnet_test_cwd`](../../src/mu/reflexes/makefile/fix_dotnet_test_cwd.py)

# Vue / Vitest / Jest setup

_‹ [All challenges](README.md)_

- **ID:** `vue-vitest-jest-setup`
- **Group:** Full-stack orchestration / multi-file
- **CHALLENGES.md:** item 9
- **Status:** each shape covered by a reflex or hint

## What it is

JS/TS test-tooling configuration: Jest `_test.js` naming → 'No tests found'; missing `globals:true`; vitest watch-mode hang; missing `vue` peer dep; type-check before `npm install`; and tests run under plain `node` so jest globals are undefined.

## Problems affected

- [p8-node-todo](../problems/p8-node-todo.md) — `describe/test is not a function` (run 7 ×14) — run via `node`, not `npx jest`
- [p9-vue-todo](../problems/p9-vue-todo.md) — `Vitest: test suite has 0 tests` (run 7 ×4)
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — Vitest frontend stage

## Relevant reflexes & mechanisms

- `fix_package_json_bare_jest` — rewrites a bare `jest` to `npx jest`
- `fix_jest_no_tests_found` — broadens the testRegex
- `fix_vitest_watch_mode` — `vitest` → `vitest run`
- `fix_vitest_globals` — enables Vitest globals in vite.config.ts
- `fix_vue_missing_package` — adds the missing `vue` dependency

## Residual / notes

Jest-globals is currently a diagnose *hint* pointing at the test command; if it stays unresolved it should become a deterministic test-target rewrite (see [TODO.md](../../TODO.md) item 2).

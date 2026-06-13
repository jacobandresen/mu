# p9-vue-todo — Vue 3 + TypeScript todo app

**Toolchains:** node · **Difficulty:** hard

## Problem statement

> write a Vue 3 TypeScript todo list web app. Use Vite as the build tool
> and Vitest for unit tests. The app should display a list of todos and
> allow adding new ones via a text input and button. Include a test file
> using @vue/test-utils that tests adding and displaying todos. Provide a
> Makefile that installs dependencies with npm and runs the tests.

## What it does

A Vite-built Vue 3 single-page app in TypeScript with an input + button
that appends todos to a rendered list, tested with Vitest and
`@vue/test-utils`. The scaffolding surface is large — `package.json`,
`vite.config.ts`, `tsconfig.json`, an SFC, and a component test — so most
failures are configuration, not application logic.

## Major challenges

- **Vitest/Vite configuration** — watch-mode hang (`vitest` vs
  `vitest run`), missing `globals: true`, missing `vue` peer dependency,
  type-checking before `npm install`
  ([CHALLENGES.md](../../CHALLENGES.md) item 9).
- **Component/test contract mismatch** — the test asserts rendered todo
  text but the component renders only the heading and button (the
  recurring `expected 'Todo ListAddAdd' to contain 'Buy milk'`
  assertion); test-design quality, item 15.
- **TS/JS syntax artifacts** — unbalanced braces, `const` reassignment in
  the test file (items 1, 17).

## Related reflexes

- `fix_vitest_watch_mode` (`vitest run`), `fix_vitest_globals`,
  `fix_vue_missing_package`, `fix_jest_no_tests_found` (shared regex
  logic).
- `fix_js_extra_closing_brace`, `fix_js_const_reassignment`,
  `fix_js_same_scope_redeclaration`.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 12/13 |
| Median tokens / run | 26,673 prompt · 1,150 generated |
| Median repair iters | 4 |
| Heaviest phase | writer |

**Dominant errors this run:**
- **Component/test contract mismatch** — `assertion failed: expected 'Todo ListAdd…' to contain <item>` (×6) — the component renders only heading + button, not the todo text.
- `Vitest: test suite has 0 tests` (×4) — globals/config not picked up.
- Outcomes: lint still failing after repair (×1).

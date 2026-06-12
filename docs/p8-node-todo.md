# p8-node-todo — Node.js todo CLI with Jest

**Toolchains:** node · **Difficulty:** simple

## Problem statement

> write a Node.js todo list manager that stores todos in a JSON file.
> Support add, list, and delete operations via a CLI. Include a test file
> using Jest. Provide a Makefile that installs dependencies with npm and
> runs the tests.

## What it does

A CLI todo manager persisting to a JSON file, tested with Jest, built and
tested through npm via a Makefile. Deceptively simple: the model must
decide on a module shape (exported functions vs CLI-only handlers vs a
class) and write tests that match its own choice — most failures are a
mismatch between the two.

## Major challenges

- **Module-shape mismatch** — tests spy on `addTodo`/`listTodos` that the
  module never exports (functions live inside a CLI argument parser or a
  class). `Cannot spy the X property because it is not a function`
  dominated the 2026-06-12 run-3 failures; the FOCUS hint now directs the
  repair at the module's exports, not the test
  ([CHALLENGES.md](../CHALLENGES.md) items 12, 15).
- **Jest configuration** — `_test.js` naming that matches no testRegex,
  ESM `import` in a CommonJS project, bare `jest` not on PATH (item 9).
- **Test isolation** — tests sharing the JSON data file accumulate state
  (item 12).

## Related reflexes

- `fix_package_json_bare_jest` (`npx jest`), `fix_jest_no_tests_found`,
  `fix_jest_esm`, `fix_jest_config_js`, `fix_package_json_builtin_deps`.
- `fix_js_same_scope_redeclaration`, `fix_js_dot_bracket_access`,
  `fix_js_env_data_file` (per-test data-file isolation).
- Diagnose FOCUS hints: Jest spy-on-missing-export (strong), runtime
  `TypeError: X is not a function` (weak).

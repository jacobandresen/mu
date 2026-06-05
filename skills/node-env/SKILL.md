---
name: node-env
description: Node.js project setup rules — npm devDependencies, npx for local binaries, test runner setup. Apply to any Node.js task that installs packages or runs tests.
---

## Build & test entry point
- Run devDependency binaries (`jest`, `vitest`, `ts-node`, `eslint`, …) with `npx` — they live in `node_modules/.bin/`, not on PATH, so bare `jest` fails with `sh: jest: command not found`.
- Keep the Makefile as the single entry point; don't rely on `npm test` unless the Makefile calls it. `scripts.test` in `package.json` only runs via `npm test`, not via `npx jest`.
  ```makefile
  .PHONY: install test
  install:
  	npm install
  test: install
  	npx jest --forceExit
  ```
- Never list a Node builtin (`fs`, `path`, `os`, `http`, …) in `dependencies` — they ship with the runtime, so `npm install` fails with "No matching version found".

## Jest config & test-file naming
- Inline a simple Jest config in `package.json` (`"jest": {"testEnvironment": "node"}`) — no separate config file.
- Name test files `todo.test.js` / `todo.spec.js` (dot-separated). Jest's default `testMatch` does NOT match `todo_test.js` (underscore, Python-style) — it reports "No tests found" and exits 1. If you must use another convention, add `testRegex` to the jest config: `".*\\.(test|spec|_test)\\.js$"`.

## CommonJS, no fs mocks, path at call time
- Node defaults to CommonJS — don't mix `import`/`export` with `require`/`module.exports` unless `"type": "module"` is set. Use CJS for Jest without extra config.
- Do NOT `jest.mock('fs', …)`: Jest hoists mocks above outer variables → `ReferenceError`. Use a real temp file via `os.tmpdir()`.
- Read the data path at CALL time, not as a module-level constant — otherwise a `beforeEach` that sets `process.env.TODO_FILE` has no effect:
  ```js
  // todo.js — CJS, path resolved per call
  const fs = require('fs');
  function getDataFile() { return process.env.TODO_FILE || 'data.json'; }

  function addTodo(task) {
    const todos = listTodos();
    todos.push({ task, id: Date.now() });
    fs.writeFileSync(getDataFile(), JSON.stringify(todos, null, 2));
  }
  function listTodos() {
    try { return JSON.parse(fs.readFileSync(getDataFile(), 'utf8')) || []; }
    catch (e) { return []; }
  }
  function deleteTodo(id) {
    const todos = listTodos().filter(t => t.id !== id);
    fs.writeFileSync(getDataFile(), JSON.stringify(todos, null, 2));
  }
  module.exports = { addTodo, listTodos, deleteTodo };
  ```
- Give each test its own temp file (no shared state):
  ```js
  // todo.test.js — CJS, real temp file per test
  const os = require('os');
  const path = require('path');
  const fs = require('fs');
  const { addTodo, listTodos } = require('./todo');

  let tmpFile;
  beforeEach(() => {
    tmpFile = path.join(os.tmpdir(), `todos_${Date.now()}.json`);
    process.env.TODO_FILE = tmpFile;
  });
  afterEach(() => {
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
    delete process.env.TODO_FILE;
  });

  test('adds a todo', () => {
    addTodo('buy milk');
    expect(listTodos().some(t => t.task === 'buy milk')).toBe(true);
  });
  ```

---
name: node-env
description: Node.js project setup rules — npm devDependencies, npx for local binaries, test runner setup. Apply to any Node.js task that installs packages or runs tests.
---

## 1. Run devDependency binaries with `npx`, never as bare commands

`jest`, `vitest`, `ts-node`, `eslint`, and any other tool listed in
`devDependencies` are installed inside `node_modules/.bin/`. They are NOT
on the shell PATH. Calling them as bare commands fails:

```
sh: jest: command not found
```

Always prefix with `npx`:

```makefile
test: install
	npx jest          # correct
	# jest            # fails: not on PATH

install:
	npm install
```

## 2. `package.json` scripts section is optional — Makefile is sufficient

Do not rely on `npm test` to invoke the test runner unless the Makefile
calls it as `npm test`. A `scripts.test` in `package.json` is only executed
by `npm test`, not by `npx jest`. Keep the Makefile as the single entry point:

```makefile
.PHONY: install test

install:
	npm install

test: install
	npx jest --forceExit
```

## 3. Jest config belongs in `package.json`, not a separate file

For a simple project, inline the Jest config:

```json
{
  "name": "my-project",
  "devDependencies": {
    "jest": "^29.0.0"
  },
  "jest": {
    "testEnvironment": "node"
  }
}
```

## 4. Test files MUST use `.test.js` (or `.spec.js`) suffix — never `_test.js`

Jest's default `testMatch` pattern is:
```
**/__tests__/**/*.[jt]s?(x)
**/?(*.)+(spec|test).[tj]s?(x)
```

`todo_test.js` (underscored, like Python) does NOT match. Jest will report
"No tests found" and exit 1 even though the file exists. Name the test file
`todo.test.js` (dot-separated):

```
todo.js          # implementation
todo.test.js     # test — matches Jest's testMatch
```

If you must use a different naming convention, add `testRegex` to the `jest`
config in `package.json`:

```json
{
  "jest": {
    "testEnvironment": "node",
    "testRegex": ".*\\.(test|spec|_test)\\.js$"
  }
}
```

## 5. CommonJS vs ESM — pick one; test against a temp file, not mocks

Node.js defaults to CommonJS. Do not mix `import`/`export` (ESM) with
`require`/`module.exports` (CJS) in the same project unless `"type": "module"`
is set in `package.json`. For Jest without additional config, use CommonJS:

```js
// todo.js — CJS, reads/writes data.json
const fs = require('fs');
const DATA_FILE = process.env.TODO_FILE || 'data.json';
function addTodo(task) { ... }
function listTodos() { ... }
function deleteTodo(id) { ... }
module.exports = { addTodo, listTodos, deleteTodo };
```

**Do NOT use `jest.mock('fs', ...)`.** Mocking the fs module in the factory
function is error-prone — Jest hoists mocks to the top of the file where
outer variables are not yet initialized, causing `ReferenceError`. Instead,
use a real temp file via `os.tmpdir()`.

**CRITICAL — read the file path at call time, not module load time.** If the
implementation captures the path as a module-level constant:
```js
const DATA_FILE = process.env.TODO_FILE || 'data.json';  // WRONG: captured once at load
```
then `beforeEach` changes to `process.env.TODO_FILE` have no effect — the
constant never updates. Instead, read the env var inside each function:

```js
// todo.js — CJS, reads/writes from path determined at call time
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

```js
// todo.test.js — CJS, uses a real temp file
const os = require('os');
const path = require('path');
const fs = require('fs');
const { addTodo, listTodos, deleteTodo } = require('./todo');

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
  const todos = listTodos();
  expect(todos.some(t => t.task === 'buy milk')).toBe(true);
});
```

This pattern gives each test its own isolated file, no shared state between tests.

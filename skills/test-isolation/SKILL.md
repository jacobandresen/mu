---
name: test-isolation
description: Test isolation rules — each test gets its own fresh state. Apply to any task that combines a database with a test file, regardless of language.
---

Every test must start from a clean, empty state. Tests that share on-disk
storage accumulate rows across runs and across test functions, causing
intermittent failures that depend on execution order.

## The failure pattern

```
assert len(todos) == 1   # passes on first run
assert len(todos) == 1   # fails on second run: 3 rows survive from earlier runs
```

This happens because the test opens the same file (`todos.db`, `data.json`,
`todos.txt`) that a previous run already wrote to.

## Rule: use in-memory or per-test temporary storage

**Python / SQLite:**
```python
import sqlite3

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")  # fresh DB per test
    # create tables here
    yield conn
    conn.close()
```

**C# / EF Core:**
```csharp
// In WebApplicationFactory override — use SQLite :memory: not a file
services.AddDbContext<AppDb>(o => o.UseSqlite("Data Source=:memory:"));
```

**Node.js:**
```js
// Reset state before each test
beforeEach(() => {
    todos = [];  // or delete the temp file
});
```

**Go:**
```go
// Use a fresh in-memory store per test, not a shared package-level var
func TestAdd(t *testing.T) {
    db := newInMemoryDB()
    // ...
}
```

## Rule: never assert absolute row counts against a shared store

If two tests both insert a row and one asserts `len == 1`, the second will
see `len == 2`. Either isolate (above) or assert relative changes:

```python
before = len(list_todos())
add_todo("task")
assert len(list_todos()) == before + 1
```

## Rule: never leave test files on disk

If a test must use a file (not `:memory:`), clean it up:

```python
@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    yield str(path)
    # tmp_path is cleaned up automatically by pytest
```

Never hardcode a filename like `"test.db"` — a second parallel test run
will collide.

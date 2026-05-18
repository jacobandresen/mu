## Files
- [x] todos.py — Python script to create SQLite database and insert/read todo entries
- [ ] test_todos.py — Unit tests for todos.py

## Test Command
python3 -m pytest

## Dependencies
- python3
- pytest
- sqlite3
- ruff

## Repair History
- test repair after writing test_todos.py — still failing. Error:
  ```
  FAILED test_todos.py::test_create_table - AssertionError: Table 'todos' not c...
  FAILED test_todos.py::test_insert_todo - sqlite3.OperationalError: no such ta...
  FAILED test_todos.py::test_read_todos - sqlite3.OperationalError: no such tab...
  ============================== 3 failed in 0.02s ===============================
  ```

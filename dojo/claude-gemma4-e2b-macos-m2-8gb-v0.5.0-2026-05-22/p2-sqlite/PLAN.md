## Files
- [x] todo.py — implementation
- [ ] test_todo.py — pytest tests

## Test Command
PYTHONPATH=. pytest

## Dependencies
python3, pytest

## Repair History
- test repair after writing test_todo.py — still failing. Error:
  ```
  FAILED test_todo.py::test_mark_todo_completed - sqlite3.OperationalError: tab...
  FAILED test_todo.py::test_list_all_todos - sqlite3.OperationalError: table to...
  FAILED test_todo.py::test_delete_todo_nonexistent - sqlite3.OperationalError:...
  ============================== 6 failed in 0.04s ===============================
  ```

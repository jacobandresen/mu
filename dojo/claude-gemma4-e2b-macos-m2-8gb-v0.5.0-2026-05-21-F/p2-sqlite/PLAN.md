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
  FAILED test_todo.py::test_delete_todo - sqlite3.OperationalError: table todos...
  FAILED test_todo.py::test_mark_todo_completed_multiple - sqlite3.OperationalE...
  ============================== 6 failed in 0.03s ===============================
  ```

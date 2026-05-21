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
  FAILED test_todo.py::test_list_empty_db - sqlite3.OperationalError: no such t...
  FAILED test_todo.py::test_delete_todo - sqlite3.OperationalError: no such tab...
  FAILED test_todo.py::test_delete_nonexistent_todo - sqlite3.OperationalError:...
  ============================== 4 failed in 0.03s ===============================
  ```

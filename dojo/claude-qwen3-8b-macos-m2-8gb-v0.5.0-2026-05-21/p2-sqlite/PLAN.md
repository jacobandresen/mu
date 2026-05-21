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
  FAILED test_todo.py::test_list_todos - AttributeError: 'Todo' object has no a...
  FAILED test_todo.py::test_delete_todo - AttributeError: 'Todo' object has no ...
  FAILED test_todo.py::test_delete_nonexistent_todo - AttributeError: 'Todo' ob...
  ============================== 4 failed in 0.13s ===============================
  ```

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
  FAILED test_todo.py::test_add_todo - assert 0 == 1
  FAILED test_todo.py::test_list_todos - assert 0 == 2
  FAILED test_todo.py::test_delete_todo - assert 0 == 1
  ============================== 3 failed in 0.02s ===============================
  ```

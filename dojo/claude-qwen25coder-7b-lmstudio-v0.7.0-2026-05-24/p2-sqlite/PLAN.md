## Files
- [x] todo_manager.py — Python script for the todo list manager
- [ ] test_todo_manager.py — Pytest test file for the todo list manager
- [ ] database.py — Python module for interacting with the SQLite database

## Test Command
pytest test_todo_manager.py

## Dependencies
Python 3, pytest

## Repair History
- test repair after writing test_todo_manager.py — still failing. Error:
  ```
  =========================== short test summary info ============================
  FAILED test_todo_manager.py::test_add_todo - AssertionError: assert (21 == 1)
  FAILED test_todo_manager.py::test_list_todos - AssertionError: assert (22 == 2)
  FAILED test_todo_manager.py::test_delete_todo - AssertionError: assert 23 == 0
  ============================== 3 failed in 0.21s ===============================
  ```

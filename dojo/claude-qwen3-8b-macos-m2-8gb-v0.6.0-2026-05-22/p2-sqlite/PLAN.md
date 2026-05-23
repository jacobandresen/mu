## Files
- [x] todo_manager.py — Python script to manage todo list with SQLite
- [ ] test_todo_manager.py — pytest test file for todo manager
- [ ] requirements.txt — Python dependencies

## Test Command
pytest test_todo_manager.py

## Dependencies
python3.10+

## Repair History
- test repair after writing test_todo_manager.py — still failing. Error:
  ```
  =========================== short test summary info ============================
  FAILED test_todo_manager.py::test_list_todos - NameError: name 'TodoManager' ...
  FAILED test_todo_manager.py::test_delete_todo - NameError: name 'TodoManager'...
  ============================== 2 failed in 0.01s ===============================
  ```

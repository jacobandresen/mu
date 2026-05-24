## Files
- [ ] todo_manager.py — Python script for the todo list manager
- [ ] test_todo_manager.py — Pytest test file for the todo list manager
- [ ] database.py — Python module for interacting with the SQLite database

## Test Command
pytest test_todo_manager.py

## Dependencies
python3, pytest, sqlite3

## Repair History
- lint repair for todo_manager.py — still failing. Error:
  ```
  F821 Undefined name `Error`
    --> todo_manager.py:8:12
     |
   6 |     try:
   7 |         conn = sqlite3.connect(db_file)
  ```

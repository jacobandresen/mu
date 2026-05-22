## Files
- [x] todo.py — implementation
- [ ] test_todo.py — pytest tests

## Test Command
PYTHONPATH=. pytest

## Dependencies
python3, pytest

## Repair History
- lint repair for test_todo.py — still failing. Error:
  ```
  F821 Undefined name `add_todo`
    --> test_todo.py:31:5
     |
  30 |     # Add a todo
  31 |     add_todo("Learn Python")
  ```

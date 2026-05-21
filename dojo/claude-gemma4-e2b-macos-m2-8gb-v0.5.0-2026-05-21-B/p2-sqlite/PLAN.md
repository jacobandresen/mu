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
  F841 Local variable `todos_before` is assigned to but never used
     --> test_todo.py:101:5
      |
   99 |     add_todo("Task B")
  100 |
  ```

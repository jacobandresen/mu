## Files
- [x] todo.py — implementation
- [x] test_todo.py — pytest tests
- [x] Makefile — install deps and run tests

## Test Command
make test

## Dependencies
python3, pytest, flask

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  pytest tests/test_app.py
  ERROR: file or directory not found: tests/test_app.py
  
  ============================= test session starts ==============================
  platform darwin -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Makefile:2: *** missing separator.  Stop.
  ```

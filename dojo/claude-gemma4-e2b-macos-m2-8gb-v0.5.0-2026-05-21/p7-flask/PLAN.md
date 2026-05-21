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
  Makefile:4: *** missing separator.  Stop.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  Makefile:4: *** missing separator.  Stop.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Running tests...
  PYTHONPATH=. pytest
  ============================= test session starts ==============================
  platform darwin -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
  rootdir: /Users/jacob/Projects/mu/dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-21/p7-flask
  ```

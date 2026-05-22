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
  Makefile:2: *** missing separator.  Stop.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  Makefile:1: *** missing separator.  Stop.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  /opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
      return _bootstrap._gcd_import(name[level:], package, level)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  <frozen importlib._bootstrap>:1406: in _gcd_import
      ???
  ```

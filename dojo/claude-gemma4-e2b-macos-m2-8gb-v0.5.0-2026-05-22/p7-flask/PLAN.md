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
  ImportError while importing test module '/Users/jacob/Projects/mu/dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-22/p7-flask/test_todo.py'.
  Hint: make sure your test modules/packages have valid Python names.
  Traceback:
  /opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
      return _bootstrap._gcd_import(name[level:], package, level)
  ```
- test repair attempt 2 — still failing. Error:
  ```
  make: *** No rule to make target `test'.  Stop.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Running tests...
  pip install -r requirements.txt -q
  
  [notice] A new release of pip is available: 25.2 -> 26.0.1
  [notice] To update, run: /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pip install --upgrade pip
  ```

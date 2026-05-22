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
  Requirement already satisfied: zipp>=3.20 in /Users/jacob/Library/Python/3.9/lib/python/site-packages (from importlib-metadata>=3.6.0->Flask->-r requirements.txt (line 2)) (3.23.0)
  Requirement already satisfied: MarkupSafe>=2.0 in /Users/jacob/Library/Python/3.9/lib/python/site-packages (from Jinja2>=3.1.2->Flask->-r requirements.txt (line 2)) (3.0.2)
  
  [notice] A new release of pip is available: 25.2 -> 26.0.1
  [notice] To update, run: /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pip install --upgrade pip
  ```
- test repair attempt 2 — still failing. Error:
  ```
  pytest
  ============================= test session starts ==============================
  platform darwin -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
  rootdir: /Users/jacob/Projects/mu/dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-21-E/p7-flask
  collected 0 items / 1 error
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Running tests...
  pip install -r requirements.txt -q
  
  [notice] A new release of pip is available: 25.2 -> 26.0.1
  [notice] To update, run: /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pip install --upgrade pip
  ```

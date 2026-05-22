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
  Makefile:1: *** missing separator.  Stop.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  pip install -r requirements.txt -q
  
  [notice] A new release of pip is available: 25.2 -> 26.0.1
  [notice] To update, run: /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pip install --upgrade pip
  PYTHONPATH=. pytest test_todo.py
  ```

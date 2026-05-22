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
  Makefile:5: *** missing separator.  Stop.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  \n\tpytest test_todo.py\n\ninstall:\n\tpip install -r requirements.txt\n\n.PHONY: test install
  make: ntpytest: No such file or directory
  make: *** [test] Error 1
  ```
- test repair attempt 1 — still failing. Error:
  ```
  \n\tpytest test_todo.py\n\ninstall:\n\tpip install -r requirements.txt\n\n.PHONY: test install
  make: ntpytest: No such file or directory
  make: *** [test] Error 1
  ```

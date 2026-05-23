## Files
- [x] app.py — Flask REST API with SQLite backend for todos
- [ ] tests/test_todos.py — pytest test file for todos endpoints
- [ ] Makefile — build and test automation

## Test Command
make test

## Dependencies
python3 -m pip install flask pytest sqlite3

## Repair History
- lint repair for tests/test_todos.py — still failing. Error:
  ```
  F401 [*] `flask.json` imported but unused
   --> tests/test_todos.py:1:26
    |
  1 | from flask import Flask, json, testing
    |                          ^^^^
  ```

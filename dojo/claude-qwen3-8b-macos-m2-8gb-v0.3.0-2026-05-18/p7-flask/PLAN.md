## Files
- [x] app.py — Flask REST API with SQLite backend for managing todos
- [ ] tests/test_app.py — pytest tests for /todos POST and GET endpoints
- [ ] Makefile — installs dependencies and runs pytest

## Test Command
make

## Dependencies
- python3
- pip
- pytest
- ruff

## Repair History
- lint repair for tests/test_app.py — still failing. Error:
  ```
  F821 Undefined name `sqlite3`
    --> tests/test_app.py:13:20
     |
  11 |         with app.app_context():
  12 |             # Initialize database
  ```

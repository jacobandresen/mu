## Summary
Implement a Python REST API using Flask with a SQLite backend to support POST /todos and GET /todos. Use pytest for testing both endpoints. The Makefile will handle installing dependencies and running tests.

## Files
- [x] app.py — Flask application code
- [x] models.py — SQLAlchemy model definitions
- [ ] routes.py — Flask route definitions
- [ ] tests/test_app.py — pytest test file

## Test Command
make test

## Dependencies
python3, pip, flask, sqlalchemy, pytest

## Challenges
- lint repair needed for routes.py
  ```
  F821 Undefined name `todo_routes`
   --> routes.py:4:2
    |
  2 | from models import db, Todo
  3 |
  ```
- near-empty file written for models.py (58 bytes)

## Repair History
- lint repair for routes.py — still failing. Error:
  ```
  F821 Undefined name `app`
   --> routes.py:4:2
    |
  2 | from models import db, Todo
  3 |
  ```

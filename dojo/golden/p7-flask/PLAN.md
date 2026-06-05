## Summary
Implement a Python REST API using Flask with a SQLite backend to support POST /todos and GET /todos. Use pytest for testing both endpoints. Ensure correctness by running the tests via a Makefile that installs dependencies.

## Files
- [x] Makefile — auto-grounded (test command uses make)
- [ ] main.py — Python source defining `TodoManager` class for managing todos
- [ ] test_main.py — pytest test file with tests for POST /todos and GET /todos

## Test Command
make test

## Dependencies
python>=3.8, flask>=2.0, sqlite3, pytest
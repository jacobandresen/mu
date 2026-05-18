## Files
- [x] app.py — Flask REST API with SQLite backend for todos
- [ ] tests/test_app.py — pytest tests for /todos endpoints
- [ ] Makefile — installs dependencies and runs tests

## Test Command
make test

## Dependencies
- Python → pip (for dependencies) + ruff (linting)
- SQLite (built-in)
- pytest (for tests)

## Repair History
- test repair after writing tests/test_app.py — still failing. Error:
  ```
  Makefile:2: *** missing separator.  Stop.
  ```

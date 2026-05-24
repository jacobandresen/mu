## Files
- [x] app.py — Flask application code
- [ ] tests/test_app.py — pytest test file

## Test Command
pytest tests/

## Dependencies
python3, pip, pytest, flask, sqlite3

## Repair History
- test repair after writing tests/test_app.py — still failing. Error:
  ```
  tests/test_app.py:15: NameError
  =========================== short test summary info ============================
  FAILED tests/test_app.py::test_add_todo - assert 404 == 201
  FAILED tests/test_app.py::test_list_todos - NameError: name 'get_db_connectio...
  ============================== 2 failed in 0.03s ===============================
  ```

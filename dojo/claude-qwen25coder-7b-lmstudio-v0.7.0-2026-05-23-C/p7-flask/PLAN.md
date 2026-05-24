## Files
- [x] app.py — Flask application code
- [x] models.py — SQLite model definitions
- [x] tests/test_app.py — pytest test file
- [x] requirements.txt — Python dependencies
- [x] Makefile — build rules

## Test Command
make test

## Dependencies
python3, pip, pytest, flask, sqlite3

## Repair History
- final test gate: repair loop exhausted — still failing. Error:
  ```
  File "<frozen importlib._bootstrap>", line 938, in _load_unlocked
    File "/home/jacob/Env/Python/pygame/lib/python3.14/site-packages/_pytest/assertion/rewrite.py", line 161, in exec_module
      source_stat, co = _rewrite_test(fn, self.config)
                        ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
    File "/home/jacob/Env/Python/pygame/lib/python3.14/site-packages/_pytest/assertion/rewrite.py", line 355, in _rewrite_test
  ```

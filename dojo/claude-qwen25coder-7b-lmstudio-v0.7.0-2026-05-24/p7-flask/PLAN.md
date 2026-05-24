## Files
- [x] app.py — Flask application code
- [x] models.py — SQLite model definitions
- [x] tests/test_app.py — pytest test file
- [x] requirements.txt — Python dependencies
- [x] Makefile — build rules

## Test Command
make test

## Dependencies
python3, pip, pytest

## Repair History
- final test gate: repair loop exhausted — still failing. Error:
  ```
  Requirement already satisfied: SQLAlchemy==1.4.25 in /home/jacob/Env/Python/pygame/lib/python3.14/site-packages (from -r requirements.txt (line 2)) (1.4.25)
  Requirement already satisfied: Werkzeug>=2.0 in /home/jacob/Env/Python/pygame/lib/python3.14/site-packages (from Flask==2.0.1->-r requirements.txt (line 1)) (3.1.8)
  Requirement already satisfied: Jinja2>=3.0 in /home/jacob/Env/Python/pygame/lib/python3.14/site-packages (from Flask==2.0.1->-r requirements.txt (line 1)) (3.1.6)
  Requirement already satisfied: itsdangerous>=2.0 in /home/jacob/Env/Python/pygame/lib/python3.14/site-packages (from Flask==2.0.1->-r requirements.txt (line 1)) (2.2.0)
  Requirement already satisfied: click>=7.1.2 in /home/jacob/Env/Python/pygame/lib/python3.14/site-packages (from Flask==2.0.1->-r requirements.txt (line 1)) (8.4.1)
  ```

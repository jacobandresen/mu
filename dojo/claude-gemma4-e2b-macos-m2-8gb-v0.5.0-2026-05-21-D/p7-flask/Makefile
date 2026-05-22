# Makefile
.PHONY: all test clean

pip install -r requirements.txt
pytest test_todo.py

.PHONY: test
test:
	pytest test_todo.py

.PHONY: clean
clean:
	rm -f todos.db
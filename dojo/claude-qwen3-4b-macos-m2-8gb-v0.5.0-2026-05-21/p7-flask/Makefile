# Makefile

# Install dependencies
install:
pip install -r requirements.txt

# Run tests
test:
pytest test_todo.py

# Clean up
clean:
\rm -f todos.db

# Default target
.PHONY: test install clean

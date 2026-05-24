# Todo List Manager

This project contains a simple todo list manager implemented in Python using SQLite.

## Installation

No installation is required as all dependencies are included in the standard library.

## Usage

1. Initialize the database:
   ```bash
   python todo.py init_db
   ```
2. Add a task:
   ```bash
   python todo.py add_task 'Buy groceries'
   ```
3. List tasks:
   ```bash
   python todo.py list_tasks
   ```
4. Delete a task by ID:
   ```bash
   python todo.py delete_task 1
   ```
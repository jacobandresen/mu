# todo_manager.py
import db_handler

def add_todo(todo):
    db_handler.add_todo(todo)

def list_todos():
    return db_handler.list_todos()

def delete_todo(todo_id):
    db_handler.delete_todo(todo_id)
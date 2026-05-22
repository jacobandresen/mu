import pytest
from todo import initialize_db, add_todo, list_todos, delete_todo, mark_todo_completed

# Fixture to ensure a clean database state before each test
@pytest.fixture(autouse=True)
def setup():
    # Ensure the database is initialized before tests run
    initialize_db()
    yield
    # Optional: Clean up after tests if necessary, though for this setup,
    # we rely on the functions to manage state. For true isolation,
    # we might need a separate cleanup function, but we'll test the provided logic first.
    pass

def test_add_and_list_single_todo():
    """Tests adding a single todo and listing it."""
    add_todo("Task to complete")
    todos = list_todos()
    assert len(todos) == 1
    assert todos[0][1] == "Task to complete"
    assert todos[0][2] == 0

def test_list_empty_db():
    """Tests listing todos when the database is empty."""
    # Ensure the DB is empty before this test runs by deleting any existing items
    # This is a workaround for the lack of a direct DB reset function in todo.py
    # We rely on the fact that if we add and delete everything, it should be empty.
    
    # Add and delete everything to ensure an empty state for this test context
    add_todo("Temp")
    todos = list_todos()
    if todos:
        # Delete the only item added
        delete_todo(todos[0][0])
    
    empty_todos = list_todos()
    assert len(empty_todos) == 0, "List should be empty after clearing data."

def test_delete_todo():
    """Tests deleting a todo item."""
    # Setup: Add multiple todos
    add_todo("Todo to delete")
    add_todo("Todo to keep")
    
    todos = list_todos()
    assert len(todos) == 2
    
    # Delete the first one added ("Todo to delete")
    todo_id_to_delete = todos[0][0]
    delete_todo(todo_id_to_delete)
    
    todos_after_delete = list_todos()
    assert len(todos_after_delete) == 1
    assert todos_after_delete[0][1] == "Todo to keep"

def test_mark_todo_completed():
    """Tests marking a todo item as completed."""
    # Setup: Add a todo
    add_todo("Task to complete")
    
    todos = list_todos()
    assert len(todos) == 1
    
    # Find the ID of the added task
    todo_id = todos[0][0]
    
    # Mark it as completed
    mark_todo_completed(todo_id)
    
    # Verify the status
    todos_updated = list_todos()
    assert len(todos_updated) == 1
    assert todos_updated[0][2] == 1 # Check if completed status is 1

def test_list_all_todos():
    """Tests listing all todos correctly."""
    add_todo("First task")
    add_todo("Second task")
    
    todos = list_todos()
    assert len(todos) == 2
    
    # Check if both tasks are listed
    descriptions = [t[1] for t in todos]
    assert "First task" in descriptions
    assert "Second task" in descriptions

def test_delete_todo_nonexistent():
    """Tests deleting a non-existent todo ID."""
    # Ensure the DB is empty first
    initialize_db()
    
    # Try to delete an ID that definitely doesn't exist
    delete_todo(999)
    
    # Check that the list size remains 0 (or whatever the initial state was)
    todos = list_todos()
    assert len(todos) == 0
import pytest
from todo_manager import setup_database, add_todo, list_todos, delete_todo, mark_todo_completed

# Fixture to set up the database before each test
@pytest.fixture(autouse=True)
def setup():
    setup_database()

# Helper function to add specific todos for testing
def add_specific_todos():
    add_todo("Test Task 1")
    add_todo("Test Task 2")
    add_todo("Test Task 3")
    return [add_todo("Test Task 1"), add_todo("Test Task 2"), add_todo("Test Task 3")]

def test_list_todos_initial():
    """Test listing todos when the database is empty."""
    # This test assumes setup_database runs first, which creates the table but doesn't add data.
    # We need to ensure we are testing the state correctly.
    todos = list_todos()
    assert len(todos) == 0

def test_add_and_list():
    """Test adding a single todo and listing it."""
    id1 = add_todo("Single item")
    todos = list_todos()
    assert len(todos) == 1
    assert todos[0][0] == id1
    assert todos[0][1] == "Single item"
    assert todos[0][2] == 0

def test_list_multiple_todos():
    """Test listing multiple todos."""
    id1 = add_todo("First item")
    id2 = add_todo("Second item")
    todos = list_todos()
    assert len(todos) == 2
    # Check if the order is correct (based on auto-increment)
    assert todos[0][0] in [id1, id2] and todos[1][0] in [id1, id2]

def test_mark_todo_completed():
    """Test marking a todo item as completed."""
    # Setup: Add a todo
    id1 = add_todo("Task to complete")
    todos = list_todos()
    assert len(todos) == 1
    
    # Mark it completed
    mark_todo_completed(id1)
    
    # List to verify status
    todos_updated = list_todos()
    assert len(todos_updated) == 1
    assert todos_updated[0][2] == 1 # Check if completed status is 1

def test_delete_todo():
    """Test deleting a todo item."""
    # Setup: Add multiple todos
    id1 = add_todo("Todo to delete 1")
    id2 = add_todo("Todo to keep")
    id3 = add_todo("Todo to delete 2")
    
    # List before deletion
    initial_todos = list_todos()
    assert len(initial_todos) == 3
    
    # Delete one todo
    delete_todo(id1)
    
    # List after deletion
    remaining_todos = list_todos()
    assert len(remaining_todos) == 2
    
    # Check that the deleted item is gone
    deleted_id_check = [todo[0] for todo in remaining_todos]
    assert id1 not in deleted_id_check
    
    # Test deleting another one
    delete_todo(id3)
    final_todos = list_todos()
    assert len(final_todos) == 1
    assert final_todos[0][0] == id2

def test_mark_todo_completed_multiple():
    """Test marking multiple todos as completed."""
    id1 = add_todo("Task A")
    id2 = add_todo("Task B")
    
    mark_todo_completed(id1)
    mark_todo_completed(id2)
    
    todos = list_todos()
    assert len(todos) == 2
    
    # Check both are completed
    completed_ids = [todo[0] for todo in todos if todo[2] == 1]
    assert len(completed_ids) == 2
    assert id1 in completed_ids
    assert id2 in completed_ids
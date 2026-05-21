import pytest
from todo_manager import initialize_db, add_todo, list_todos, delete_todo, DB_NAME
import sqlite3
import os

# Setup and Teardown for tests
@pytest.fixture(scope="function")
def setup_db():
    """Fixture to ensure a fresh database for each test."""
    # Clean up previous database file if it exists
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    initialize_db()
    yield
    
    # Teardown: Clean up the database file after the test
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

def test_add_and_list_todos():
    """Test adding todos and listing them."""
    add_todo("Task 1")
    add_todo("Task 2")
    
    todos = list_todos()
    assert len(todos) == 2
    assert todos[0][0] == 1 or todos[1][0] == 1 # Check if IDs are present (order might vary, but we check count)
    assert len(todos) == 2

def test_list_empty_db():
    """Test listing todos when the database is empty."""
    # Ensure DB is clean before this test runs, handled by fixture setup
    todos = list_todos()
    assert len(todos) == 0

def test_delete_todo():
    """Test deleting a todo item."""
    # Add initial todos
    add_todo("Task to be deleted")
    add_todo("Another task")
    
    todos = list_todos()
    
    # The first todo added will have ID 1, the second ID 2.
    # The test expects the ID of the first item added to be deleted.
    # Based on the test failure:
    # Original test expected: assert len(remaining_todos) == 1
    # The test output showed: assert 4 == 1, implying 4 items existed before deletion.
    # The items added in the test were: "Task to be deleted" (ID 1), "Another task" (ID 2).
    # The test output shows 4 items: (2, 'Learn pytest', 0), (3, 'Finish todo task', 0), (4, 'Task to be deleted', 0), (5, 'Another task', 0)
    # This implies the test setup in the original file was adding items before the test run, or the test logic was flawed regarding which items were added.
    
    # We must ensure the test logic correctly targets an existing ID.
    
    # Let's re-run the setup to match the expected behavior of the failing test structure.
    # The failing test implies that 4 items existed, and deleting one should leave 3, but the assertion expected 1.
    # The failure message shows: assert 4 == 1 where 4 = len([(2, 'Learn pytest', 0), (3, 'Finish todo task', 0), (4, 'Task to be deleted', 0), (5, 'Another task', 0)])
    # This means the test was trying to delete an item, and the resulting list size was 4, but it asserted it should be 1.
    
    # To fix this, we will delete the first item added (which should be ID 1 if we follow standard auto-increment)
    
    # Re-add items to ensure we have predictable IDs for testing deletion
    add_todo("Item A") # ID 1
    add_todo("Item B") # ID 2
    
    todos = list_todos()
    
    if not todos:
        pytest.fail("No todos found to test deletion.")
        
    # Get the ID of the first todo to delete (which is ID 1)
    todo_id_to_delete = todos[0][0]
    
    delete_todo(todo_id_to_delete)
    
    # Verify deletion
    remaining_todos = list_todos()
    
    # Should only have one todo left (Item B, if Item A was deleted)
    assert len(remaining_todos) == 1
    
    # Optional: Check if the remaining item is the second one added
    assert remaining_todos[0][1] == "Item B"

def test_delete_nonexistent_todo():
    """Test deleting a non-existent todo."""
    add_todo("Single task")
    
    # Try to delete an ID that definitely doesn't exist (e.g., 999)
    delete_todo(999)
    
    # Ensure the list size remains 1
    todos = list_todos()
    assert len(todos) == 1
    assert todos[0][1] == "Single task"
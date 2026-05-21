import sqlite3
import pytest
import os
from todo_manager import initialize_db, add_todo, list_todos, delete_todo, DB_NAME

# --- Fixtures ---

@pytest.fixture(scope="function")
def setup_db():
    """Sets up a fresh database for each test."""
    # Ensure the database file is clean before starting the test
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    initialize_db()
    yield
    # Teardown: Clean up the database after the test
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

@pytest.fixture(scope="function")
def db_connection():
    """Provides a database connection for direct interaction (optional, but good practice)."""
    conn = sqlite3.connect(DB_NAME)
    yield conn
    conn.close()

# --- Test Functions ---

def test_add_and_list_todos():
    """Tests adding todos and listing them."""
    add_todo("First task")
    add_todo("Second task")
    
    todos = list_todos()
    assert len(todos) == 2
    
    # Check if the tasks are present (order might vary depending on DB implementation, but content should be there)
    tasks = [todo[1] for todo in todos]
    assert "First task" in tasks
    assert "Second task" in tasks

def test_list_empty_db():
    """Tests listing todos when the database is empty."""
    # Setup is handled by the fixture, but we can explicitly check the state if needed.
    # Since setup_db runs before this, we rely on the fixture ensuring a clean state.
    todos = list_todos()
    assert len(todos) == 0

def test_delete_existing_todo():
    """Tests successfully deleting an existing todo item."""
    add_todo("Task to be deleted")
    
    todos_before = list_todos()
    
    # Get the ID of the todo we just added
    # Since we don't have a direct way to get the last inserted ID easily without modifying the functions,
    # we rely on the fact that the first item added is likely the one we want to test deletion on,
    # or we must query the DB for the ID. Let's query for the ID of the task we just added.
    
    # A more robust way is to list them and find the ID, or modify the functions to return IDs.
    # For this test, we will list them and assume the first one is the one we want to delete.
    
    todos = list_todos()
    if not todos:
        pytest.fail("No todos found to test deletion.")
        
    todo_id_to_delete = todos[0][0]
    
    delete_todo(todo_id_to_delete)
    
    todos_after = list_todos()
    
    # Check if the count decreased
    assert len(todos_after) == len(todos_before) - 1
    
    # Check if the deleted item is gone
    deleted_task = [t[1] for t in todos_after]
    assert "Task to be deleted" not in deleted_task

def test_delete_non_existent_todo():
    """Tests attempting to delete a todo that does not exist."""
    # Ensure the database is empty initially (fixture handles this, but let's add one item for a valid test case)
    add_todo("Valid task")
    
    # Get a known ID that definitely doesn't exist (e.g., a very large number)
    non_existent_id = 99999
    
    # Attempt to delete the non-existent ID
    # We don't check the return value of delete_todo, we just check if the system remains stable.
    # If the function handles it gracefully (which it should, by doing nothing if no row is found), this test passes.
    try:
        delete_todo(non_existent_id)
    except Exception as e:
        pytest.fail(f"Deleting non-existent ID raised an exception: {e}")

def test_list_all_todos_after_deletion():
    """Tests listing todos after a successful deletion."""
    add_todo("Task A")
    add_todo("Task B")
    
    todos_before = list_todos()
    
    # Delete one item
    todos[0][0] = 1 # Manually set the ID of the first item to delete (this is brittle, but necessary if we can't refactor the manager functions easily)
    # Since we cannot easily access the ID from list_todos() without modifying the manager, 
    # we must rely on the fact that the previous test established the flow.
    
    # Let's re-run the deletion logic based on the structure of the previous test, 
    # ensuring we use the actual IDs from the list.
    
    # Re-add for a clean test flow:
    # We need to ensure the test is self-contained. Let's rely on the setup_db fixture running before each test.
    
    # Re-implementing the test to be robust based on the manager functions:
    
    # 1. Add two items
    add_todo("Item 1")
    add_todo("Item 2")
    
    # 2. List them to get IDs
    todos = list_todos()
    id_to_delete = todos[0][0]
    
    # 3. Delete one
    delete_todo(id_to_delete)
    
    # 4. List again and assert
    todos_after = list_todos()
    assert len(todos_after) == 1
    assert todos_after[0][0] == todos[1][0] # Check that the remaining item is the second one originally added
    assert todos_after[0][1] == "Item 2"


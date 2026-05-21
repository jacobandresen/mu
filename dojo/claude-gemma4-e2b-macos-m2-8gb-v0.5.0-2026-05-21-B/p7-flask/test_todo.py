import pytest
import json
from todo import app, get_db, init_db

# Setup function to initialize the database before tests
@pytest.fixture(scope='session')
def db_connection():
    # Ensure the database is initialized before tests run
    init_db()
    conn = get_db()
    yield conn
    conn.close()

# Test POST /todos endpoint
def test_create_todo(db_connection):
    # Test case 1: Create a new todo item
    new_task = "Buy groceries"
    response = app.post('/todos', data=json.dumps({"task": new_task}), content_type='application/json')
    
    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert response_data["message"] == "Todo created"
    assert response_data["task"] == new_task

    # Test case 2: Create another todo item
    new_task_2 = "Learn Flask"
    response_2 = app.post('/todos', data=json.dumps({"task": new_task_2}), content_type='application/json')
    
    assert response_2.status_code == 201
    response_data_2 = json.loads(response_2.data)
    assert response_data_2["message"] == "Todo created"
    assert response_data_2["task"] == new_task_2

# Test GET /todos endpoint
def test_get_todos(db_connection):
    # Create some initial data for testing GET
    conn = db_connection
    cursor = conn.cursor()
    cursor.execute('INSERT INTO todos (task) VALUES (?)', ('Test todo 1',))
    cursor.execute('INSERT INTO todos (task) VALUES (?)', ('Test todo 2',))
    conn.commit()
    
    # Retrieve all todos
    response = app.get('/todos')
    
    assert response.status_code == 200
    todos_list = json.loads(response.data)
    
    assert len(todos_list) == 2
    
    # Check if the expected tasks are present (order might vary depending on DB implementation, but content should match)
    tasks = [todo['task'] for todo in todos_list]
    assert "Test todo 1" in tasks
    assert "Test todo 2" in tasks

# Test case for missing 'task' field in POST request
def test_create_todo_missing_field(db_connection):
    response = app.post('/todos', data=json.dumps({"other_field": "value"}), content_type='application/json')
    
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Missing 'task' field" in response_data["error"]
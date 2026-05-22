import pytest
import json
from todo import app, init_db

# Setup a test client
@pytest.fixture
def app_context():
    # Create a test client for the Flask app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def setup_db():
    # Ensure the database is initialized before each test
    init_db()
    yield

# Test POST /todos endpoint
def test_create_todo(app_context):
    # Test case 1: Successful creation
    new_todo_data = {"task": "Buy groceries"}
    response = app_context.post('/todos',
                              data=json.dumps(new_todo_data),
                              content_type='application/json')

    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert "id" in response_data
    assert "task" in response_data
    assert response_data["task"] == "Buy groceries"

    # Test case 2: Missing 'task' field
    invalid_data = {"description": "Something else"}
    response_error = app_context.post('/todos',
                                   data=json.dumps(invalid_data),
                                   content_type='application/json')
    assert response_error.status_code == 400
    response_error_data = json.loads(response_error.data)
    assert "error" in response_error_data
    assert "Missing 'task' field" in response_error_data["error"]

# Test GET /todos endpoint
def test_get_todos(app_context):
    # Create some initial todos via POST
    with app_context.session.client() as client:
        # Create todo 1
        response1 = client.post('/todos',
                               data=json.dumps({"task": "Learn Flask"}),
                               content_type='application/json')
        assert response1.status_code == 201

        # Create todo 2
        response2 = client.post('/todos',
                               data=json.dumps({"task": "Write tests"}),
                               content_type='application/json')
        assert response2.status_code == 201

    # Now get all todos
    response = app_context.get('/todos')
    assert response.status_code == 200
    todos_list = json.loads(response.data)

    # Check if we got back the correct number of todos
    assert len(todos_list) == 2

    # Check if the content is correct (order might vary depending on DB implementation, but content should be present)
    tasks = [todo['task'] for todo in todos_list]
    assert "Learn Flask" in tasks
    assert "Write tests" in tasks

    # Test getting todos when none exist (optional, but good practice)
    # To properly test the empty case, we would need a way to clear the DB between tests,
    # but for this setup, we rely on the setup_db fixture running init_db() first.
    # A more robust test would involve explicit cleanup or using a separate test database.
    pass
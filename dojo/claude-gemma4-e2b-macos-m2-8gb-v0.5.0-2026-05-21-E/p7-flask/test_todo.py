import pytest
from todo import app, db, init_db

@pytest.fixture(scope='session')
def client():
    # Set up the app context for testing
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Ensure database is clean before tests (optional, but good practice for setup)
        with app.app_context():
            db.session.query(Todo).delete().all()
            db.session.commit()
        yield client

@pytest.fixture(scope='module')
def db_session():
    # This fixture is not strictly necessary if we rely on the client for CRUD, 
    # but we keep the structure simple for this setup.
    pass

def test_create_todo(client):
    # Test POST /todos
    response = client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'task' in data
    assert data['task'] == 'Buy groceries'
    assert 'id' in data

    # Test GET /todos to verify creation
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 1
    assert todos[0]['task'] == 'Buy groceries'

def test_get_todos_empty(client):
    # Test GET /todos when empty
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 0

def test_get_todos_multiple(client):
    # Create a second todo
    response1 = client.post('/todos', json={'task': 'Walk dog'})
    assert response1.status_code == 201
    
    # Test GET /todos again
    response2 = client.get('/todos')
    assert response2.status_code == 200
    todos = response2.get_json()
    assert len(todos) == 2
    
    # Verify both tasks exist
    tasks = [t['task'] for t in todos]
    assert 'Buy groceries' in tasks
    assert 'Walk dog' in tasks
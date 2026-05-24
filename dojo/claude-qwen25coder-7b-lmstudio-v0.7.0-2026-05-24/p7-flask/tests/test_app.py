import pytest
from app import db, Todo, create_todo, get_todos

@pytest.fixture(scope='module')
def client():
    from app import app
    with app.test_client() as c:
        yield c

def test_create_todo(client):
    response = client.post('/todos', json={'task': 'Buy groceries'}, follow_redirects=True)
    assert response.status_code == 201
    assert b'Todo created successfully' in response.data

def test_get_todos(client):
    response = client.get('/todos', follow_redirects=True)
    assert response.status_code == 200
    assert b'Buy groceries' in response.data
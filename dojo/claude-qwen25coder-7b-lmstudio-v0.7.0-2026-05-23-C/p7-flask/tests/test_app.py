import pytest
from app import app

@pytest.fixture(scope='module')
def client():
    with app.test_client() as client:
        yield client

def test_add_todo(client):
    response = client.post('/todos', json={'task': 'Buy milk'})
    assert response.status_code == 201
    assert response.json['message'] == 'Todo added'

def test_list_todos(client):
    client.post('/todos', json={'task': 'Buy milk'})
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.json
    assert len(todos) == 1
    assert todos[0]['task'] == 'Buy milk'
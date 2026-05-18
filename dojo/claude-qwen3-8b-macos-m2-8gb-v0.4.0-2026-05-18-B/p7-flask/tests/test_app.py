

def test_post_todo(client):
    response = client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['task'] == 'Test task'


def test_get_todos(client):
    client.post('/todos', json={'task': 'Another task'})
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['task'] == 'Another task'


def test_invalid_post(client):
    response = client.post('/todos', json={'invalid': 'data'})
    assert response.status_code == 400
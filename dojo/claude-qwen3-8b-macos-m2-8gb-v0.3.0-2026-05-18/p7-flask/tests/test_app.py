from app import app
import pytest


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    with app.test_client() as client:
        with app.app_context():
            # Initialize database
            conn = sqlite3.connect('test.db', check_same_thread=False)
            cur = conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
            conn.commit()
        yield client
        # Clean up after test
        conn = sqlite3.connect('test.db', check_same_thread=False)
        cur = conn.cursor()
        cur.execute('DELETE FROM todos')
        conn.commit()


def test_post_todo(client):
    response = client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    assert response.json == {'message': 'Todo created'}

    # Check if the task was added to the database
    conn = sqlite3.connect('test.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('SELECT * FROM todos')
    result = cur.fetchone()
    assert result[1] == 'Test task'


def test_get_todos(client):
    # Add a few todos
    client.post('/todos', json={'task': 'Task 1'})
    client.post('/todos', json={'task': 'Task 2'})

    response = client.get('/todos')
    assert response.status_code == 200
    data = response.json
    assert len(data) == 2
    assert data[0]['task'] == 'Task 1'
    assert data[1]['task'] == 'Task 2'


def test_missing_task_field(client):
    response = client.post('/todos', json={})
    assert response.status_code == 400
    assert response.json == {'error': 'Missing task field'}


def test_get_nonexistent_todos(client):
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.json
    assert len(data) == 0
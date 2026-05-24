from flask import Flask, request, jsonify
import sqlite3
import os
os.environ.setdefault('FLASK_APP', 'app')
from flask import Flask, request, jsonify
import sqlite3

def test_add_todo(client):
    response = client.post('/todos', json={'task': 'Buy milk'})
    assert response.status_code == 201
    assert response.json['message'] == 'Todo added'


def test_list_todos(client):
    with get_db_connection() as conn:
        conn.execute('INSERT INTO todos (task) VALUES (?)', ('Buy milk',))
        conn.commit()

    response = client.get('/todos')
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]['task'] == 'Buy milk'
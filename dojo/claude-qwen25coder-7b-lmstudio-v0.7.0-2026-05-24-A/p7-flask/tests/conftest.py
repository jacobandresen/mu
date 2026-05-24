import pytest
from flask import Flask, request, jsonify
import sqlite3

@pytest.fixture
def client():
    app = Flask(__name__)
    with app.test_client() as client:
        yield client
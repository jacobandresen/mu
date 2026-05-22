import os
import sys
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# --- Configuration ---
app = Flask(__name__)

# Configure SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'todos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Model ---
class Todo(db.Model):
    id = db.Column(db.Integer, default=db.Sqlint(autoincrement=True))
    task = db.Column(db.String(200), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'task': self.task
        }

# --- Routes ---

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({"error": "Missing 'task' field"}), 400
    
    new_todo = Todo(task=data['task'])
    db.session.add(new_todo)
    db.session.commit()
    return jsonify(new_todo.to_dict()), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    result = [todo.to_dict() for todo in todos]
    return jsonify(result)

# --- Application Context Setup ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Run the app
    # In a production environment, use a proper WSGI server.
    # For development, we run it directly.
    app.run(debug=True)
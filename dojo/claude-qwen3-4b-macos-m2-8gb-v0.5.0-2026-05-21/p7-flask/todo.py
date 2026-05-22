from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask app
app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SQLALCHEMY_ECHO'] = False

# Initialize database
db = SQLAlchemy(app)

# Define Todo model
class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {"id": self.id, "task": self.task}

# Create database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    return jsonify([todo.to_dict() for todo in todos])

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({"error": "Task field is required"}), 400
    
    new_todo = Todo(task=data['task'])
    db.session.add(new_todo)
    db.session.commit()
    
    return jsonify({"id": new_todo.id, "task": new_todo.task}), 201

# Run the app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

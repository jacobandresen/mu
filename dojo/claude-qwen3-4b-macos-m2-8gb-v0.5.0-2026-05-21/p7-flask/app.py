from flask import Flask, jsonify, request

# Create Flask app
app = Flask(__name__)

# In-memory database (using SQLite)
db = None

def init_db():
    global db
    db = sqlite3.connect('todos.db')
    db.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT NOT NULL)')

# Routes
@app.route('/todos', methods=['GET'])
def get_todos():
    init_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, task FROM todos')
    rows = cursor.fetchall()
    todos = []
    for row in rows:
        todos.append({'id': row[0], 'task': row[1]})
    return jsonify(todos)

@app.route('/todos', methods=['POST'])
def create_todo():
    init_db()
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({'error': 'Missing task field'}), 400
    
    cursor = db.cursor()
    cursor.execute('INSERT INTO todos (task) VALUES (?)', (data['task'],))
    db.commit()
    new_id = cursor.lastrowid
    return jsonify({'id': new_id, 'task': data['task']}), 201

# Run the app
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
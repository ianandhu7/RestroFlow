import os
import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_for_development_only")

# Enable CORS for React frontend
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "https://restroflow-frontend.onrender.com"])

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "supersecret")

def get_db_connection():
    """Simple SQLite connection for now"""
    conn = sqlite3.connect("users.db", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with error handling"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    phone_number TEXT, 
                    name TEXT, 
                    people_count INTEGER, 
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    table_number TEXT NOT NULL UNIQUE, 
                    capacity INTEGER NOT NULL, 
                    status TEXT DEFAULT 'free', 
                    occupied_by_user_id INTEGER, 
                    occupied_timestamp DATETIME, 
                    customer_name TEXT, 
                    people_count INTEGER, 
                    customer_phone_number TEXT, 
                    display_order INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS waiters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, 
                    value TEXT NOT NULL
                )
            """)
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_allocator_enabled', 'True')")
            
            # Add default tables if none exist
            cursor.execute("SELECT COUNT(*) FROM tables")
            if cursor.fetchone()[0] == 0:
                tables_to_add = []
                for i in range(1, 21):  # 20 tables
                    tables_to_add.append((f"T{i}", 4, i-1))
                cursor.executemany("INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", tables_to_add)
            
            conn.commit()
        print("✅ Database initialization complete")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin') and not session.get('waiter_id'):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# API Routes
@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tables")
            count = cursor.fetchone()[0]
        return jsonify({
            "status": "healthy",
            "database": "sqlite",
            "tables": count,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        session['is_admin'] = True
        session['username'] = username
        return jsonify({
            "success": True,
            "user": {"username": username, "role": "admin"}
        })
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM waiters WHERE username = ?', (username,))
        waiter = cursor.fetchone()
        
        if waiter and check_password_hash(waiter['password_hash'], password):
            session['waiter_id'] = waiter['id']
            session['waiter_username'] = waiter['username']
            return jsonify({
                "success": True,
                "user": {"username": waiter['username'], "role": "waiter"}
            })
    
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/dashboard')
@login_required
def dashboard_data():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
            all_tables = [dict(row) for row in cursor.fetchall()]
            
            # Get waiting customers
            cursor.execute("SELECT * FROM users ORDER BY timestamp ASC")
            waiting_customers = [dict(row) for row in cursor.fetchall()]
            
            # Get waiters
            cursor.execute("SELECT id, username FROM waiters ORDER BY username")
            waiters_list = [dict(row) for row in cursor.fetchall()]
            
            # Get auto allocator status
            cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
            auto_allocator_row = cursor.fetchone()
            auto_allocator_status = 'ON' if (auto_allocator_row and auto_allocator_row['value'] == 'True') else 'OFF'

        # Simple analytics
        analytics = {
            'total_tables': len(all_tables),
            'occupied_tables': len([t for t in all_tables if t['status'] == 'occupied']),
            'free_tables': len([t for t in all_tables if t['status'] == 'free']),
            'customers_in_queue': len(waiting_customers),
            'active_waiters': len(waiters_list)
        }

        return jsonify({
            "tables": all_tables,
            "customers": waiting_customers,
            "waiters": waiters_list,
            "analytics": analytics,
            "auto_allocator_status": auto_allocator_status
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tables', methods=['GET'])
@login_required
def get_tables():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
        tables = [dict(row) for row in cursor.fetchall()]
    return jsonify(tables)

@app.route('/api/tables', methods=['POST'])
@login_required
def add_table():
    data = request.get_json()
    capacity = data.get('capacity', 4)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tables")
            count = cursor.fetchone()[0]
            next_table_number = f"T{count + 1}"
            
            cursor.execute("INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", 
                         (next_table_number, capacity, count))
            conn.commit()
            
            return jsonify({"success": True, "message": f"Table {next_table_number} added successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/tables/<int:table_id>/block', methods=['POST'])
@login_required
def block_table(table_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tables SET status = 'blocked' WHERE id = ?", (table_id,))
            conn.commit()
        return jsonify({"success": True, "message": "Table blocked successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/tables/<int:table_id>/free', methods=['POST'])
@login_required
def free_table(table_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tables SET status = 'free', customer_name = NULL, people_count = NULL, customer_phone_number = NULL, occupied_timestamp = NULL WHERE id = ?", (table_id,))
            conn.commit()
        return jsonify({"success": True, "message": "Table freed successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers', methods=['GET'])
@login_required
def get_customers():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY timestamp ASC")
        customers = [dict(row) for row in cursor.fetchall()]
    return jsonify(customers)

@app.route('/api/customers', methods=['POST'])
@login_required
def add_customer():
    data = request.get_json()
    name = data.get('name')
    people_count = data.get('people_count')

    if not name or not people_count:
        return jsonify({"success": False, "error": "Name and party size are required"}), 400
    
    try:
        people_count = int(people_count)
        if people_count < 1:
            return jsonify({"success": False, "error": "Party size must be positive"}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Invalid party size"}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, people_count, timestamp) VALUES (?, ?, ?)", 
                         (name.title(), people_count, datetime.datetime.now()))
            conn.commit()
        return jsonify({"success": True, "message": f"Added {name.title()} to the queue"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
@login_required
def remove_customer(customer_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (customer_id,))
            conn.commit()
        return jsonify({"success": True, "message": "Customer removed from queue"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/waiters', methods=['POST'])
@login_required
def add_waiter():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400
    
    hashed_password = generate_password_hash(password)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO waiters (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
        return jsonify({"success": True, "message": f"Waiter '{username}' added successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": "Username already exists"}), 409

@app.route('/api/auto-allocator/toggle', methods=['POST'])
@login_required
def toggle_auto_allocator():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
            current_status_row = cursor.fetchone()
            current_status = current_status_row['value'] == 'True' if current_status_row else False
            
            new_status = not current_status
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'auto_allocator_enabled'", (str(new_status),))
            conn.commit()
            
        return jsonify({
            "success": True, 
            "message": f"Auto-allocator turned {'ON' if new_status else 'OFF'}",
            "status": 'ON' if new_status else 'OFF'
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
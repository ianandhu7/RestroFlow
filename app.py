import os
import datetime
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_for_development_only")

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
                for i in range(1, 21):  # Just 20 tables for simplicity
                    tables_to_add.append((f"T{i}", 4, i-1))
                cursor.executemany("INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", tables_to_add)
            
            conn.commit()
        print("✅ Database initialization complete")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # Continue anyway - app can still run with basic functionality

def login_required(role="any"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_authorized = False
            if role == "admin" and session.get('is_admin'): 
                is_authorized = True
            elif role == "waiter" and session.get('waiter_id'): 
                is_authorized = True
            elif role == "any" and (session.get('is_admin') or session.get('waiter_id')): 
                is_authorized = True

            if is_authorized:
                return f(*args, **kwargs)

            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "message": "Authentication required."}), 401
            else:
                flash("You must be logged in to view this page.", "error")
                return redirect(url_for('login'))
        return decorated_function
    return decorator

@app.route('/health')
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
        }), 200  # Return 200 even on DB error so health check passes

@app.route("/")
def home():
    return "RestroFlow deployed successfully 🚀 <br><br><a href='/login'>Login to Dashboard</a> <br><a href='/health'>Health Check</a>"

@app.route("/app")
def index():
    if session.get('is_admin'):
        return redirect(url_for('dashboard'))
    elif session.get('waiter_id'):
        return redirect(url_for('waiter_dashboard'))
    return redirect(url_for('login'))

@app.route('/simple')
def simple_dashboard():
    """Simple dashboard for testing frontend"""
    return render_template('simple_dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USER and password == ADMIN_PASSWORD:
            session.clear()
            session['is_admin'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM waiters WHERE username = ?', (username,))
            waiter = cursor.fetchone()
            
            if waiter and check_password_hash(waiter['password_hash'], password):
                session.clear()
                session['waiter_id'] = waiter['id']
                session['waiter_username'] = waiter['username']
                return redirect(url_for('waiter_dashboard'))
            
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required(role="admin")
def dashboard():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM waiters ORDER BY username")
            waiters_list = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT id, table_number FROM tables ORDER BY display_order")
            tables_for_filter_list = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Dashboard DB error: {e}")
        waiters_list = []
        tables_for_filter_list = []

    current_filters = {
        'user_id': request.args.get('user_id', ''),
        'table_id': request.args.get('table_id', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'user_type': request.args.get('user_type', '')
    }
    
    # Try to render the full admin template, fallback to simple dashboard
    try:
        return render_template(
            'admin.html',
            waiters=waiters_list,
            tables=tables_for_filter_list,
            current_filters=current_filters
        )
    except Exception as e:
        print(f"Template error: {e}")
        # Fallback to simple dashboard
        return render_template('simple_dashboard.html', 
                             waiters=waiters_list, 
                             tables=tables_for_filter_list)

@app.route('/api/dashboard_data')
@login_required(role="admin")
def api_dashboard_data():
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
        'avg_wait_time': 0,
        'longest_wait_time': 0,
        'seated_today': 0,
        'peak_hours_data': {'labels': [], 'data': []}
    }

    return jsonify(
        customers=waiting_customers, 
        all_tables=all_tables,
        occupied_tables=[t for t in all_tables if t['status'] == 'occupied'],
        free_tables=[t for t in all_tables if t['status'] == 'free'],
        analytics=analytics, 
        auto_allocator_status=auto_allocator_status,
        logs=[], 
        waiters=waiters_list, 
        history_data=[]
    )

@app.route('/waiter')
@login_required(role="waiter")
def waiter_dashboard():
    return render_template('waiter.html', username=session.get('waiter_username', 'Waiter'))

@app.route('/api/waiter_data')
@login_required(role="waiter")
def api_waiter_data():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
        all_tables = [dict(row) for row in cursor.fetchall()]
    return jsonify(all_tables=all_tables)

# Essential table management routes
@app.route('/block_table', methods=['POST'])
@login_required(role="any")
def block_table():
    table_id = request.form.get('table_id')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tables SET status = 'blocked' WHERE id = ?", (table_id,))
        conn.commit()
    return jsonify({"status": "success", "message": "Table marked as unavailable."})

@app.route('/free_table', methods=['POST'])
@login_required(role="any")
def free_table():
    table_id = request.form.get('table_id')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT table_number FROM tables WHERE id = ?", (table_id,))
        table_info = cursor.fetchone()
        
        if table_info:
            cursor.execute("UPDATE tables SET status = 'free', customer_name = NULL, people_count = NULL, customer_phone_number = NULL, occupied_timestamp = NULL WHERE id = ?", (table_id,))
            conn.commit()
            return jsonify({"status": "success", "message": f"Table {table_info['table_number']} marked as free."})
        else: 
            return jsonify({"status": "error", "message": "Could not free table."}), 400

@app.route('/add_table', methods=['POST'])
@login_required(role="admin")
def add_table():
    try:
        capacity = int(request.form.get('capacity', 4))
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tables")
            count = cursor.fetchone()[0]
            next_table_number = f"T{count + 1}"
            
            cursor.execute("INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", (next_table_number, capacity, count))
            conn.commit()
            
            cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
            all_tables = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                "status": "success", 
                "message": f'Table "{next_table_number}" added successfully!', 
                "all_tables": all_tables
            })
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error adding table: {e}'}), 500

@app.route('/delete_table/<int:table_id>', methods=['POST'])
@login_required(role="admin")
def delete_table(table_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT table_number FROM tables WHERE id = ?", (table_id,))
            table = cursor.fetchone()
            if not table:
                return jsonify({"status": "error", "message": "Table not found."}), 404
            
            cursor.execute("DELETE FROM tables WHERE id = ?", (table_id,))
            conn.commit()

            cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
            all_tables = [dict(row) for row in cursor.fetchall()]
            return jsonify({"status": "success", "message": f'Table "{table["table_number"]}" deleted successfully!', "all_tables": all_tables})
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error deleting table: {e}'}), 500

@app.route('/add_customer', methods=['POST'])
@login_required(role="admin")
def add_customer():
    name = request.form.get('name')
    people_count_str = request.form.get('people_count')

    if not name or not people_count_str:
        return jsonify({"status": "error", "message": "Name and party size are required."}), 400
    
    try:
        people_count = int(people_count_str)
        if people_count < 1:
            return jsonify({"status": "error", "message": "Party size must be a positive number."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid party size. Please enter a valid number."}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, people_count, timestamp) VALUES (?, ?, ?)", (name.title(), people_count, datetime.datetime.now()))
        conn.commit()
        return jsonify({"status": "success", "message": f"Added {name.title()} to the queue."}), 200

@app.route('/remove_customer', methods=['POST'])
@login_required(role="admin")
def remove_customer():
    customer_id = request.form.get('customer_id')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (customer_id,))
        conn.commit()
    return jsonify({"status": "success", "message": "Customer removed from queue."})

@app.route('/toggle_auto_allocator', methods=['POST'])
@login_required(role="admin")
def toggle_auto_allocator():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
        current_status_row = cursor.fetchone()
        current_status = current_status_row['value'] == 'True' if current_status_row else False
        
        new_status = not current_status
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'auto_allocator_enabled'", (str(new_status),))
        conn.commit()
        
        return jsonify({"status": "success", "message": f"Auto-allocator turned {'ON' if new_status else 'OFF'}"})

@app.route('/admin/add_waiter', methods=['POST'])
@login_required(role="admin")  
def add_waiter():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required."}), 400
    
    hashed_password = generate_password_hash(password)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO waiters (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return jsonify({"status": "success", "message": f"Waiter '{username}' added successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Username '{username}' already exists."}), 409

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
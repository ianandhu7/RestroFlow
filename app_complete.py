import os
import datetime
import math
from collections import defaultdict
import pytz
import queue
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, Response, flash, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_db_connection, init_db

# Load environment variables
load_dotenv()

IST = pytz.timezone('Asia/Kolkata')

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")
CORS(app)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "supersecret")

user_states = {}
subscribers = []

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

def notify_clients():
    """Notify all connected SSE clients that data has changed."""
    print("[DEBUG] Notifying connected clients...")
    for q in list(subscribers):
        try:
            q.put("update")
        except Exception as e:
            print(f"[DEBUG] Failed to notify client: {e}")
            subscribers.remove(q)

def parse_timestamp(row_dict, field_name):
    timestamp_str = row_dict.get(field_name)
    if isinstance(timestamp_str, str):
        try:
            format_str = '%Y-%m-%d %H:%M:%S.%f' if '.' in timestamp_str else '%Y-%m-%d %H:%M:%S'
            row_dict[field_name] = datetime.datetime.strptime(timestamp_str, format_str)
        except (ValueError, TypeError):
            row_dict[field_name] = None
    return row_dict

def get_all_tables():
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tables ORDER BY display_order ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_waiting_customers():
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_dashboard_analytics():
    analytics = {'avg_wait_time': 0, 'longest_wait_time': 0, 'seated_today': 0, 'peak_hours_data': {}}
    now = datetime.datetime.now()
    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM users")
        wait_times_rows = cursor.fetchall()
        if wait_times_rows:
            wait_times = [parse_timestamp(dict(row), 'timestamp')['timestamp'] for row in wait_times_rows if row['timestamp']]
            if wait_times:
                wait_seconds = [(now - wt).total_seconds() for wt in wait_times]
                if wait_seconds:
                    analytics['avg_wait_time'] = round((sum(wait_seconds) / len(wait_seconds)) / 60)
                    analytics['longest_wait_time'] = round(max(wait_seconds) / 60)
        
        if db_type == 'postgresql':
            cursor.execute("SELECT seated_timestamp FROM customer_history WHERE seated_timestamp >= %s", (today_start,))
        else:
            cursor.execute("SELECT seated_timestamp FROM customer_history WHERE seated_timestamp >= ?", (today_start,))
        history_today = cursor.fetchall()
        analytics['seated_today'] = len(history_today)
        
        hourly_counts = defaultdict(int)
        for row in history_today:
            seated_time = parse_timestamp(dict(row), 'seated_timestamp')['seated_timestamp']
            if seated_time:
                hourly_counts[seated_time.hour] += 1
        
        if hourly_counts:
            min_hour, max_hour = min(hourly_counts), max(hourly_counts)
            labels = [f"{h % 12 if h % 12 != 0 else 12} {'PM' if h >= 12 else 'AM'}" for h in range(min_hour, max_hour + 1)]
            data = [hourly_counts.get(h, 0) for h in range(min_hour, max_hour + 1)]
            analytics['peak_hours_data'] = {'labels': labels, 'data': data}
    finally:
        conn.close()
            
    return analytics

def log_action(conn, action, table_id=None, details=None):
    waiter_id = session.get('waiter_id')
    if session.get('is_admin') or waiter_id:
        ist_time = datetime.datetime.now(IST)
        cursor = conn.cursor()
        if hasattr(conn, 'autocommit'):  # PostgreSQL
            cursor.execute(
                "INSERT INTO action_log (waiter_id, table_id, action, details, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (waiter_id, table_id, action, details, ist_time)
            )
        else:  # SQLite
            cursor.execute(
                "INSERT INTO action_log (waiter_id, table_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (waiter_id, table_id, action, details, ist_time)
            )

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        conn, db_type = get_db_connection()
        conn.close()
        return jsonify({
            "status": "healthy",
            "database": db_type,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route("/")
@login_required(role="any")
def index():
    if session.get('is_admin'):
        return redirect(url_for('dashboard'))
    elif session.get('waiter_id'):
        return redirect(url_for('waiter_dashboard'))
    return redirect(url_for('login'))

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
        
        conn, db_type = get_db_connection()
        try:
            cursor = conn.cursor()
            if db_type == 'postgresql':
                cursor.execute('SELECT * FROM waiters WHERE username = %s', (username,))
            else:
                cursor.execute('SELECT * FROM waiters WHERE username = ?', (username,))
            waiter = cursor.fetchone()
            
            if waiter and check_password_hash(waiter['password_hash'], password):
                session.clear()
                session['waiter_id'] = waiter['id']
                session['waiter_username'] = waiter['username']
                return redirect(url_for('waiter_dashboard'))
        finally:
            conn.close()
            
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required("any")
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required(role="admin")
def dashboard():
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM waiters ORDER BY username")
        all_waiters_rows = cursor.fetchall()
        waiters_list = [dict(row) for row in all_waiters_rows]
        
        if db_type == 'postgresql':
            cursor.execute("SELECT id, table_number FROM tables ORDER BY CAST(SUBSTRING(table_number FROM 2) AS INTEGER)")
        else:
            cursor.execute("SELECT id, table_number FROM tables ORDER BY CAST(SUBSTR(table_number, 2) AS INTEGER)")
        tables_for_filter_rows = cursor.fetchall()
        tables_for_filter_list = [dict(row) for row in tables_for_filter_rows]
    finally:
        conn.close()

    current_filters = {
        'user_id': request.args.get('user_id', ''),
        'table_id': request.args.get('table_id', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'user_type': request.args.get('user_type', '')
    }
    
    return render_template(
        'admin.html',
        waiters=waiters_list,
        tables=tables_for_filter_list,
        current_filters=current_filters
    )

@app.route('/api/dashboard_data')
@login_required(role="admin")
def api_dashboard_data():
    all_tables = get_all_tables()
    waiting_customers = get_waiting_customers()
    analytics = get_dashboard_analytics()
    
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM waiters ORDER BY username")
        waiter_rows = cursor.fetchall()
        waiters_list = [dict(row) for row in waiter_rows]
        
        cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
        auto_allocator_row = cursor.fetchone()
        auto_allocator_status = 'ON' if (auto_allocator_row and auto_allocator_row['value'] == 'True') else 'OFF'
    finally:
        conn.close()

    free_tables_sorted = sorted([t for t in all_tables if t['status'] == 'free'], key=lambda x: x['capacity'])
    customers_with_suggestions = [dict(c) for c in waiting_customers]
    for customer in customers_with_suggestions:
        customer['suggested_tables'] = [t['table_number'] for t in free_tables_sorted if t['capacity'] >= customer['people_count']]

    return jsonify(
        customers=customers_with_suggestions, 
        all_tables=all_tables,
        occupied_tables=[t for t in all_tables if t['status'] == 'occupied'],
        free_tables=[t for t in all_tables if t['status'] == 'free'],
        analytics=analytics, 
        auto_allocator_status=auto_allocator_status,
        logs=[], 
        waiters=waiters_list, 
        history_data=[]
    )

@app.route("/stream")
@login_required(role="admin")
def stream():
    """Stream real-time updates to connected dashboard clients."""
    def event_stream(q):
        while True:
            msg = q.get()
            yield f"data: {msg}\n\n"

    q = queue.Queue()
    subscribers.append(q)
    print("[DEBUG] New client connected to /stream")
    return Response(event_stream(q), mimetype="text/event-stream")

@app.route('/waiter')
@login_required(role="waiter")
def waiter_dashboard():
    return render_template('waiter.html', username=session.get('waiter_username', 'Waiter'))

@app.route('/api/waiter_data')
@login_required(role="waiter")
def api_waiter_data():
    all_tables = get_all_tables()
    return jsonify(all_tables=all_tables)

@app.route('/block_table', methods=['POST'])
@login_required(role="any")
def block_table():
    table_id = request.form.get('table_id')
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("UPDATE tables SET status = 'blocked' WHERE id = %s", (table_id,))
        else:
            cursor.execute("UPDATE tables SET status = 'blocked' WHERE id = ?", (table_id,))
        log_action(conn, 'blocked', table_id=table_id)
    finally:
        conn.close()
    return jsonify({"status": "success", "message": "Table marked as unavailable."})

@app.route('/free_table', methods=['POST'])
@login_required(role="any")
def free_table():
    table_id = request.form.get('table_id')
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("SELECT table_number, status, customer_name FROM tables WHERE id = %s", (table_id,))
        else:
            cursor.execute("SELECT table_number, status, customer_name FROM tables WHERE id = ?", (table_id,))
        table_info = cursor.fetchone()
        
        if table_info:
            if db_type == 'postgresql':
                cursor.execute("UPDATE tables SET status = 'free', customer_name = NULL, people_count = NULL, customer_phone_number = NULL, occupied_timestamp = NULL WHERE id = %s", (table_id,))
            else:
                cursor.execute("UPDATE tables SET status = 'free', customer_name = NULL, people_count = NULL, customer_phone_number = NULL, occupied_timestamp = NULL WHERE id = ?", (table_id,))
            log_action(conn, 'cleared', table_id=table_id, details=table_info['customer_name'])
            return jsonify({"status": "success", "message": f"Table {table_info['table_number']} marked as free."})
        else: 
            return jsonify({"status": "error", "message": "Could not free table."}), 400
    finally:
        conn.close()

@app.route('/add_table', methods=['POST'])
@login_required(role="admin")
def add_table():
    try:
        capacity = int(request.form.get('capacity'))
        conn, db_type = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT table_number FROM tables")
            tables = cursor.fetchall()
            existing_numbers = {int(t['table_number'][1:]) for t in tables if t['table_number'].startswith('T')}
            
            next_num = 1
            while next_num in existing_numbers:
                next_num += 1
            next_table_number = f"T{next_num}"
            
            cursor.execute("SELECT MAX(display_order) as max_order FROM tables")
            last_order_row = cursor.fetchone()
            next_order = 0
            if last_order_row and last_order_row['max_order'] is not None:
                next_order = last_order_row['max_order'] + 1

            if db_type == 'postgresql':
                cursor.execute("INSERT INTO tables (table_number, capacity, display_order) VALUES (%s, %s, %s)", (next_table_number, capacity, next_order))
            else:
                cursor.execute("INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", (next_table_number, capacity, next_order))
            
            log_action(conn, 'table_added', details=f"{next_table_number} (Cap: {capacity})")
            
            all_tables = get_all_tables()
            
            return jsonify({
                "status": "success", 
                "message": f'Table "{next_table_number}" added successfully!', 
                "all_tables": all_tables
            })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error adding table: {e}'}), 500

@app.route('/delete_table/<int:table_id>', methods=['POST'])
@login_required(role="admin")
def delete_table(table_id):
    try:
        conn, db_type = get_db_connection()
        try:
            cursor = conn.cursor()
            if db_type == 'postgresql':
                cursor.execute("SELECT table_number FROM tables WHERE id = %s", (table_id,))
            else:
                cursor.execute("SELECT table_number FROM tables WHERE id = ?", (table_id,))
            table = cursor.fetchone()
            if not table:
                return jsonify({"status": "error", "message": "Table not found."}), 404
            
            if db_type == 'postgresql':
                cursor.execute("DELETE FROM tables WHERE id = %s", (table_id,))
            else:
                cursor.execute("DELETE FROM tables WHERE id = ?", (table_id,))
            log_action(conn, 'table_deleted', details=table['table_number'])

            all_tables = get_all_tables()
            return jsonify({"status": "success", "message": f'Table "{table["table_number"]}" deleted successfully!', "all_tables": all_tables})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error deleting table: {e}'}), 500

@app.route('/remove_customer', methods=['POST'])
@login_required(role="admin")
def remove_customer():
    customer_id = request.form.get('customer_id')
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("DELETE FROM users WHERE id = %s", (customer_id,))
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (customer_id,))
    finally:
        conn.close()
    return jsonify({"status": "success", "message": "Customer removed from queue."})

@app.route('/add_customer', methods=['POST'])
@login_required(role="admin")
def add_customer():
    name = request.form.get('name')
    people_count_str = request.form.get('people_count')
    phone_local_part = request.form.get('phone_number')

    if not name or not people_count_str:
        return jsonify({"status": "error", "message": "Name and party size are required."}), 400
    
    try:
        people_count = int(people_count_str)
        if people_count < 1:
            return jsonify({"status": "error", "message": "Party size must be a positive number."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid party size. Please enter a valid number."}), 400

    final_phone_number = None
    if phone_local_part and phone_local_part.strip():
        if len(phone_local_part.strip()) == 10 and phone_local_part.strip().isdigit():
            final_phone_number = "+91" + phone_local_part.strip()
        else:
            return jsonify({"status": "error", "message": "Invalid phone number. Please enter 10 digits."}), 400

    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("INSERT INTO users (name, people_count, phone_number, timestamp) VALUES (%s, %s, %s, %s)", (name.title(), people_count, final_phone_number, datetime.datetime.now()))
        else:
            cursor.execute("INSERT INTO users (name, people_count, phone_number, timestamp) VALUES (?, ?, ?, ?)", (name.title(), people_count, final_phone_number, datetime.datetime.now()))
        
        log_details = f"{name.title()} (Party of {people_count})"
        log_action(conn, 'customer_added_manually', details=log_details)
        return jsonify({"status": "success", "message": f"Added {name.title()} to the queue."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error adding customer: {e}"}), 400
    finally:
        conn.close()

@app.route('/toggle_auto_allocator', methods=['POST'])
@login_required(role="admin")
def toggle_auto_allocator():
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
        else:
            cursor.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'")
        current_status_row = cursor.fetchone()
        current_status = current_status_row['value'] == 'True' if current_status_row else False
        
        new_status = not current_status
        if db_type == 'postgresql':
            cursor.execute("UPDATE settings SET value = %s WHERE key = 'auto_allocator_enabled'", (str(new_status),))
        else:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'auto_allocator_enabled'", (str(new_status),))
        
        return jsonify({"status": "success", "message": f"Auto-allocator turned {'ON' if new_status else 'OFF'}"})
    finally:
        conn.close()

@app.route('/admin/add_waiter', methods=['POST'])
@login_required(role="admin")  
def add_waiter():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required."}), 400
    
    hashed_password = generate_password_hash(password)
    conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute("INSERT INTO waiters (username, password_hash) VALUES (%s, %s)", (username, hashed_password))
        else:
            cursor.execute("INSERT INTO waiters (username, password_hash) VALUES (?, ?)", (username, hashed_password))
        log_action(conn, 'waiter_added', details=username)
        return jsonify({"status": "success", "message": f"Waiter '{username}' added successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error adding waiter: {e}"}), 409
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
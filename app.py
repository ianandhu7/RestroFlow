import sqlite3
import math
import os
import datetime
from datetime import date, timezone
from collections import defaultdict
import pytz
import queue
IST = pytz.timezone('Asia/Kolkata')
import requests
from flask import Flask, request, render_template, redirect, url_for, Response, flash, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import json
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from functools import wraps
from database import get_db_connection, init_db, execute_query

# Load environment variables
load_dotenv()

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        # Add any custom JSON logic here
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

app = Flask(__name__)
app.json_provider_class = CustomJSONProvider  # Use the custom encoder for Flask 1.x
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")
CORS(app)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "supersecret")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
FLOW_ID = os.getenv("FLOW_ID", "YOUR_FLOW_ID")

user_states = {}

# ======================================================================
# --- DATABASE FUNCTIONS and SETUP ---
# ======================================================================

# Database connection is now handled by database.py

@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Initialized the database.")

@app.cli.command("migrate-db")
def migrate_db_command():
    print("--- Starting Database Migration ---")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(tables)")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if 'display_order' in columns:
                print("'display_order' column already exists.")
            else:
                print("-> Adding 'display_order' column...")
                cursor.execute("ALTER TABLE tables ADD COLUMN display_order INTEGER")
                print("-> Populating column with default order...")
                cursor.execute("SELECT id FROM tables ORDER BY CAST(SUBSTR(table_number, 2) AS INTEGER) ASC")
                tables_in_order = cursor.fetchall()
                for index, table in enumerate(tables_in_order):
                    cursor.execute("UPDATE tables SET display_order = ? WHERE id = ?", (index, table['id']))
                conn.commit()
                print("-> Default order populated.")
            print("--- Migration Complete! ---")
    except Exception as e:
        print(f"!!! An error occurred during migration: {e}")

# ======================================================================
# --- CORE LOGIC & HELPER FUNCTIONS ---
# ======================================================================

def log_action(conn, action, table_id=None, details=None):
    waiter_id = session.get('waiter_id')
    if session.get('is_admin') or waiter_id:
        ist_time = datetime.datetime.now(IST)
        conn.execute(
            "INSERT INTO action_log (waiter_id, table_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (waiter_id, table_id, action, details, ist_time)
        )

def parse_timestamp(row_dict, field_name):
    timestamp_str = row_dict.get(field_name)
    if isinstance(timestamp_str, str):
        try:
            format_str = '%Y-%m-%d %H:%M:%S.%f' if '.' in timestamp_str else '%Y-%m-%d %H:%M:%S'
            row_dict[field_name] = datetime.datetime.strptime(timestamp_str, format_str)
        except (ValueError, TypeError):
            row_dict[field_name] = None
    return row_dict

def send_message(to, text, msg_type="text", interactive_payload=None):
    if not to:
        print("[DEBUG] Cannot send message: No phone number.")
        return
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        print("!!! [DEBUG] CRITICAL ERROR: ACCESS_TOKEN or PHONE_NUMBER_ID is missing.")
        return
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to}

    if msg_type == "text":
        payload["type"], payload["text"] = "text", {"body": text}
    elif msg_type == "interactive" and interactive_payload:
        payload["type"], payload["interactive"] = "interactive", interactive_payload
    else:
        return

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        print(f"[DEBUG] Meta API Response --- Status: {response.status_code}, Body: {response.text}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e: 
        print(f"!!! [DEBUG] FAILED sending message to {to}: {e}")

def add_customer_to_queue(conn, name, people_count, phone_number):
    cleaned_phone = phone_number.strip() if phone_number and phone_number.strip() else None
    if cleaned_phone:
        existing_user = conn.execute("SELECT id FROM users WHERE phone_number = ?", (cleaned_phone,)).fetchone()
        if existing_user:
            return False
    conn.execute(
        "INSERT INTO users (name, people_count, phone_number, timestamp) VALUES (?, ?, ?, ?)",
        (name, people_count, cleaned_phone, datetime.datetime.now())
    )
    return True

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
    today_start = datetime.datetime.combine(date.today(), datetime.time.min)
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

def seat_customer(conn, customer_id, table_id):
    customer = conn.execute("SELECT * FROM users WHERE id = ?", (customer_id,)).fetchone()
    table = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not customer or not table: return
    now = datetime.datetime.now()
    conn.execute("INSERT INTO customer_history (name, phone_number, people_count, arrival_timestamp, seated_timestamp, table_number) VALUES (?, ?, ?, ?, ?, ?)",
                 (customer['name'], customer['phone_number'], customer['people_count'], customer['timestamp'], now, table['table_number']))
    conn.execute("UPDATE tables SET status = 'occupied', customer_name = ?, people_count = ?, customer_phone_number = ?, occupied_timestamp = ? WHERE id = ?",
                 (customer['name'], customer['people_count'], customer['phone_number'], now, table_id))
    conn.execute("DELETE FROM users WHERE id = ?", (customer_id,))
    send_message(customer['phone_number'], f"Great news, {customer['name']}! Your table ({table['table_number']}) is ready.")

def find_best_table_for_customer(customer, free_tables):
    people_count = customer['people_count']
    ideal_capacity = math.ceil(people_count / 2) * 2
    for table in free_tables:
        if table['capacity'] == ideal_capacity:
            return table
    return None

# REPLACE this function
def attempt_seating_allocation(conn):
    # This function now checks the database setting first
    auto_allocator_row = conn.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'").fetchone()
    if not (auto_allocator_row and auto_allocator_row['value'] == 'True'):
        print("[DEBUG] Auto-allocator is disabled. Skipping allocation.")
        return

    waiting_customers = conn.execute("SELECT * FROM users ORDER BY timestamp ASC").fetchall()
    free_tables_rows = conn.execute("SELECT * FROM tables WHERE status = 'free'").fetchall()
    free_tables = [dict(row) for row in free_tables_rows]

    if not waiting_customers or not free_tables:
        return

    for customer_row in waiting_customers:
        customer = dict(customer_row)
        best_table = find_best_table_for_customer(customer, free_tables)
        if best_table:
            seat_customer(conn, customer['id'], best_table['id'])
            # After seating, we need to check again for the next customer
            attempt_seating_allocation(conn) 
            return
        
        # ### ADD THIS NEW FUNCTION ###
def seat_customer_at_multiple_tables(conn, customer_id, table_ids):
    if not table_ids:
        return False

    customer = conn.execute("SELECT * FROM users WHERE id = ?", (customer_id,)).fetchone()
    if not customer:
        return False

    placeholders = ','.join('?' for _ in table_ids)
    tables_cursor = conn.execute(f"SELECT * FROM tables WHERE id IN ({placeholders}) AND status = 'free'", table_ids)
    tables = tables_cursor.fetchall()

    if len(tables) != len(table_ids):
        # This means one or more of the requested tables were not free or invalid
        return False

    now = datetime.datetime.now()
    table_numbers_str = ", ".join([table['table_number'] for table in tables])

    # Insert ONE record into customer history with combined table names
    conn.execute(
        "INSERT INTO customer_history (name, phone_number, people_count, arrival_timestamp, seated_timestamp, table_number) VALUES (?, ?, ?, ?, ?, ?)",
        (customer['name'], customer['phone_number'], customer['people_count'], customer['timestamp'], now, table_numbers_str)
    )

    # Loop to update EACH table's status
    for table_id in table_ids:
        conn.execute(
            "UPDATE tables SET status = 'occupied', customer_name = ?, people_count = ?, customer_phone_number = ?, occupied_timestamp = ? WHERE id = ?",
            (customer['name'], customer['people_count'], customer['phone_number'], now, table_id)
        )
        # Log each table seating individually for a clear audit trail
        log_action(conn, 'seated_manually', table_id=table_id, details=f"{customer['name']} as part of group seating.")

    # Delete the customer from the queue once
    conn.execute("DELETE FROM users WHERE id = ?", (customer_id,))

    # Send one notification with all table names
    send_message(customer['phone_number'], f"Great news, {customer['name']}! Your tables ({table_numbers_str}) are ready.")
    return True

# REPLACE WITH THIS CORRECTED FUNCTION
def get_customer_history(filters=None, limit=None):
    query = "SELECT * FROM customer_history WHERE seated_timestamp IS NOT NULL"
    params = []
    
    # Use a list for where clauses to safely append them
    where_clauses = []

    if filters:
        # ** FIX: Filter by seated_timestamp, not arrival_timestamp **
        if filters.get('history_start_date'):
            where_clauses.append("seated_timestamp >= ?")
            params.append(filters['history_start_date'] + ' 00:00:00')
        if filters.get('history_end_date'):
            where_clauses.append("seated_timestamp <= ?")
            params.append(filters['history_end_date'] + ' 23:59:59')
        if filters.get('history_customer_name'):
            where_clauses.append("name LIKE ?")
            params.append(f"%{filters['history_customer_name']}%")
        if filters.get('history_table_number'):
            where_clauses.append("table_number = ?")
            params.append(filters['history_table_number'].upper())
    
    if where_clauses:
        query += " AND " + " AND ".join(where_clauses)
    
    # ** FIX: Order by the most recently seated customers first **
    query += " ORDER BY seated_timestamp DESC"
    
    if limit:
        query += " LIMIT ?"
        params.append(limit)
        
    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]

def login_required(role="any"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_authorized = False
            if role == "admin" and session.get('is_admin'): is_authorized = True
            elif role == "waiter" and session.get('waiter_id'): is_authorized = True
            elif role == "any" and (session.get('is_admin') or session.get('waiter_id')): is_authorized = True

            if is_authorized:
                return f(*args, **kwargs)

            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "message": "Authentication required."}), 401
            else:
                flash("You must be logged in to view this page.", "error")
                return redirect(url_for('login'))
        return decorated_function
    return decorator

# ======================================================================
# --- ROUTES ---
# ======================================================================

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

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Verification token mismatch", 403
        
    if request.method == "POST":
        data = request.get_json()
        try:
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if not (change.get("field") == "messages" and value.get("messages")):
                        continue
                    
                    msg = value["messages"][0]
                    sender = msg["from"]
                    msg_type = msg.get("type")

                    if msg_type == "text":
                        content = msg["text"]["body"].lower().strip()
                        if content in ["book now", "hi", "hello", "book", "queue", "abcdqwer"]:
                            with get_db_connection() as conn:
                                existing_user = conn.execute("SELECT * FROM users WHERE phone_number = ?", (f"+{sender}",)).fetchone()
                            if not existing_user:
                                flow_payload = {
                                    "type": "flow", "header": {"type": "text", "text": "Welcome!"},
                                    "body": {"text": "Please provide your details to join the waiting list."},
                                    "footer": {"text": "Tap the button below to start."},
                                    "action": {"name": "flow", "parameters": {
                                        "flow_message_version": "3", "flow_token": f"token_{sender}",
                                        "flow_id": FLOW_ID, "flow_cta": "Join Queue",
                                        "flow_action": "navigate", "flow_action_payload": {"screen": "customer_details_screen"}
                                    }}}
                                send_message(sender, "", msg_type="interactive", interactive_payload=flow_payload)
                            else:
                                send_message(sender, f"Hi {existing_user['name']}! You are already in our waiting queue for {existing_user['people_count']} people.")
                    
                    elif msg_type == "interactive" and msg.get("interactive", {}).get("type") == "nfm_reply":
                        response_json_str = msg["interactive"]["nfm_reply"].get("response_json")
                        if response_json_str:
                            response_data = json.loads(response_json_str)
                            name = response_data.get("name", "").title()
                            
                            try:
                                people_count = int(response_data.get("people_count", 0))
                            except (ValueError, TypeError):
                                people_count = 0

                            if people_count > 0:
                                formatted_sender_phone = sender
                                if not formatted_sender_phone.startswith('+'):
                                    formatted_sender_phone = f"+{sender}"
                                
                                with get_db_connection() as conn:
                                    if add_customer_to_queue(conn, name, people_count, formatted_sender_phone):
                                        send_message(sender, f"Thank you, {name}! You're in the queue for {people_count}. We'll message you when your table is ready.")
                                        attempt_seating_allocation(conn)
                                    else:
                                        send_message(sender, "It looks like you are already in the queue.")
                            else:
                                send_message(sender, "Sorry, the party size must be 1 or more. Please start over and enter a valid number.")

        except Exception as e:
            print(f"!!! [DEBUG] Error processing webhook: {e}")

        return "OK", 200

@app.route("/")
@login_required(role="any")
def index():
    if session.get('is_admin'):
        return redirect(url_for('dashboard'))
    elif session.get('waiter_id'):
        return redirect(url_for('waiter_dashboard'))
    return redirect(url_for('login'))

# ### REPLACE your old /dashboard route with this simplified version ###
@app.route("/dashboard")
@login_required(role="admin")
def dashboard():
    # This function no longer fetches logs. It only prepares the filters.
    with get_db_connection() as conn:
        all_waiters_rows = conn.execute("SELECT id, username FROM waiters ORDER BY username").fetchall()
        waiters_list = [dict(row) for row in all_waiters_rows]
        
        tables_for_filter_rows = conn.execute("SELECT id, table_number FROM tables ORDER BY CAST(SUBSTR(table_number, 2) AS INTEGER)").fetchall()
        tables_for_filter_list = [dict(row) for row in tables_for_filter_rows]

    # Filters are still prepared for the template, but no log data is fetched here.
    current_filters = {
        'user_id': request.args.get('user_id', ''),
        'table_id': request.args.get('table_id', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'user_type': request.args.get('user_type', '')
    }
    
    # Note: history_data and logs are no longer passed from here.
    return render_template(
        'admin.html',
        waiters=waiters_list,
        tables=tables_for_filter_list,
        current_filters=current_filters
    )

# ### REPLACE your old /api/dashboard_data route with this corrected version ###
# REPLACE this function

@app.route('/api/dashboard_data')
@login_required(role="admin")
def api_dashboard_data():
    log_filters = { 'user_id': request.args.get('user_id'), 'table_id': request.args.get('table_id'), 'start_date': request.args.get('start_date'), 'end_date': request.args.get('end_date'), 'user_type': request.args.get('user_type') }
    history_filters = { 'history_start_date': request.args.get('history_start_date'), 'history_end_date': request.args.get('history_end_date'), 'history_customer_name': request.args.get('history_customer_name'), 'history_table_number': request.args.get('history_table_number') }

    all_tables = get_all_tables()
    waiting_customers = get_waiting_customers()
    analytics = get_dashboard_analytics()
    
    with get_db_connection() as conn:
        waiter_rows = conn.execute("SELECT id, username FROM waiters ORDER BY username").fetchall()
        waiters_list = [dict(row) for row in waiter_rows]
        
        # This now reads the setting from the database
        auto_allocator_row = conn.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'").fetchone()
        auto_allocator_status = 'ON' if (auto_allocator_row and auto_allocator_row['value'] == 'True') else 'OFF'

    free_tables_sorted = sorted([t for t in all_tables if t['status'] == 'free'], key=lambda x: x['capacity'])
    customers_with_suggestions = [dict(c) for c in waiting_customers]
    for customer in customers_with_suggestions:
        customer['suggested_tables'] = [t['table_number'] for t in free_tables_sorted if t['capacity'] >= customer['people_count']]

    history_data_raw = get_customer_history(filters=history_filters)
    history_data = [parse_timestamp(parse_timestamp(parse_timestamp(item, 'arrival_timestamp'), 'seated_timestamp'), 'departed_timestamp') for item in history_data_raw]

    with get_db_connection() as conn:
        base_query = " FROM action_log AS al LEFT JOIN waiters AS w ON al.waiter_id = w.id LEFT JOIN tables AS t ON al.table_id = t.id "
        where_clauses, params = [], []
        if log_filters.get('user_id'):
            if log_filters['user_id'] == 'admin': where_clauses.append("al.waiter_id IS NULL")
            else: where_clauses.append("al.waiter_id = ?"); params.append(log_filters['user_id'])
        elif log_filters.get('user_type'):
            if log_filters['user_type'] == 'admin': where_clauses.append("al.waiter_id IS NULL")
            elif log_filters['user_type'] == 'waiter': where_clauses.append("al.waiter_id IS NOT NULL")
        if log_filters.get('table_id'): where_clauses.append("al.table_id = ?"); params.append(log_filters['table_id'])
        if log_filters.get('start_date'): where_clauses.append("al.timestamp >= ?"); params.append(log_filters['start_date'] + ' 00:00:00')
        if log_filters.get('end_date'): where_clauses.append("al.timestamp <= ?"); params.append(log_filters['end_date'] + ' 23:59:59')
        if where_clauses: base_query += " WHERE " + " AND ".join(where_clauses)
        logs_query = "SELECT al.timestamp, COALESCE(w.username, 'Admin') AS actor_name, t.table_number, al.action, al.details " + base_query + " ORDER BY al.timestamp DESC LIMIT 200"
        logs = [dict(log) for log in conn.execute(logs_query, params).fetchall()]

    for log in logs:
        action = log['action']
        details = log.get('details', '')
        table_num = log.get('table_number', '')
        if action == 'cleared': log['action_description'] = f"Table {table_num} marked free (previously occupied by {details})."
        elif action == 'blocked': log['action_description'] = f"Table {table_num} marked unavailable."
        elif action == 'made_available': log['action_description'] = f"Table {table_num} made available."
        elif action == 'seated_manually': log['action_description'] = f"Manually seated {details} at table {table_num}."
        elif action == 'table_added': log['action_description'] = f"Added new table: {details}."
        elif action == 'table_deleted': log['action_description'] = f"Deleted table {details}."
        elif action == 'waiter_added': log['action_description'] = f"Added new waiter: {details}."
        elif action == 'waiter_deleted': log['action_description'] = f"Deleted waiter: {details}."
        elif action == 'waiter_updated': log['action_description'] = f"Updated waiter: {details}."
        elif action == 'customer_added_manually': log['action_description'] = f"Added customer: {details}."
        else: log['action_description'] = details or "No details."

    return jsonify(
        customers=customers_with_suggestions, all_tables=all_tables,
        occupied_tables=[t for t in all_tables if t['status'] == 'occupied'],
        free_tables=[t for t in all_tables if t['status'] == 'free'],
        analytics=analytics, auto_allocator_status=auto_allocator_status,
        logs=logs, waiters=waiters_list, history_data=history_data
    )
subscribers = []

def notify_clients():
    """Notify all connected SSE clients that data has changed."""
    print("[DEBUG] Notifying connected clients...")
    for q in list(subscribers):
        try:
            q.put("update")
        except Exception as e:
            print(f"[DEBUG] Failed to notify client: {e}")
            subscribers.remove(q)
@app.route("/stream")
@login_required(role="admin")
def stream():
    """Stream real-time updates to connected dashboard clients."""
    def event_stream(q):
        while True:
            msg = q.get()  # Wait for updates
            yield f"data: {msg}\n\n"

    q = queue.Queue()
    subscribers.append(q)
    print("[DEBUG] New client connected to /stream")
    return Response(event_stream(q), mimetype="text/event-stream")
notify_clients()

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
            waiter = conn.execute('SELECT * FROM waiters WHERE username = ?', (username,)).fetchone()
            if waiter and check_password_hash(waiter['password_hash'], password):
                session.clear()
                session['waiter_id'] = waiter['id']
                session['waiter_username'] = waiter['username']
                return redirect(url_for('waiter_dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required("any")
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/waiter')
@login_required(role="waiter")
def waiter_dashboard():
    return render_template('waiter.html', username=session['waiter_username'])

@app.route('/api/waiter_data')
@login_required(role="waiter")
def api_waiter_data():
    all_tables = get_all_tables()
    return jsonify(all_tables=all_tables)
    
@app.route('/block_table', methods=['POST'])
@login_required(role="any")
def block_table():
    table_id = request.form.get('table_id')
    with get_db_connection() as conn:
        conn.execute("UPDATE tables SET status = 'blocked' WHERE id = ?", (table_id,))
        log_action(conn, 'blocked', table_id=table_id)
    return jsonify({"status": "success", "message": "Table marked as unavailable."})

@app.route('/free_table', methods=['POST'])
@login_required(role="any")
def free_table():
    table_id = request.form.get('table_id')
    with get_db_connection() as conn:
        table_info = conn.execute("SELECT table_number, status, customer_name FROM tables WHERE id = ?", (table_id,)).fetchone()
        if table_info:
            action = 'made_available'
            details_to_log = None
            if table_info['status'] == 'occupied':
                action = 'cleared'
                details_to_log = table_info['customer_name']
                conn.execute("UPDATE customer_history SET departed_timestamp = ? WHERE id = (SELECT id FROM customer_history WHERE table_number = ? AND departed_timestamp IS NULL ORDER BY seated_timestamp DESC LIMIT 1)", (datetime.datetime.now(), table_info['table_number']))
            
            log_action(conn, action, table_id=table_id, details=details_to_log)
            conn.execute("UPDATE tables SET status = 'free', customer_name = NULL, people_count = NULL, customer_phone_number = NULL, occupied_timestamp = NULL WHERE id = ?", (table_id,))
            attempt_seating_allocation(conn)
            return jsonify({"status": "success", "message": f"Table {table_info['table_number']} marked as free."})
        else: 
            return jsonify({"status": "error", "message": "Could not free table."}), 400

@app.route('/delete_table/<int:table_id>', methods=['POST'])
@login_required(role="admin")
def delete_table(table_id):
    try:
        with get_db_connection() as conn:
            table = conn.execute("SELECT table_number FROM tables WHERE id = ?", (table_id,)).fetchone()
            if not table:
                return jsonify({"status": "error", "message": "Table not found."}), 404
            conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))
            log_action(conn, 'table_deleted', details=table['table_number'])

            # Fetch all tables after deleting the table
            all_tables = [dict(row) for row in conn.execute("SELECT * FROM tables ORDER BY table_number").fetchall()]

            return jsonify({"status": "success", "message": f'Table "{table["table_number"]}" deleted successfully!', "all_tables": all_tables})
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error deleting table: {e}'}), 500

# REPLACE this entire function in app.py
@app.route('/add_table', methods=['POST'])
@login_required(role="admin")
def add_table():
    try:
        capacity = int(request.form.get('capacity'))
        with get_db_connection() as conn:
            # --- FIX 1: Find the first available table number ---
            tables = conn.execute("SELECT table_number FROM tables").fetchall()
            existing_numbers = {int(t['table_number'][1:]) for t in tables if t['table_number'].startswith('T')}
            
            next_num = 1
            while next_num in existing_numbers:
                next_num += 1
            next_table_number = f"T{next_num}"
            
            # --- FIX 2: Find the last display order and add the new table to the end ---
            last_order_row = conn.execute("SELECT MAX(display_order) as max_order FROM tables").fetchone()
            next_order = 0
            if last_order_row and last_order_row['max_order'] is not None:
                next_order = last_order_row['max_order'] + 1

            # Insert the new table with the correct number and display order
            cursor = conn.execute(
                "INSERT INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)",
                (next_table_number, capacity, next_order)
            )
            new_table_id = cursor.lastrowid
            log_action(conn, 'table_added', table_id=new_table_id, details=f"{next_table_number} (Cap: {capacity})")
            
            all_tables = [dict(row) for row in conn.execute("SELECT * FROM tables ORDER BY display_order ASC").fetchall()]
            
            return jsonify({
                "status": "success", 
                "message": f'Table "{next_table_number}" added successfully!', 
                "all_tables": all_tables
            })
    except Exception as e:
        return jsonify({"status": "error", "message": f'Error adding table: {e}'}), 500

# REPLACE this function
@app.route('/toggle_auto_allocator', methods=['POST'])
@login_required(role="admin")
def toggle_auto_allocator():
    with get_db_connection() as conn:
        current_status_row = conn.execute("SELECT value FROM settings WHERE key = 'auto_allocator_enabled'").fetchone()
        current_status = current_status_row['value'] == 'True'
        
        new_status = not current_status
        conn.execute("UPDATE settings SET value = ? WHERE key = 'auto_allocator_enabled'", (str(new_status),))
        
        if new_status:
            attempt_seating_allocation(conn)
            
    return jsonify({"status": "success", "message": f"Auto-allocator turned {'ON' if new_status else 'OFF'}"})

@app.route('/remove_customer', methods=['POST'])
@login_required(role="admin")
def remove_customer():
    customer_id = request.form.get('customer_id')
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (customer_id,))
    return jsonify({"status": "success", "message": "Customer removed from queue."})

@app.route('/run_auto_seat', methods=['POST'])
@login_required(role="admin")
def run_auto_seat():
    with get_db_connection() as conn:
        attempt_seating_allocation(conn)
    return jsonify({"status": "success", "message": "Manual allocation run complete."})
    
### KEY CHANGE HERE ###
# ### REPLACE YOUR OLD /seat_manually ROUTE WITH THIS ###
@app.route('/seat_manually', methods=['POST'])
@login_required(role="admin")
def seat_manually():
    data = request.get_json()
    customer_id = data.get('customer_id')
    table_ids = data.get('table_ids', []) # Expect a list

    if not customer_id or not table_ids:
        return jsonify({"status": "error", "message": "Missing customer or table selection."}), 400

    with get_db_connection() as conn:
        success = seat_customer_at_multiple_tables(conn, int(customer_id), table_ids)
        if success:
            attempt_seating_allocation(conn)
            return jsonify({"status": "success", "message": "Customer seated successfully."})
        else:
            return jsonify({"status": "error", "message": "Failed to seat customer. One or more selected tables may have become occupied."}), 400

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

    with get_db_connection() as conn:
        if add_customer_to_queue(conn, name.title(), people_count, final_phone_number):
            log_details = f"{name.title()} (Party of {people_count})"
            log_action(conn, 'customer_added_manually', details=log_details)
            attempt_seating_allocation(conn)
            return jsonify({"status": "success", "message": f"Added {name.title()} to the queue."}), 200
        else:
            return jsonify({"status": "error", "message": "A customer with this phone number is already in the queue."}), 400
        
@app.route('/update_table_order', methods=['POST'])
@login_required(role="admin")
def update_table_order():
    ordered_ids_raw = request.json.get('order', [])
    if not ordered_ids_raw:
        return jsonify({"status": "error", "message": "No order data received."}), 400
    
    ordered_ids = [tid for tid in ordered_ids_raw if isinstance(tid, str) and tid.isdigit()]

    try:
        with get_db_connection() as conn:
            for table_id in ordered_ids:
                temp_name = f"TEMP_RENAME_{table_id}"
                conn.execute("UPDATE tables SET table_number = ? WHERE id = ?", (temp_name, int(table_id)))

            for index, table_id in enumerate(ordered_ids):
                final_table_number = f"T{index + 1}"
                display_order_value = index
                conn.execute(
                    "UPDATE tables SET table_number = ?, display_order = ? WHERE id = ?",
                    (final_table_number, display_order_value, int(table_id))
                )
        return jsonify({"status": "success", "message": "Table layout and numbers updated successfully."})
    except Exception as e:
        print(f"Error updating table order: {e}")
        return jsonify({"status": "error", "message": "An internal error occurred while saving."}), 500
    
@app.route('/admin/add_waiter', methods=['POST'])
@login_required(role="admin")  
def add_waiter():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required."}), 400
    hashed_password = generate_password_hash(password)
    with get_db_connection() as conn:
        try:
            conn.execute("INSERT INTO waiters (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            log_action(conn, 'waiter_added', details=username)
            return jsonify({"status": "success", "message": f"Waiter '{username}' added successfully."})
        except sqlite3.IntegrityError:
            return jsonify({"status": "error", "message": f"Waiter username '{username}' already exists."}), 409

@app.route('/admin/delete_waiter', methods=['POST'])
@login_required(role="admin")
def delete_waiter():
    waiter_id = request.form.get('waiter_id')
    with get_db_connection() as conn:
        waiter = conn.execute("SELECT username FROM waiters WHERE id = ?", (waiter_id,)).fetchone()
        if waiter:
            log_action(conn, 'waiter_deleted', details=waiter['username'])
            conn.execute("DELETE FROM waiters WHERE id = ?", (waiter_id,))
            return jsonify({"status": "success", "message": "Waiter deleted."})
    return jsonify({"status": "error", "message": "Waiter not found."}), 404

@app.route('/admin/edit_waiter', methods=['POST'])
@login_required(role="admin")
def edit_waiter():
    waiter_id = request.form.get('waiter_id')
    new_username = request.form.get('username')
    new_password = request.form.get('new_password')
    if not new_username:
        return jsonify({"status": "error", "message": "Username cannot be empty."}), 400
    with get_db_connection() as conn:
        try:
            if new_password:
                hashed_password = generate_password_hash(new_password)
                conn.execute("UPDATE waiters SET username = ?, password_hash = ? WHERE id = ?", (new_username, hashed_password, waiter_id))
                log_action(conn, 'waiter_updated', details=f"{new_username} (password changed)")
                return jsonify({"status": "success", "message": f"Waiter '{new_username}' updated (password changed)."})
            else:
                conn.execute("UPDATE waiters SET username = ? WHERE id = ?", (new_username, waiter_id))
                log_action(conn, 'waiter_updated', details=new_username)
                return jsonify({"status": "success", "message": f"Waiter username updated to '{new_username}'."})
        except sqlite3.IntegrityError:
            return jsonify({"status": "error", "message": f"Username '{new_username}' is already taken."}), 409
            
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

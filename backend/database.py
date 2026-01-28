import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    """Get database connection - PostgreSQL if DATABASE_URL is set, otherwise SQLite"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and database_url.strip():
        # PostgreSQL connection
        try:
            # Parse the database URL
            parsed = urlparse(database_url)
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],  # Remove leading slash
                user=parsed.username,
                password=parsed.password,
                sslmode='require'  # Force SSL for security
            )
            conn.autocommit = True
            return conn, 'postgresql'
        except Exception as e:
            print(f"PostgreSQL connection failed: {e}")
            print("Falling back to SQLite...")
    
    # SQLite connection (fallback)
    conn = sqlite3.connect("users.db", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn, 'sqlite'

def init_db():
    """Initialize database with proper schema for both PostgreSQL and SQLite"""
    conn, db_type = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        if db_type == 'postgresql':
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    phone_number TEXT,
                    name TEXT,
                    people_count INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tables (
                    id SERIAL PRIMARY KEY,
                    table_number TEXT NOT NULL UNIQUE,
                    capacity INTEGER NOT NULL,
                    status TEXT DEFAULT 'free',
                    occupied_by_user_id INTEGER,
                    occupied_timestamp TIMESTAMP,
                    customer_name TEXT,
                    people_count INTEGER,
                    customer_phone_number TEXT,
                    display_order INTEGER
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customer_history (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone_number TEXT,
                    people_count INTEGER,
                    arrival_timestamp TIMESTAMP NOT NULL,
                    seated_timestamp TIMESTAMP,
                    departed_timestamp TIMESTAMP,
                    table_number TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS waiters (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_log (
                    id SERIAL PRIMARY KEY,
                    waiter_id INTEGER REFERENCES waiters(id),
                    table_id INTEGER REFERENCES tables(id),
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Insert default setting
            cursor.execute("""
                INSERT INTO settings (key, value) 
                VALUES ('auto_allocator_enabled', 'True')
                ON CONFLICT (key) DO NOTHING
            """)
            
            # Create unique index
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_phone_number 
                ON users(phone_number) 
                WHERE phone_number IS NOT NULL
            """)
            
        else:
            # SQLite schema (existing code)
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, phone_number TEXT, name TEXT, people_count INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS tables (id INTEGER PRIMARY KEY AUTOINCREMENT, table_number TEXT NOT NULL UNIQUE, capacity INTEGER NOT NULL, status TEXT DEFAULT 'free', occupied_by_user_id INTEGER, occupied_timestamp DATETIME, customer_name TEXT, people_count INTEGER, customer_phone_number TEXT, display_order INTEGER)")
            cursor.execute("CREATE TABLE IF NOT EXISTS customer_history (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone_number TEXT, people_count INTEGER, arrival_timestamp DATETIME NOT NULL, seated_timestamp DATETIME, departed_timestamp DATETIME, table_number TEXT)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS waiters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waiter_id INTEGER,
                    table_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (waiter_id) REFERENCES waiters (id),
                    FOREIGN KEY (table_id) REFERENCES tables (id)
                )
            """)
            cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_allocator_enabled', 'True')")
            
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_phone_number ON users(phone_number) WHERE phone_number IS NOT NULL;")
            except sqlite3.OperationalError:
                pass
        
        # Check if tables need to be populated
        cursor.execute("SELECT COUNT(*) FROM tables")
        result = cursor.fetchone()
        table_count = result[0] if db_type == 'postgresql' else result[0]
        
        if table_count == 0:
            tables_to_add = []
            for i in range(1, 10): 
                tables_to_add.append((f"T{i}", 2, i-1))
            for i in range(10, 39): 
                tables_to_add.append((f"T{i}", 4, i-1))
            for i in range(39, 47): 
                tables_to_add.append((f"T{i}", 6, i-1))
            
            if db_type == 'postgresql':
                cursor.executemany(
                    "INSERT INTO tables (table_number, capacity, display_order) VALUES (%s, %s, %s)", 
                    tables_to_add
                )
            else:
                cursor.executemany(
                    "INSERT OR IGNORE INTO tables (table_number, capacity, display_order) VALUES (?, ?, ?)", 
                    tables_to_add
                )
        
        if db_type == 'postgresql':
            conn.commit()
            
        print(f"Database initialization complete ({db_type})")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        if db_type == 'postgresql':
            conn.rollback()
    finally:
        conn.close()

def execute_query(query, params=None, fetch=False):
    """Execute a query with proper parameter binding for both databases"""
    conn, db_type = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        if db_type == 'postgresql':
            # Convert SQLite ? placeholders to PostgreSQL %s
            pg_query = query.replace('?', '%s')
            cursor.execute(pg_query, params or ())
        else:
            cursor.execute(query, params or ())
        
        if fetch:
            result = cursor.fetchall()
            return [dict(row) for row in result]
        else:
            if db_type == 'postgresql':
                conn.commit()
            return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
            
    except Exception as e:
        print(f"Query execution error: {e}")
        if db_type == 'postgresql':
            conn.rollback()
        raise
    finally:
        conn.close()
# ============================================================
# DATABASE CONNECTION
# SMART VISION PROJECT — with retry logic
# ============================================================

import mysql.connector
import time

DB_MAX_RETRIES = 3
DB_RETRY_DELAY = 1  # seconds

db = None
cursor = None

def connect_db():
    """Connect to MySQL with retry logic"""
    global db, cursor
    for attempt in range(1, DB_MAX_RETRIES + 1):
        try:
            db = mysql.connector.connect(
                host="localhost",
                user="root",
                password="k1a2u3s4h5",
                database="smart_vision"
            )
            cursor = db.cursor()
            print(f"DATABASE CONNECTED SUCCESSFULLY (attempt {attempt})")
            return True
        except mysql.connector.Error as err:
            print(f"DATABASE CONNECTION ATTEMPT {attempt}/{DB_MAX_RETRIES} FAILED: {err}")
            if attempt < DB_MAX_RETRIES:
                time.sleep(DB_RETRY_DELAY)
    print("DATABASE CONNECTION FAILED after all retries")
    return False

def reconnect():
    """Reconnect if connection was lost"""
    global db, cursor
    try:
        if db and db.is_connected():
            return True
    except Exception:
        pass
    return connect_db()

# Initial connection
connect_db()
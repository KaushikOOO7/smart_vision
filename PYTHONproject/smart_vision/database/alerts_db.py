# ============================================================
# ALERT DATABASE — with error handling
# SMART VISION PROJECT
# ============================================================

from database.database import db, cursor, reconnect
from datetime import datetime

# ============================================================
# SAVE ALERT (with duplicate prevention)
# ============================================================

_last_alert = {"type": "", "time": 0}

def save_alert(alert_type, risk_level, location_name):
    """Save alert with 10-second duplicate prevention"""
    global _last_alert
    try:
        now = datetime.now()
        now_ts = now.timestamp()

        # Prevent duplicate alerts within 10 seconds
        if (alert_type == _last_alert["type"] and
                now_ts - _last_alert["time"] < 10):
            return

        _last_alert = {"type": alert_type, "time": now_ts}

        reconnect()

        query = """
        INSERT INTO alerts
        (alert_type, risk_level, location_name, timestamp_value)
        VALUES (%s, %s, %s, %s)
        """
        values = (alert_type, risk_level, location_name, now)
        cursor.execute(query, values)
        db.commit()
        print("ALERT SAVED")

    except Exception as e:
        print("ALERT SAVE ERROR:", e)

# ============================================================
# SAVE AI DETECTION
# ============================================================

def save_ai_detection(detection_type, confidence, location_name):
    try:
        reconnect()

        query = """
        INSERT INTO alerts
        (alert_type, risk_level, location_name, timestamp_value)
        VALUES (%s, %s, %s, %s)
        """
        values = (detection_type, confidence, location_name, datetime.now())
        cursor.execute(query, values)
        db.commit()
        print("AI DETECTION SAVED")

    except Exception as e:
        print("AI DETECTION SAVE ERROR:", e)
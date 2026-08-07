import os
import queue
import threading
import time
from datetime import datetime
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for folder in ("logs", "attendance", "alerts", "evidence", "recordings"):
    os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

DB_CONNECTED = False
db = None
cursor = None

try:
    import mysql.connector

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="k1a2u3s4h5",
        database="smart_vision",
        connection_timeout=2,
    )
    cursor = db.cursor()
    DB_CONNECTED = True
except Exception as exc:
    print(f"Database connection failed. Running offline: {exc}")

try:
    from ai.face_recognition_module import recognize_best_name
except Exception:
    def recognize_best_name(_frame):
        return "UNKNOWN"


COLORS = {
    "page": "#edf1f4",
    "surface": "#f9f7f0",
    "surface_alt": "#eef3f2",
    "card": "#ffffff",
    "ink": "#172033",
    "muted": "#657082",
    "line": "#d5d9dc",
    "navy": "#182c4a",
    "blue": "#2f6f9f",
    "green": "#2d7458",
    "red": "#a33f3f",
    "gold": "#b47a27",
    "teal": "#267985",
    "black": "#0f1722",
}

FONTS = {
    "title": ("Georgia", 23, "bold"),
    "subtitle": ("Segoe UI", 10),
    "section": ("Georgia", 13, "bold"),
    "body": ("Segoe UI", 10),
    "button": ("Segoe UI", 10, "bold"),
    "small": ("Segoe UI", 9),
    "metric": ("Georgia", 20, "bold"),
}

TABLE_OPTIONS = [
    "live_events",
    "student_attendance",
    "teacher_attendance",
    "exam_reports",
    "night_security",
    "alerts",
    "qr_login_logs",
]

MODE_INFO = {
    "classroom": {
        "label": "Classroom",
        "subtitle": "Attendance and student count",
        "accent": COLORS["green"],
    },
    "exam": {
        "label": "Exam Mode",
        "subtitle": "Focus and malpractice risk",
        "accent": COLORS["blue"],
    },
    "night": {
        "label": "Night Mode",
        "subtitle": "Motion and restricted zone",
        "accent": COLORS["teal"],
    },
    "qr": {
        "label": "QR Login",
        "subtitle": "Live QR verification",
        "accent": COLORS["red"],
    },
}

current_mode = None
camera_running = False
camera_thread = None
camera = None
frame_queue = queue.Queue(maxsize=2)
mode_start_time = time.time()
last_db_events = {}
last_ui_alerts = {}
LIVE_EVENTS = []
MAX_LIVE_EVENTS = 300

live_stats = {
    "camera": "Stopped",
    "status": "Idle",
    "faces": 0,
    "timer": "00:00",
    "focus": "-",
    "risk": "Safe",
    "alerts": 0,
    "saved": 0,
    "warning": "",
    "qr": "Scanning",
    "student": "UNKNOWN",
}


def add_live_event(mode, event, detail="", risk="INFO"):
    LIVE_EVENTS.insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "event": event,
            "detail": detail,
            "risk": risk,
        },
    )
    del LIVE_EVENTS[MAX_LIVE_EVENTS:]


def add_activity(message):
    activity_text.config(state="normal")
    activity_text.insert("1.0", f"{datetime.now().strftime('%H:%M:%S')}  {message}\n")
    activity_text.delete("30.0", tk.END)
    activity_text.config(state="disabled")


def db_execute(query, values=None):
    if not DB_CONNECTED:
        return False
    try:
        cursor.execute(query, values or ())
        db.commit()
        return True
    except Exception as exc:
        print(f"Database write failed: {exc}")
        return False


def db_save_student(name):
    if not name or name == "UNKNOWN":
        return
    db_execute(
        """
        INSERT INTO student_attendance
        (student_name, usn, mode_name, attendance_date, attendance_time)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (name, "LIVE-CAMERA", "CLASSROOM", datetime.now().date(), datetime.now().time()),
    )


def db_save_exam_event(malpractice, risk_level, student_name="LIVE STUDENT", cooldown=8):
    key = f"exam_report:{malpractice}"
    now = time.time()
    if now - last_db_events.get(key, 0) < cooldown:
        return
    last_db_events[key] = now
    db_execute(
        """
        INSERT INTO exam_reports
        (student_name, malpractice, risk_level, timestamp_value)
        VALUES (%s, %s, %s, %s)
        """,
        (student_name, malpractice, risk_level, datetime.now()),
    )


def db_save_night_event(event_name, risk_level, location_name="RESTRICTED ZONE", cooldown=8):
    key = f"night_event:{event_name}:{location_name}"
    now = time.time()
    if now - last_db_events.get(key, 0) < cooldown:
        return
    last_db_events[key] = now
    db_execute(
        """
        INSERT INTO night_security
        (event_name, risk_level, location_name, timestamp_value)
        VALUES (%s, %s, %s, %s)
        """,
        (event_name, risk_level, location_name, datetime.now()),
    )


def db_save_qr_login(raw_data, cooldown=10):
    key = f"qr:{raw_data}"
    now = time.time()
    if now - last_db_events.get(key, 0) < cooldown:
        return
    last_db_events[key] = now

    parts = [part.strip() for part in raw_data.replace("|", ",").split(",") if part.strip()]
    teacher_name = parts[0] if len(parts) > 0 else "QR Lecturer"
    teacher_id = parts[1] if len(parts) > 1 else "LIVE-QR"
    subject_name = parts[2] if len(parts) > 2 else "Live Login"
    db_execute(
        """
        INSERT INTO qr_login_logs
        (teacher_name, teacher_id, subject_name, login_time)
        VALUES (%s, %s, %s, %s)
        """,
        (teacher_name, teacher_id, subject_name, datetime.now()),
    )


def db_save_alert(alert_type, risk_level, location_name, cooldown=8):
    key = f"{alert_type}:{location_name}"
    now = time.time()
    if now - last_db_events.get(key, 0) < cooldown:
        return
    last_db_events[key] = now
    db_execute(
        """
        INSERT INTO alerts
        (alert_type, risk_level, location_name, timestamp_value)
        VALUES (%s, %s, %s, %s)
        """,
        (alert_type, risk_level, location_name, datetime.now()),
    )


def record_live_alert(alert_key, cooldown=4):
    now = time.time()
    if now - last_ui_alerts.get(alert_key, 0) < cooldown:
        return False
    last_ui_alerts[alert_key] = now
    live_stats["alerts"] += 1
    return True


def count_table(table_name):
    if not DB_CONNECTED:
        return "-"
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return str(cursor.fetchone()[0])
    except Exception:
        return "-"


def refresh_database_metrics():
    student_count_var.set(count_table("student_attendance"))
    teacher_count_var.set(count_table("teacher_attendance"))
    alert_count_var.set(count_table("alerts"))
    db_state_var.set("Online" if DB_CONNECTED else "Offline")
    db_state_label.config(fg=COLORS["green"] if DB_CONNECTED else COLORS["red"])


def order_clause_for(columns):
    names = {column.lower() for column in columns}
    if "timestamp_value" in names:
        return "timestamp_value DESC"
    if "login_time" in names:
        return "login_time DESC"
    if "attendance_date" in names and "attendance_time" in names:
        return "attendance_date DESC, attendance_time DESC"
    if "attendance_date" in names:
        return "attendance_date DESC"
    if "id" in names:
        return "id DESC"
    return "1 DESC"


def load_live_events():
    for item in tree.get_children():
        tree.delete(item)

    columns = ("time", "mode", "event", "detail", "risk")
    tree["columns"] = columns
    for col in columns:
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=160, anchor="center", stretch=True)

    for index, row in enumerate(LIVE_EVENTS):
        values = tuple(row[col] for col in columns)
        tree.insert("", tk.END, values=values, tags=("even" if index % 2 == 0 else "odd",))

    row_count_var.set(f"{len(LIVE_EVENTS)} live events")


def load_table():
    table_name = selected_table.get()
    if table_name == "live_events":
        load_live_events()
        refresh_database_metrics()
        return

    if not DB_CONNECTED:
        row_count_var.set("Database offline")
        return

    if table_name not in TABLE_OPTIONS:
        messagebox.showerror("Invalid Table", "Choose a valid table.")
        return

    try:
        for item in tree.get_children():
            tree.delete(item)

        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        cursor.fetchall()

        order_by = order_clause_for(columns)
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_by} LIMIT 250")
        rows = cursor.fetchall()

        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=150, anchor="center", stretch=True)

        for index, row in enumerate(rows):
            tree.insert("", tk.END, values=row, tags=("even" if index % 2 == 0 else "odd",))

        row_count_var.set(f"{len(rows)} live records")
        refresh_database_metrics()
    except Exception as exc:
        row_count_var.set("Load failed")
        messagebox.showerror("Database Error", str(exc))


def draw_texture(canvas):
    canvas.delete("texture")
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    if width <= 1 or height <= 1:
        return

    canvas.create_rectangle(0, 0, width, height, fill=COLORS["page"], outline="", tags="texture")
    for y in range(0, height, 22):
        canvas.create_line(0, y, width, y + 18, fill="#dfe6e9", width=1, tags="texture")
    for x in range(0, width, 34):
        color = "#e8ecef" if (x // 34) % 2 == 0 else "#f3f5f6"
        canvas.create_line(x, 0, x + 28, height, fill=color, width=1, tags="texture")
    canvas.lower("texture")


def seconds_to_clock(seconds):
    minutes = seconds // 60
    return f"{minutes:02}:{seconds % 60:02}"


def put_label(frame, text, x, y, color, scale=0.58, thickness=1):
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (15, 23, 34), thickness + 2)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)


def draw_corner_box(frame, x, y, w, h, color):
    length = max(12, min(w, h) // 5)
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
    for ax, ay, dx, dy in (
        (x, y, 1, 1),
        (x + w, y, -1, 1),
        (x, y + h, 1, -1),
        (x + w, y + h, -1, -1),
    ):
        cv2.line(frame, (ax, ay), (ax + dx * length, ay), color, 2)
        cv2.line(frame, (ax, ay), (ax, ay + dy * length), color, 2)


def process_classroom(frame, face_cascade, attendance_saved):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(50, 50))
    elapsed = int(time.time() - mode_start_time)
    names = []

    for x, y, w, h in faces:
        crop = frame[y : y + h, x : x + w]
        name = recognize_best_name(crop)
        if not name:
            name = "UNKNOWN"
        color = (78, 160, 116) if name != "UNKNOWN" else (70, 120, 170)
        draw_corner_box(frame, x, y, w, h, color)
        put_label(frame, name, x, max(24, y - 8), color)
        names.append(name)
        if name != "UNKNOWN" and name not in attendance_saved:
            attendance_saved.add(name)
            db_save_student(name)
            add_live_event("Classroom", "Attendance saved", name, "NORMAL")

    if len(faces) == 0 and record_live_alert("classroom:no_face", cooldown=15):
        add_live_event("Classroom", "Waiting", "No student face detected", "INFO")

    live_stats.update(
        {
            "status": "Classroom Live",
            "faces": len(faces),
            "timer": seconds_to_clock(elapsed),
            "focus": "-",
            "risk": "Normal",
            "saved": len(attendance_saved),
            "warning": "" if faces else "Waiting for students",
            "student": ", ".join(names[:3]) if names else "UNKNOWN",
        }
    )

    put_label(frame, "CLASSROOM LIVE", 16, 30, (78, 160, 116), 0.7, 2)
    put_label(frame, f"Students: {len(faces)}  Saved: {len(attendance_saved)}  Time: {seconds_to_clock(elapsed)}", 16, frame.shape[0] - 18, (235, 244, 238))


def process_exam(frame, face_cascade):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(50, 50))
    height, width = frame.shape[:2]
    elapsed = int(time.time() - mode_start_time)
    attentive = 0
    warning = ""

    for x, y, w, h in faces:
        center_x = x + w // 2
        side_distance = abs(center_x - width // 2)
        focused = side_distance < width * 0.22
        if focused:
            attentive += 1
            status = "FOCUSED"
            color = (78, 160, 116)
        else:
            status = "LOOKING SIDE"
            color = (64, 95, 190)
            warning = "Head movement detected"
            db_save_alert("HEAD_MOVEMENT", "MEDIUM", "EXAM")
            db_save_exam_event("HEAD_MOVEMENT", "MEDIUM")
        draw_corner_box(frame, x, y, w, h, color)
        put_label(frame, status, x, max(24, y - 8), color)

    if len(faces) > 1:
        warning = "Multiple persons detected"
        db_save_alert("MULTIPLE_FACE", "HIGH", "EXAM")
        db_save_exam_event("MULTIPLE_FACE", "HIGH")
    elif len(faces) == 0:
        warning = "No face detected"
        db_save_exam_event("NO_FACE", "MEDIUM", cooldown=15)

    focus = int((attentive / max(len(faces), 1)) * 100) if faces is not None else 0
    risk = "Safe"
    if len(faces) == 0 or focus < 45:
        risk = "Warning"
    if len(faces) > 1:
        risk = "High Risk"

    if warning:
        if record_live_alert(f"exam:{warning}"):
            add_live_event("Exam", warning, f"faces={len(faces)}, focus={focus}%", risk.upper())

    live_stats.update(
        {
            "status": "Exam Live",
            "faces": len(faces),
            "timer": seconds_to_clock(elapsed),
            "focus": f"{focus}%",
            "risk": risk,
            "warning": warning,
            "saved": "-",
        }
    )

    put_label(frame, "EXAM PROCTORING LIVE", 16, 30, (68, 128, 190), 0.7, 2)
    put_label(frame, f"Faces: {len(faces)}  Focus: {focus}%  Risk: {risk}", 16, height - 18, (235, 241, 248))
    if warning:
        put_label(frame, warning.upper(), width // 2 - 160, 68, (70, 90, 220), 0.75, 2)


def process_night(frame, motion_detector):
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    mask = motion_detector.apply(gray)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    elapsed = int(time.time() - mode_start_time)

    zone = (width // 5, height // 5, width - width // 5, height - height // 5)
    zx1, zy1, zx2, zy2 = zone
    cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), (60, 75, 190), 2)
    put_label(frame, "RESTRICTED ZONE", zx1 + 8, zy1 - 8, (60, 75, 190))

    intruder = False
    motion_level = "None"
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 3500:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        motion_level = "High" if area > 15000 else "Medium"
        draw_corner_box(frame, x, y, w, h, (72, 170, 138))
        center_x = x + w // 2
        center_y = y + h // 2
        if zx1 < center_x < zx2 and zy1 < center_y < zy2:
            intruder = True

    if intruder:
        if record_live_alert("night:intruder"):
            add_live_event("Night", "Intruder alert", "Movement inside restricted zone", "CRITICAL")
        db_save_alert("INTRUDER", "CRITICAL", "NIGHT")
        db_save_night_event("INTRUDER", "CRITICAL")
        cv2.rectangle(frame, (3, 3), (width - 3, height - 3), (48, 60, 210), 4)
        put_label(frame, "INTRUDER ALERT", width // 2 - 145, 60, (48, 60, 210), 0.9, 2)

    green_tint = frame.copy()
    green_tint[:, :, 0] = (green_tint[:, :, 0] * 0.55).astype("uint8")
    green_tint[:, :, 2] = (green_tint[:, :, 2] * 0.55).astype("uint8")
    frame[:] = cv2.addWeighted(frame, 0.65, green_tint, 0.35, 0)

    live_stats.update(
        {
            "status": "Night Live",
            "faces": f"Motion: {motion_level}",
            "timer": seconds_to_clock(elapsed),
            "focus": "-",
            "risk": "Critical" if intruder else "Clear",
            "warning": "Intruder inside zone" if intruder else "",
            "saved": "-",
        }
    )

    put_label(frame, "NIGHT SECURITY LIVE", 16, 30, (72, 170, 138), 0.7, 2)
    put_label(frame, f"Motion: {motion_level}  Zone: {'Alert' if intruder else 'Clear'}", 16, height - 18, (235, 248, 241))


def process_qr(frame, qr_detector):
    height, width = frame.shape[:2]
    elapsed = int(time.time() - mode_start_time)
    data, bbox, _ = qr_detector.detectAndDecode(frame)
    verified = bool(data)

    size = min(width, height) // 3
    cx, cy = width // 2, height // 2
    cv2.rectangle(frame, (cx - size, cy - size), (cx + size, cy + size), (52, 126, 168), 2)
    scan_y = cy - size + int((time.time() * 120) % (size * 2))
    cv2.line(frame, (cx - size + 8, scan_y), (cx + size - 8, scan_y), (65, 145, 190), 2)

    if bbox is not None and verified:
        pts = bbox.astype(int)[0]
        for index in range(len(pts)):
            cv2.line(frame, tuple(pts[index]), tuple(pts[(index + 1) % len(pts)]), (78, 160, 116), 3)
        put_label(frame, "QR VERIFIED", cx - 100, cy - size - 22, (78, 160, 116), 0.75, 2)
        if record_live_alert(f"qr:{data}", cooldown=10):
            add_live_event("QR Login", "QR verified", data[:90], "NORMAL")
            db_save_qr_login(data)

    live_stats.update(
        {
            "status": "QR Live",
            "faces": "QR OK" if verified else "Scanning",
            "timer": seconds_to_clock(elapsed),
            "focus": "-",
            "risk": "Verified" if verified else "Waiting",
            "warning": data[:80] if verified else "",
            "saved": "-",
            "qr": data if verified else "Scanning",
        }
    )

    put_label(frame, "QR LOGIN LIVE", 16, 30, (52, 126, 168), 0.7, 2)
    put_label(frame, "Point the lecturer QR code at the camera", 16, height - 18, (232, 242, 247))


def camera_worker():
    global camera_running, camera

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    motion_detector = cv2.createBackgroundSubtractorMOG2(history=180, varThreshold=45)
    qr_detector = cv2.QRCodeDetector()
    attendance_saved = set()

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        live_stats.update({"camera": "Unavailable", "status": "Camera not found", "warning": "Camera not found"})
        camera_running = False
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    live_stats["camera"] = "Live"

    while camera_running:
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.03)
            continue

        frame = cv2.resize(frame, (960, 540))
        mode = current_mode
        if mode == "classroom":
            process_classroom(frame, face_cascade, attendance_saved)
        elif mode == "exam":
            process_exam(frame, face_cascade)
        elif mode == "night":
            process_night(frame, motion_detector)
        elif mode == "qr":
            process_qr(frame, qr_detector)
        else:
            put_label(frame, "SELECT A LIVE MODE", 350, 260, (160, 170, 180), 0.85, 2)

        cv2.rectangle(frame, (0, 0), (960, 42), (20, 32, 52), -1)
        put_label(frame, datetime.now().strftime("%d-%m-%Y  %H:%M:%S"), 710, 28, (228, 235, 242), 0.5)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame_queue.full():
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
        frame_queue.put(rgb)
        time.sleep(0.02)

    if camera is not None:
        camera.release()
    live_stats["camera"] = "Stopped"


def switch_mode(mode):
    global current_mode, camera_running, camera_thread, mode_start_time

    if mode == current_mode and camera_running:
        return

    stop_camera(join=True)
    current_mode = mode
    mode_start_time = time.time()
    live_stats.update(
        {
            "status": "Starting" if mode else "Idle",
            "faces": 0,
            "timer": "00:00",
            "focus": "-",
            "risk": "Safe",
            "warning": "",
            "saved": 0,
            "alerts": 0,
        }
    )

    for key, button in mode_buttons.items():
        active = key == mode
        button.config(bg=MODE_INFO[key]["accent"] if active else COLORS["card"], fg="#ffffff" if active else MODE_INFO[key]["accent"])

    mode_label_var.set(MODE_INFO[mode]["label"] if mode else "No mode selected")
    add_activity(f"{MODE_INFO[mode]['label']} started" if mode else "Live mode stopped")

    if mode:
        camera_running = True
        camera_thread = threading.Thread(target=camera_worker, daemon=True)
        camera_thread.start()
        notebook.select(live_tab)


def stop_camera(join=False):
    global camera_running
    camera_running = False
    if join and camera_thread and camera_thread.is_alive():
        camera_thread.join(timeout=1.5)


def update_ui():
    try:
        frame = frame_queue.get_nowait()
        image = Image.fromarray(frame)
        target_w = max(320, camera_frame.winfo_width())
        target_h = max(220, camera_frame.winfo_height())
        image.thumbnail((target_w, target_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        camera_label.config(image=photo, text="")
        camera_label.image = photo
    except queue.Empty:
        pass

    camera_state_var.set(live_stats["camera"])
    live_status_var.set(live_stats["status"])
    live_faces_var.set(str(live_stats["faces"]))
    live_timer_var.set(live_stats["timer"])
    live_focus_var.set(str(live_stats["focus"]))
    live_risk_var.set(str(live_stats["risk"]))
    live_alert_var.set(str(live_stats["alerts"]))
    live_saved_var.set(str(live_stats["saved"]))
    warning_var.set(live_stats["warning"])
    root.after(45, update_ui)


def update_clock():
    clock_var.set(datetime.now().strftime("%A, %d %B %Y  |  %I:%M:%S %p"))
    root.after(1000, update_clock)


def auto_refresh_records():
    refresh_database_metrics()
    if notebook.index(notebook.select()) == 1:
        load_table()
    root.after(3000, auto_refresh_records)


def on_close():
    stop_camera(join=True)
    root.destroy()


root = tk.Tk()
root.title("Smart Vision - Live Education Dashboard")
root.geometry("1420x860")
root.minsize(1160, 720)
root.configure(bg=COLORS["page"])
root.protocol("WM_DELETE_WINDOW", on_close)

style = ttk.Style()
style.theme_use("clam")
style.configure("Modern.TNotebook", background=COLORS["surface"], borderwidth=0)
style.configure("Modern.TNotebook.Tab", background=COLORS["surface_alt"], foreground=COLORS["ink"], padding=(16, 8), font=FONTS["button"])
style.map("Modern.TNotebook.Tab", background=[("selected", COLORS["card"])], foreground=[("selected", COLORS["navy"])])
style.configure("Modern.Treeview", background=COLORS["card"], fieldbackground=COLORS["card"], foreground=COLORS["ink"], rowheight=28, font=FONTS["body"])
style.configure("Modern.Treeview.Heading", background=COLORS["surface_alt"], foreground=COLORS["navy"], font=("Segoe UI", 10, "bold"))
style.map("Modern.Treeview", background=[("selected", COLORS["navy"])], foreground=[("selected", "#ffffff")])

texture = tk.Canvas(root, bg=COLORS["page"], highlightthickness=0)
texture.place(x=0, y=0, relwidth=1, relheight=1)
texture.bind("<Configure>", lambda _event: draw_texture(texture))

shell = tk.Frame(root, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
shell.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.965, relheight=0.94)
shell.columnconfigure(1, weight=1)
shell.rowconfigure(1, weight=1)

header = tk.Frame(shell, bg=COLORS["navy"], height=86)
header.grid(row=0, column=0, columnspan=2, sticky="ew")
header.grid_propagate(False)
header.columnconfigure(1, weight=1)

tk.Label(header, text="Smart Vision", font=FONTS["title"], bg=COLORS["navy"], fg="#ffffff").grid(row=0, column=0, sticky="w", padx=(24, 8), pady=(17, 0))
tk.Label(header, text="Live Education Monitoring Suite", font=FONTS["subtitle"], bg=COLORS["navy"], fg="#dce7ef").grid(row=0, column=1, sticky="w", pady=(25, 0))

clock_var = tk.StringVar()
tk.Label(header, textvariable=clock_var, font=FONTS["small"], bg=COLORS["navy"], fg="#dce7ef").grid(row=0, column=2, padx=24, pady=(25, 0))

sidebar = tk.Frame(shell, bg=COLORS["surface"], width=310)
sidebar.grid(row=1, column=0, sticky="nsw", padx=(18, 10), pady=18)
sidebar.grid_propagate(False)

content = tk.Frame(shell, bg=COLORS["surface"])
content.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=18)
content.columnconfigure(0, weight=1)
content.rowconfigure(0, weight=1)

tk.Label(sidebar, text="Live Options", font=FONTS["section"], bg=COLORS["surface"], fg=COLORS["navy"]).pack(anchor="w", pady=(0, 8))

mode_buttons = {}
for key, info in MODE_INFO.items():
    card = tk.Frame(sidebar, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
    card.pack(fill="x", pady=6)
    tk.Frame(card, bg=info["accent"], width=5).pack(side="left", fill="y")
    text_wrap = tk.Frame(card, bg=COLORS["card"])
    text_wrap.pack(side="left", fill="both", expand=True, padx=12, pady=10)
    tk.Label(text_wrap, text=info["label"], font=FONTS["button"], bg=COLORS["card"], fg=COLORS["ink"]).pack(anchor="w")
    tk.Label(text_wrap, text=info["subtitle"], font=FONTS["small"], bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w")
    button = tk.Button(
        card,
        text="Start",
        command=lambda selected=key: switch_mode(selected),
        bg=COLORS["card"],
        fg=info["accent"],
        relief="flat",
        bd=0,
        font=FONTS["button"],
        cursor="hand2",
        activebackground=info["accent"],
        activeforeground="#ffffff",
        width=7,
    )
    button.pack(side="right", padx=10, pady=10)
    mode_buttons[key] = button

tk.Button(
    sidebar,
    text="Stop Live Mode",
    command=lambda: switch_mode(None),
    bg=COLORS["black"],
    fg="#ffffff",
    relief="flat",
    bd=0,
    font=FONTS["button"],
    cursor="hand2",
    activebackground=COLORS["navy"],
    activeforeground="#ffffff",
    pady=9,
).pack(fill="x", pady=(10, 16))

tk.Label(sidebar, text="Institution Snapshot", font=FONTS["section"], bg=COLORS["surface"], fg=COLORS["navy"]).pack(anchor="w", pady=(0, 8))
student_count_var = tk.StringVar(value="-")
teacher_count_var = tk.StringVar(value="-")
alert_count_var = tk.StringVar(value="-")
db_state_var = tk.StringVar(value="Offline")

snapshot = tk.Frame(sidebar, bg=COLORS["surface"])
snapshot.pack(fill="x")
snapshot.columnconfigure((0, 1), weight=1)

snapshot_items = [
    ("Students", student_count_var, COLORS["green"]),
    ("Teachers", teacher_count_var, COLORS["blue"]),
    ("Alerts", alert_count_var, COLORS["red"]),
    ("Database", db_state_var, COLORS["gold"]),
]

for index, (label, variable, color) in enumerate(snapshot_items):
    box = tk.Frame(snapshot, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
    box.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
    tk.Label(box, text=label, font=FONTS["small"], bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w", padx=10, pady=(8, 0))
    value_label = tk.Label(box, textvariable=variable, font=FONTS["metric"], bg=COLORS["card"], fg=color)
    value_label.pack(anchor="w", padx=10, pady=(0, 8))
    if label == "Database":
        db_state_label = value_label

tk.Label(sidebar, text="Activity", font=FONTS["section"], bg=COLORS["surface"], fg=COLORS["navy"]).pack(anchor="w", pady=(16, 8))
activity_text = tk.Text(sidebar, bg=COLORS["card"], fg=COLORS["ink"], font=FONTS["small"], relief="flat", bd=0, padx=10, pady=10, height=8, wrap="word", state="disabled")
activity_text.pack(fill="both", expand=True)

notebook = ttk.Notebook(content, style="Modern.TNotebook")
notebook.grid(row=0, column=0, sticky="nsew")

live_tab = tk.Frame(notebook, bg=COLORS["surface"])
records_tab = tk.Frame(notebook, bg=COLORS["surface"])
notebook.add(live_tab, text="Live Camera")
notebook.add(records_tab, text="Records")

live_tab.columnconfigure(0, weight=1)
live_tab.columnconfigure(1, weight=0)
live_tab.rowconfigure(1, weight=1)

mode_label_var = tk.StringVar(value="No mode selected")
tk.Label(live_tab, textvariable=mode_label_var, font=FONTS["section"], bg=COLORS["surface"], fg=COLORS["navy"]).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

camera_frame = tk.Frame(live_tab, bg=COLORS["black"], highlightbackground=COLORS["line"], highlightthickness=1)
camera_frame.grid(row=1, column=0, sticky="nsew", padx=(14, 10), pady=(0, 14))
camera_frame.columnconfigure(0, weight=1)
camera_frame.rowconfigure(0, weight=1)
camera_label = tk.Label(camera_frame, text="Choose a live option to start the camera feed.", bg=COLORS["black"], fg="#dce4ed", font=("Segoe UI", 15))
camera_label.grid(row=0, column=0, sticky="nsew")

stats_panel = tk.Frame(live_tab, bg=COLORS["surface"], width=250)
stats_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 14), pady=(12, 14))
stats_panel.grid_propagate(False)

camera_state_var = tk.StringVar(value="Stopped")
live_status_var = tk.StringVar(value="Idle")
live_faces_var = tk.StringVar(value="0")
live_timer_var = tk.StringVar(value="00:00")
live_focus_var = tk.StringVar(value="-")
live_risk_var = tk.StringVar(value="Safe")
live_alert_var = tk.StringVar(value="0")
live_saved_var = tk.StringVar(value="0")
warning_var = tk.StringVar(value="")

stat_specs = [
    ("Camera", camera_state_var, COLORS["teal"]),
    ("Status", live_status_var, COLORS["green"]),
    ("Detection", live_faces_var, COLORS["blue"]),
    ("Timer", live_timer_var, COLORS["gold"]),
    ("Focus", live_focus_var, COLORS["blue"]),
    ("Risk", live_risk_var, COLORS["red"]),
    ("Alerts", live_alert_var, COLORS["red"]),
    ("Saved", live_saved_var, COLORS["green"]),
]

for label, variable, color in stat_specs:
    box = tk.Frame(stats_panel, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
    box.pack(fill="x", pady=4)
    tk.Label(box, text=label, font=FONTS["small"], bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w", padx=10, pady=(7, 0))
    tk.Label(box, textvariable=variable, font=("Segoe UI", 14, "bold"), bg=COLORS["card"], fg=color, wraplength=220).pack(anchor="w", padx=10, pady=(0, 7))

tk.Label(stats_panel, textvariable=warning_var, font=FONTS["small"], bg="#fff2df", fg=COLORS["red"], wraplength=225, justify="left").pack(fill="x", pady=(8, 0))

records_tab.columnconfigure(0, weight=1)
records_tab.rowconfigure(2, weight=1)

records_header = tk.Frame(records_tab, bg=COLORS["surface"])
records_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
records_header.columnconfigure(2, weight=1)
tk.Label(records_header, text="Live Records Register", font=FONTS["section"], bg=COLORS["surface"], fg=COLORS["navy"]).grid(row=0, column=0, sticky="w")
row_count_var = tk.StringVar(value="Ready")
tk.Label(records_header, textvariable=row_count_var, font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["muted"]).grid(row=0, column=2, sticky="e")

controls = tk.Frame(records_tab, bg=COLORS["surface"])
controls.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
tk.Label(controls, text="Table", font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["ink"]).pack(side="left")
selected_table = tk.StringVar(value=TABLE_OPTIONS[0])
table_dropdown = ttk.Combobox(controls, textvariable=selected_table, values=TABLE_OPTIONS, state="readonly", width=24)
table_dropdown.pack(side="left", padx=(8, 10))
table_dropdown.bind("<<ComboboxSelected>>", lambda _event: load_table())
tk.Button(controls, text="Refresh Now", command=load_table, bg=COLORS["navy"], fg="#ffffff", relief="flat", bd=0, font=FONTS["button"], padx=16, pady=6).pack(side="left")

tree_wrap = tk.Frame(records_tab, bg=COLORS["line"])
tree_wrap.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
tree_wrap.columnconfigure(0, weight=1)
tree_wrap.rowconfigure(0, weight=1)
tree = ttk.Treeview(tree_wrap, show="headings", style="Modern.Treeview")
tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=(1, 0))
v_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
h_scroll = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
v_scroll.grid(row=0, column=1, sticky="ns", pady=(1, 0))
h_scroll.grid(row=1, column=0, sticky="ew", padx=(1, 0))
tree.tag_configure("odd", background="#f6f8f9")
tree.tag_configure("even", background="#ffffff")

add_activity("Dashboard ready")
add_activity("All options now run as live in-dashboard modes")
refresh_database_metrics()
load_table()
update_clock()
update_ui()
auto_refresh_records()
root.mainloop()

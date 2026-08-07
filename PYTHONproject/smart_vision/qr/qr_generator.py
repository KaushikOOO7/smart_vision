# ==========================================================
# SMART VISION AI DASHBOARD — FULLY UNIFIED LIVE UI
# All modes run INSIDE the dashboard (no separate windows)
# ==========================================================

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import mediapipe as mp
import threading
import time
import os
import sys
import queue
from PIL import Image, ImageTk
from datetime import datetime

# ==========================================================
# PATH FIX
# ==========================================================

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# ==========================================================
# DATABASE
# ==========================================================

import mysql.connector

try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="k1a2u3s4h5",
        database="smart_vision"
    )
    cursor = db.cursor()
    DB_CONNECTED = True
    print("DATABASE CONNECTED SUCCESSFULLY")
except mysql.connector.Error as err:
    DB_CONNECTED = False
    print(f"DATABASE ERROR: {err}")

# ==========================================================
# FACE RECOGNITION (optional — graceful fallback)
# ==========================================================

try:
    from ai.face_recognition_module import detect_face
    FACE_RECOG = True
except Exception:
    FACE_RECOG = False
    def detect_face(frame):
        return "UNKNOWN"

# ==========================================================
# DB HELPERS
# ==========================================================

def db_save_student_attendance(name, usn, mode):
    if not DB_CONNECTED:
        return
    try:
        cursor.execute(
            "INSERT INTO student_attendance (name, usn, mode, timestamp) VALUES (%s, %s, %s, %s)",
            (name, usn, mode, datetime.now())
        )
        db.commit()
    except Exception as e:
        print(f"Attendance DB error: {e}")

def db_save_alert(alert_type, severity, mode):
    if not DB_CONNECTED:
        return
    try:
        cursor.execute(
            "INSERT INTO alerts (type, severity, mode, timestamp) VALUES (%s, %s, %s, %s)",
            (alert_type, severity, mode, datetime.now())
        )
        db.commit()
    except Exception as e:
        print(f"Alert DB error: {e}")

# ==========================================================
# FOLDERS
# ==========================================================

for folder in ["logs", "alerts", "attendance", "evidence", "recordings", "qr_codes"]:
    os.makedirs(folder, exist_ok=True)

# ==========================================================
# THEME
# ==========================================================

BG_DEEP      = "#0a0e1a"
BG_PANEL     = "#0f1624"
BG_CARD      = "#131d2e"
BG_HOVER     = "#1a2640"
ACCENT_CYAN  = "#00d4ff"
ACCENT_BLUE  = "#0088ff"
ACCENT_GREEN = "#00ff9d"
ACCENT_RED   = "#ff4757"
ACCENT_PURPLE= "#a855f7"
ACCENT_ORANGE= "#ff9f43"
TEXT_PRIMARY  = "#e8f4fd"
TEXT_SECONDARY= "#8ba3c7"
TEXT_DIM      = "#3a5270"
BORDER_GLOW   = "#1e3a5f"

FONT_TITLE   = ("Courier New", 20, "bold")
FONT_HEADING = ("Courier New", 11, "bold")
FONT_MONO    = ("Courier New", 10)
FONT_MONO_SM = ("Courier New", 9)
FONT_BTN     = ("Courier New", 11, "bold")
FONT_CLOCK   = ("Courier New", 14, "bold")
FONT_STATUS  = ("Courier New", 9, "bold")
FONT_STAT_VAL= ("Courier New", 17, "bold")

# ==========================================================
# GLOBAL STATE
# ==========================================================

current_mode    = None        # None | "classroom" | "exam" | "night" | "qr"
camera_running  = False
camera_thread   = None
cap             = None
frame_queue     = queue.Queue(maxsize=2)

# Per-mode live stats (updated by camera thread, read by UI)
live_stats = {
    # classroom
    "student_count": 0,
    "lecture_time": 0,
    "teacher_name": "Dr Ravi",
    "attendance_saved": set(),
    # exam
    "suspicious_score": 0,
    "risk_level": "SAFE",
    "risk_color": ACCENT_GREEN,
    "total_faces": 0,
    "engagement": 0,
    "exam_time": "00:00",
    "student_name": "NOT VERIFIED",
    "head_movements": 0,
    "multi_face": 0,
    "warning_msg": "",
    # night
    "intruder": False,
    "motion_level": "NONE",
    "recording": False,
    "night_alerts": 0,
    # qr
    "qr_data": "SCANNING...",
    "qr_verified": False,
}

mode_start_time = time.time()

# ==========================================================
# ROOT WINDOW
# ==========================================================

root = tk.Tk()
root.title("SMART VISION AI DASHBOARD")
root.geometry("1500x900")
root.configure(bg=BG_DEEP)
root.resizable(True, True)

# ==========================================================
# TOP BAR
# ==========================================================

top_bar = tk.Frame(root, bg=BG_PANEL, height=58)
top_bar.pack(fill="x", side="top")
top_bar.pack_propagate(False)

tk.Label(
    top_bar,
    text="◈ SMART VISION",
    font=("Courier New", 18, "bold"),
    bg=BG_PANEL, fg=ACCENT_CYAN
).pack(side="left", padx=(20, 0), pady=10)

tk.Label(
    top_bar,
    text="  AI CONTROL CENTER",
    font=("Courier New", 12),
    bg=BG_PANEL, fg=TEXT_SECONDARY
).pack(side="left", pady=(14, 0))

# Status dots (top right)
status_right = tk.Frame(top_bar, bg=BG_PANEL)
status_right.pack(side="right", padx=20)

dot_camera_var = tk.StringVar(value="●")
dot_system_var = tk.StringVar(value="●")
dot_db_var     = tk.StringVar(value="●")

for dot_var, label, color in [
    (dot_camera_var, "CAMERA", ACCENT_GREEN),
    (dot_system_var, "SYSTEM ONLINE", ACCENT_CYAN),
    (dot_db_var,     "DB " + ("CONNECTED" if DB_CONNECTED else "ERROR"),
                     ACCENT_GREEN if DB_CONNECTED else ACCENT_RED),
]:
    f = tk.Frame(status_right, bg=BG_PANEL)
    f.pack(side="left", padx=10)
    tk.Label(f, textvariable=dot_var if dot_var is dot_camera_var else tk.StringVar(value="●"),
             font=("Courier New", 11), bg=BG_PANEL, fg=color).pack(side="left")
    tk.Label(f, text=f" {label}", font=FONT_STATUS, bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left")

# clock
clock_bar = tk.Frame(root, bg=BG_DEEP)
clock_bar.pack(fill="x", padx=20, pady=(4, 0))

time_label = tk.Label(clock_bar, text="", font=FONT_CLOCK, bg=BG_DEEP, fg=ACCENT_CYAN)
time_label.pack(side="left")
tk.Label(clock_bar, text="  ◆  NEURAL SURVEILLANCE SYSTEM v3.0",
         font=FONT_STATUS, bg=BG_DEEP, fg=TEXT_DIM).pack(side="left", pady=(2, 0))

mode_badge = tk.Label(clock_bar, text="● IDLE", font=FONT_STATUS, bg=BG_DEEP, fg=TEXT_DIM)
mode_badge.pack(side="right", padx=10)

def update_clock():
    time_label.config(text="⏱  " + datetime.now().strftime("%d-%m-%Y   %H:%M:%S"))
    root.after(1000, update_clock)

# ==========================================================
# MAIN LAYOUT  (left panel + right content)
# ==========================================================

tk.Frame(root, bg=BORDER_GLOW, height=1).pack(fill="x")

main_frame = tk.Frame(root, bg=BG_DEEP)
main_frame.pack(fill="both", expand=True, padx=0, pady=0)

# --- LEFT PANEL ---
left_panel = tk.Frame(main_frame, bg=BG_PANEL, width=230)
left_panel.pack(side="left", fill="y")
left_panel.pack_propagate(False)

# --- RIGHT CONTENT ---
right_content = tk.Frame(main_frame, bg=BG_DEEP)
right_content.pack(side="left", fill="both", expand=True)

# ==========================================================
# LEFT PANEL — MODE BUTTONS
# ==========================================================

def sec_label(parent, text, color=ACCENT_CYAN):
    tk.Label(parent, text=f"▸ {text}", font=FONT_HEADING,
             bg=BG_PANEL, fg=color).pack(anchor="w", padx=14, pady=(10, 4))
    tk.Frame(parent, bg=BORDER_GLOW, height=1).pack(fill="x", padx=14)

sec_label(left_panel, "OPERATION MODES")

MODE_BTNS = [
    ("⬡  CLASSROOM",  "classroom", ACCENT_GREEN),
    ("◈  EXAM MODE",  "exam",      ACCENT_BLUE),
    ("◐  NIGHT MODE", "night",     ACCENT_PURPLE),
    ("⬢  QR LOGIN",   "qr",        ACCENT_RED),
]

active_btn_refs = {}

def make_mode_btn(parent, label, mode_key, color):
    f = tk.Frame(parent, bg=BG_PANEL)
    f.pack(fill="x", padx=12, pady=4)

    btn = tk.Button(
        f,
        text=label,
        font=FONT_BTN,
        bg=BG_CARD,
        fg=color,
        relief="flat",
        bd=0,
        padx=10,
        pady=10,
        cursor="hand2",
        activebackground=BG_HOVER,
        activeforeground=color,
        anchor="w",
        width=18,
        command=lambda m=mode_key: switch_mode(m),
    )
    btn.pack(fill="x")
    active_btn_refs[mode_key] = btn

for lbl, key, clr in MODE_BTNS:
    make_mode_btn(left_panel, lbl, key, clr)

# --- Stop button ---
tk.Frame(left_panel, bg=BORDER_GLOW, height=1).pack(fill="x", padx=14, pady=(14, 4))

stop_btn = tk.Button(
    left_panel,
    text="◼  STOP MODE",
    font=FONT_BTN,
    bg=BG_CARD, fg=ACCENT_ORANGE,
    relief="flat", bd=0,
    padx=10, pady=8,
    cursor="hand2",
    activebackground=BG_HOVER,
    activeforeground=ACCENT_ORANGE,
    anchor="w", width=18,
    command=lambda: switch_mode(None),
)
stop_btn.pack(fill="x", padx=12, pady=2)

# --- Metrics section ---
sec_label(left_panel, "LIVE METRICS", ACCENT_CYAN)

metric_labels = {}

def make_metric(parent, key, label, color):
    f = tk.Frame(parent, bg=BG_CARD, bd=0)
    f.pack(fill="x", padx=12, pady=3)
    tk.Label(f, text=label, font=FONT_MONO_SM, bg=BG_CARD, fg=TEXT_DIM).pack(anchor="w", padx=8, pady=(5, 0))
    v = tk.Label(f, text="—", font=("Courier New", 14, "bold"), bg=BG_CARD, fg=color)
    v.pack(anchor="w", padx=8, pady=(0, 5))
    metric_labels[key] = v

make_metric(left_panel, "faces",   "FACES DETECTED", ACCENT_CYAN)
make_metric(left_panel, "status",  "MODE STATUS",    ACCENT_GREEN)
make_metric(left_panel, "alerts",  "ALERTS",         ACCENT_RED)
make_metric(left_panel, "score",   "RISK / SCORE",   ACCENT_ORANGE)

# --- Exit ---
tk.Frame(left_panel, bg=BORDER_GLOW, height=1).pack(fill="x", padx=14, pady=(12, 4))
tk.Button(
    left_panel,
    text="■  EXIT SYSTEM",
    font=FONT_BTN,
    bg="#1a0a0a", fg=ACCENT_RED,
    relief="flat", bd=0,
    padx=10, pady=10,
    cursor="hand2",
    activebackground="#2a0a0a",
    activeforeground=ACCENT_RED,
    width=18,
    command=lambda: on_exit(),
).pack(fill="x", padx=12, pady=4)

# ==========================================================
# RIGHT CONTENT — NOTEBOOK (Camera | Database)
# ==========================================================

style = ttk.Style()
style.theme_use("default")
style.configure("Dark.TNotebook",        background=BG_DEEP, borderwidth=0)
style.configure("Dark.TNotebook.Tab",    background=BG_PANEL, foreground=TEXT_SECONDARY,
                font=FONT_HEADING, padding=[14, 6])
style.map("Dark.TNotebook.Tab",
          background=[("selected", BG_CARD)],
          foreground=[("selected", ACCENT_CYAN)])

notebook = ttk.Notebook(right_content, style="Dark.TNotebook")
notebook.pack(fill="both", expand=True, padx=6, pady=6)

# ---- TAB 1: LIVE CAMERA ----
cam_tab = tk.Frame(notebook, bg=BG_DEEP)
notebook.add(cam_tab, text="  ◈ LIVE CAMERA  ")

cam_top = tk.Frame(cam_tab, bg=BG_DEEP)
cam_top.pack(fill="both", expand=True)

# Camera canvas
cam_canvas_frame = tk.Frame(cam_top, bg=BG_CARD, bd=0)
cam_canvas_frame.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

cam_label = tk.Label(cam_canvas_frame, bg=BG_CARD,
                     text="◈  NO MODE ACTIVE\n\nSelect a mode from the left panel\nto start the live camera feed.",
                     font=("Courier New", 14), fg=TEXT_DIM)
cam_label.pack(fill="both", expand=True)

# Stats sidebar
stats_sidebar = tk.Frame(cam_top, bg=BG_PANEL, width=230)
stats_sidebar.pack(side="right", fill="y", padx=(0, 8), pady=8)
stats_sidebar.pack_propagate(False)

tk.Label(stats_sidebar, text="▸ MODE DETAILS", font=FONT_HEADING,
         bg=BG_PANEL, fg=ACCENT_CYAN).pack(anchor="w", padx=12, pady=(10, 4))
tk.Frame(stats_sidebar, bg=BORDER_GLOW, height=1).pack(fill="x", padx=12)

# Dynamic stats cards
stat_card_data = {}

def make_stat_card(parent, key, label, color=ACCENT_CYAN):
    f = tk.Frame(parent, bg=BG_CARD)
    f.pack(fill="x", padx=10, pady=4)
    tk.Label(f, text=label, font=FONT_MONO_SM, bg=BG_CARD, fg=TEXT_DIM).pack(anchor="w", padx=8, pady=(6, 0))
    v = tk.Label(f, text="—", font=FONT_STAT_VAL, bg=BG_CARD, fg=color)
    v.pack(anchor="w", padx=8, pady=(0, 6))
    stat_card_data[key] = v

make_stat_card(stats_sidebar, "s1", "STUDENTS / FACES",  ACCENT_GREEN)
make_stat_card(stats_sidebar, "s2", "MODE TIMER",        ACCENT_CYAN)
make_stat_card(stats_sidebar, "s3", "ATTENTION / FOCUS", ACCENT_ORANGE)
make_stat_card(stats_sidebar, "s4", "RISK LEVEL",        ACCENT_RED)
make_stat_card(stats_sidebar, "s5", "ATTENDANCE SAVED",  ACCENT_GREEN)
make_stat_card(stats_sidebar, "s6", "WARNINGS",          ACCENT_RED)

# Warning banner
warn_banner = tk.Label(
    stats_sidebar,
    text="",
    font=("Courier New", 9, "bold"),
    bg="#1a0a0a", fg=ACCENT_RED,
    wraplength=200, justify="left"
)
warn_banner.pack(fill="x", padx=10, pady=6)

# ---- TAB 2: DATABASE VIEWER ----
db_tab = tk.Frame(notebook, bg=BG_DEEP)
notebook.add(db_tab, text="  ◆ DATABASE VIEWER  ")

db_controls = tk.Frame(db_tab, bg=BG_DEEP)
db_controls.pack(fill="x", padx=10, pady=8)

tk.Label(db_controls, text="TABLE ▸", font=FONT_MONO,
         bg=BG_DEEP, fg=TEXT_SECONDARY).pack(side="left")

selected_table = tk.StringVar(value="student_attendance")
table_options = ["student_attendance", "teacher_attendance",
                 "exam_reports", "night_security", "alerts"]

style.configure("D.TCombobox",
                fieldbackground=BG_CARD, background=BG_CARD,
                foreground=TEXT_PRIMARY, selectbackground=BG_HOVER,
                selectforeground=ACCENT_CYAN, bordercolor=BORDER_GLOW,
                arrowcolor=ACCENT_CYAN)
style.map("D.TCombobox",
          fieldbackground=[("readonly", BG_CARD)],
          selectbackground=[("readonly", BG_CARD)],
          selectforeground=[("readonly", ACCENT_CYAN)])

dropdown = ttk.Combobox(
    db_controls, textvariable=selected_table,
    values=table_options, state="readonly",
    style="D.TCombobox", font=FONT_MONO, width=26
)
dropdown.pack(side="left", padx=(8, 12))

row_count_lbl = tk.Label(db_controls, text="", font=FONT_MONO_SM, bg=BG_DEEP, fg=TEXT_DIM)
row_count_lbl.pack(side="right", padx=8)

tk.Button(
    db_controls, text="⟳  REFRESH", command=lambda: load_table(),
    bg=BG_CARD, fg=ACCENT_CYAN, font=FONT_MONO,
    relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
    activebackground=BG_HOVER, activeforeground=ACCENT_CYAN
).pack(side="left")

# Treeview
style.configure("D.Treeview",
                background=BG_CARD, foreground=TEXT_PRIMARY,
                rowheight=26, fieldbackground=BG_CARD,
                borderwidth=0, font=("Courier New", 10))
style.configure("D.Treeview.Heading",
                background=BG_PANEL, foreground=ACCENT_CYAN,
                font=("Courier New", 10, "bold"), relief="flat", borderwidth=0)
style.map("D.Treeview",
          background=[("selected", BG_HOVER)],
          foreground=[("selected", ACCENT_CYAN)])

tree_wrap = tk.Frame(db_tab, bg=BORDER_GLOW, bd=1)
tree_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
tree_inner = tk.Frame(tree_wrap, bg=BG_CARD)
tree_inner.pack(fill="both", expand=True, padx=1, pady=1)

v_sc = tk.Scrollbar(tree_inner, orient="vertical",   bg=BG_PANEL, troughcolor=BG_CARD)
h_sc = tk.Scrollbar(tree_inner, orient="horizontal", bg=BG_PANEL, troughcolor=BG_CARD)
v_sc.pack(side="right", fill="y")
h_sc.pack(side="bottom", fill="x")

tree = ttk.Treeview(tree_inner, show="headings", style="D.Treeview",
                    yscrollcommand=v_sc.set, xscrollcommand=h_sc.set)
tree.pack(fill="both", expand=True)
v_sc.config(command=tree.yview)
h_sc.config(command=tree.xview)
tree.tag_configure("odd",  background=BG_CARD)
tree.tag_configure("even", background=BG_PANEL)

dropdown.bind("<<ComboboxSelected>>", lambda e: load_table())

# ==========================================================
# STATUS BAR
# ==========================================================

status_bar = tk.Frame(root, bg=BG_PANEL, height=24)
status_bar.pack(fill="x", side="bottom")
status_bar.pack_propagate(False)

status_left = tk.Label(status_bar,
    text="◆ SMART VISION AI  ●  All systems nominal  ●  Powered by OpenCV + YOLOv8",
    font=FONT_MONO_SM, bg=BG_PANEL, fg=TEXT_DIM)
status_left.pack(side="left", padx=16, pady=3)

tk.Label(status_bar, text="v3.0.0  ◆",
         font=FONT_MONO_SM, bg=BG_PANEL, fg=TEXT_DIM).pack(side="right", padx=16)

# ==========================================================
# DATABASE LOADER
# ==========================================================

def load_table():
    if not DB_CONNECTED:
        row_count_lbl.config(text="NO DB ●", fg=ACCENT_RED)
        return
    table_name = selected_table.get()
    try:
        for item in tree.get_children():
            tree.delete(item)
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col.upper().replace("_", " "))
            tree.column(col, width=160, anchor="center")
        for i, row in enumerate(rows):
            tree.insert("", tk.END, values=row, tags=("even" if i % 2 == 0 else "odd",))
        count = len(rows)
        row_count_lbl.config(
            text=f"{count} RECORD{'S' if count != 1 else ''}  ●",
            fg=ACCENT_GREEN if count > 0 else ACCENT_RED
        )
    except Exception as e:
        messagebox.showerror("Database Error", str(e))

# ==========================================================
# MEDIAPIPE SETUP (shared across modes)
# ==========================================================

mp_face       = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(min_detection_confidence=0.5)

# ==========================================================
# CAMERA THREAD — processes frames for each mode
# ==========================================================

def camera_worker():
    global cap, camera_running, live_stats, mode_start_time

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

    if not cap.isOpened():
        camera_running = False
        return

    # QR scanner
    qr_decoder = cv2.QRCodeDetector()

    # For night mode — background subtractor
    motion_detector = cv2.createBackgroundSubtractorMOG2()

    night_alert_count = 0
    exam_attendance_set = set()
    classroom_attendance_set = set()

    while camera_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.03)
            continue

        mode = current_mode
        h, w, _ = frame.shape

        # Overlay: dark top strip for stats
        overlay_h = 36
        cv2.rectangle(frame, (0, 0), (w, overlay_h), (10, 14, 26), -1)

        elapsed = int(time.time() - mode_start_time)

        # ── CLASSROOM MODE ──────────────────────────────────
        if mode == "classroom":
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = face_detector.process(rgb)
            count = 0

            if res.detections:
                for det in res.detections:
                    bb = det.location_data.relative_bounding_box
                    x = max(0, int(bb.xmin * w))
                    y = max(0, int(bb.ymin * h))
                    bw = max(1, int(bb.width * w))
                    bh = max(1, int(bb.height * h))

                    # Cyan scan-line box
                    cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0, 212, 255), 2)
                    # Corner accents
                    cl = 10
                    for (ax, ay, dx, dy) in [
                        (x,y,1,1),(x+bw,y,-1,1),(x,y+bh,1,-1),(x+bw,y+bh,-1,-1)
                    ]:
                        cv2.line(frame,(ax,ay),(ax+dx*cl,ay),(0,255,157),2)
                        cv2.line(frame,(ax,ay),(ax,ay+dy*cl),(0,255,157),2)

                    count += 1
                    face_crop = frame[y:y+bh, x:x+bw]

                    if FACE_RECOG:
                        try:
                            name = detect_face(face_crop) or "UNKNOWN"
                        except Exception:
                            name = "UNKNOWN"
                    else:
                        name = "STUDENT"

                    # Name tag with dark bg
                    tag = f" {str(name)} "
                    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                    cv2.rectangle(frame, (x, y-th-8), (x+tw+4, y), (0, 212, 255), -1)
                    cv2.putText(frame, tag, (x+2, y-4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 14, 26), 1)

                    if name != "UNKNOWN" and name not in classroom_attendance_set:
                        classroom_attendance_set.add(name)
                        db_save_student_attendance(name, "4VP22CS001", "CLASSROOM")

            live_stats["student_count"] = count
            live_stats["lecture_time"]  = elapsed
            live_stats["attendance_saved"] = classroom_attendance_set.copy()

            # HUD
            mins, secs = elapsed // 60, elapsed % 60
            cv2.putText(frame, f"CLASSROOM MODE  |  Teacher: {live_stats['teacher_name']}",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 212, 255), 1)
            cv2.putText(frame, f"Lecture: {mins:02}:{secs:02}  |  Students: {count}  |  Saved: {len(classroom_attendance_set)}",
                        (10, h-14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 157), 1)

        # ── EXAM MODE ───────────────────────────────────────
        elif mode == "exam":
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = face_detector.process(rgb)
            total_faces = 0
            attentive   = 0
            warning     = ""

            if res.detections:
                for det in res.detections:
                    total_faces += 1
                    bb   = det.location_data.relative_bounding_box
                    x    = max(0, int(bb.xmin * w))
                    y    = max(0, int(bb.ymin * h))
                    bw   = max(1, int(bb.width * w))
                    bh   = max(1, int(bb.height * h))
                    cx   = x + bw // 2
                    diff = abs(cx - w // 2)

                    if diff < 200:
                        attentive += 1
                        color  = (0, 255, 157)
                        status = "FOCUSED"
                    else:
                        live_stats["suspicious_score"] += 1
                        live_stats["head_movements"]   += 1
                        color  = (0, 60, 255)
                        status = "DISTRACTED"
                        warning = "⚠ HEAD MOVEMENT"
                        db_save_alert("HEAD_MOVEMENT", "MEDIUM", "EXAM")

                    cv2.rectangle(frame, (x, y), (x+bw, y+bh), color, 2)
                    cv2.putText(frame, status, (x, y-8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

            if total_faces > 1:
                live_stats["suspicious_score"] += 3
                live_stats["multi_face"]       += 1
                warning = "⚠ MULTIPLE PERSONS"
                db_save_alert("MULTIPLE_FACE", "HIGH", "EXAM")

            if total_faces == 0:
                live_stats["suspicious_score"] += 1
                warning = "⚠ NO FACE DETECTED"

            engagement = int((attentive / total_faces * 100)) if total_faces > 0 else 0
            sc = live_stats["suspicious_score"]
            if sc > 40:
                risk, rcol = "CRITICAL",  ACCENT_RED
            elif sc > 20:
                risk, rcol = "HIGH RISK", ACCENT_ORANGE
            elif sc > 10:
                risk, rcol = "WARNING",   ACCENT_ORANGE
            else:
                risk, rcol = "SAFE",      ACCENT_GREEN

            live_stats.update({
                "total_faces": total_faces,
                "engagement":  engagement,
                "risk_level":  risk,
                "risk_color":  rcol,
                "warning_msg": warning,
                "exam_time":   f"{elapsed//60:02}:{elapsed%60:02}",
            })

            mins, secs = elapsed // 60, elapsed % 60
            cv2.putText(frame, f"EXAM PROCTORING  |  Timer: {mins:02}:{secs:02}  |  Faces: {total_faces}",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 136, 255), 1)
            if warning:
                cv2.putText(frame, warning, (w//2 - 150, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 60, 255), 2)
            cv2.putText(frame, f"Risk: {risk}  |  Score: {sc}  |  Focus: {engagement}%",
                        (10, h-14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 212, 255), 1)

        # ── NIGHT MODE ──────────────────────────────────────
        elif mode == "night":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            mask = motion_detector.apply(gray)
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            # Restricted zone
            zx1, zy1, zx2, zy2 = 100, 80, w-100, h-80
            cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), (0, 60, 255), 2)
            cv2.putText(frame, "RESTRICTED ZONE", (zx1+8, zy1-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 60, 255), 1)

            intruder = False
            motion_level = "NONE"
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 4000:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    motion_level = "HIGH" if area > 15000 else "MEDIUM"
                    cv2.rectangle(frame, (x, y), (x+cw, y+ch), (0, 255, 157), 2)
                    # Check restricted zone intrusion
                    cx_, cy_ = x+cw//2, y+ch//2
                    if zx1 < cx_ < zx2 and zy1 < cy_ < zy2:
                        intruder = True
                        night_alert_count += 1
                        db_save_alert("INTRUDER", "CRITICAL", "NIGHT")
                        cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 180), 4)
                        cv2.putText(frame, "⚠ INTRUDER ALERT", (w//2-160, h//2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)

            live_stats["intruder"]     = intruder
            live_stats["motion_level"] = motion_level
            live_stats["night_alerts"] = night_alert_count

            # Night vision tint
            b, g, r = cv2.split(frame)
            frame = cv2.merge([b//2, g, r//2])

            cv2.putText(frame, f"NIGHT SECURITY  |  Motion: {motion_level}  |  Alerts: {night_alert_count}",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 157), 1)

        # ── QR MODE ─────────────────────────────────────────
        elif mode == "qr":
            data, bbox, _ = qr_decoder.detectAndDecode(frame)
            if data:
                live_stats["qr_data"]     = data
                live_stats["qr_verified"] = True
                if bbox is not None:
                    bbox = bbox.astype(int)
                    for i in range(len(bbox[0])):
                        pt1 = tuple(bbox[0][i])
                        pt2 = tuple(bbox[0][(i+1) % len(bbox[0])])
                        cv2.line(frame, pt1, pt2, (0, 255, 157), 3)
                cv2.putText(frame, "✓ QR VERIFIED", (w//2-120, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 157), 2)
            else:
                live_stats["qr_data"]     = "SCANNING..."
                live_stats["qr_verified"] = False

            # Scanning animation box in center
            cx, cy = w//2, h//2
            sz = 140
            cv2.rectangle(frame, (cx-sz, cy-sz), (cx+sz, cy+sz), (0, 212, 255), 2)
            for (sx, sy, ddx, ddy) in [
                (cx-sz, cy-sz, 1, 1), (cx+sz, cy-sz, -1, 1),
                (cx-sz, cy+sz, 1, -1), (cx+sz, cy+sz, -1, -1)
            ]:
                cv2.line(frame, (sx, sy), (sx+ddx*30, sy),   (0, 255, 157), 3)
                cv2.line(frame, (sx, sy), (sx, sy+ddy*30),   (0, 255, 157), 3)

            cv2.putText(frame, "QR LOGIN  |  Point QR code at camera",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 120, 70), 1)

        # ── IDLE ────────────────────────────────────────────
        else:
            cv2.putText(frame, "SELECT A MODE FROM THE DASHBOARD",
                        (w//2 - 220, h//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (58, 82, 112), 2)

        # Timestamp watermark
        ts = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        cv2.putText(frame, ts, (w - 200, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (58, 82, 112), 1)

        # Push frame to queue
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if not frame_queue.full():
            frame_queue.put(rgb_frame)

        time.sleep(0.025)

    cap.release()

# ==========================================================
# UI FRAME UPDATE LOOP
# ==========================================================

def update_ui():
    # Update camera frame
    try:
        frame = frame_queue.get_nowait()
        img = Image.fromarray(frame)
        # Fit to cam_canvas_frame
        fw = cam_canvas_frame.winfo_width()
        fh = cam_canvas_frame.winfo_height()
        if fw > 10 and fh > 10:
            img = img.resize((fw, fh), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        cam_label.config(image=photo, text="")
        cam_label.image = photo
    except queue.Empty:
        pass

    mode = current_mode

    # ── Update sidebar stats ─────────────────────────────
    if mode == "classroom":
        elapsed = live_stats["lecture_time"]
        stat_card_data["s1"].config(text=str(live_stats["student_count"]),        fg=ACCENT_GREEN)
        stat_card_data["s2"].config(text=f"{elapsed//60:02}:{elapsed%60:02}",     fg=ACCENT_CYAN)
        stat_card_data["s3"].config(text="—",                                     fg=ACCENT_ORANGE)
        stat_card_data["s4"].config(text="SAFE",                                  fg=ACCENT_GREEN)
        stat_card_data["s5"].config(text=str(len(live_stats["attendance_saved"])), fg=ACCENT_GREEN)
        stat_card_data["s6"].config(text="0",                                     fg=ACCENT_RED)
        warn_banner.config(text="")
        metric_labels["faces"].config(text=str(live_stats["student_count"]))
        metric_labels["status"].config(text="ACTIVE", fg=ACCENT_GREEN)
        metric_labels["alerts"].config(text="0")
        metric_labels["score"].config(text="—")

    elif mode == "exam":
        sc  = live_stats["suspicious_score"]
        eng = live_stats["engagement"]
        risk= live_stats["risk_level"]
        rc  = live_stats["risk_color"]
        stat_card_data["s1"].config(text=str(live_stats["total_faces"]),      fg=ACCENT_CYAN)
        stat_card_data["s2"].config(text=live_stats["exam_time"],             fg=ACCENT_CYAN)
        stat_card_data["s3"].config(text=f"{eng}%",                          fg=ACCENT_ORANGE)
        stat_card_data["s4"].config(text=risk,                               fg=rc)
        stat_card_data["s5"].config(text=str(live_stats["multi_face"]),       fg=ACCENT_RED)
        stat_card_data["s6"].config(text=str(live_stats["head_movements"]),   fg=ACCENT_RED)
        warn = live_stats["warning_msg"]
        warn_banner.config(text=warn if warn else "")
        metric_labels["faces"].config(text=str(live_stats["total_faces"]))
        metric_labels["status"].config(text=risk, fg=rc)
        metric_labels["alerts"].config(text=str(live_stats["multi_face"]))
        metric_labels["score"].config(text=str(sc))

    elif mode == "night":
        alert_c = ACCENT_RED if live_stats["intruder"] else ACCENT_GREEN
        stat_card_data["s1"].config(text="INTRUDER" if live_stats["intruder"] else "CLEAR", fg=alert_c)
        stat_card_data["s2"].config(text=f"{int(time.time()-mode_start_time)//60:02}:{int(time.time()-mode_start_time)%60:02}", fg=ACCENT_CYAN)
        stat_card_data["s3"].config(text=live_stats["motion_level"],          fg=ACCENT_ORANGE)
        stat_card_data["s4"].config(text="HIGH RISK" if live_stats["intruder"] else "CLEAR", fg=alert_c)
        stat_card_data["s5"].config(text="—",                                fg=TEXT_DIM)
        stat_card_data["s6"].config(text=str(live_stats["night_alerts"]),     fg=ACCENT_RED)
        warn_banner.config(text="⚠ INTRUDER DETECTED" if live_stats["intruder"] else "")
        metric_labels["faces"].config(text="MOTION: " + live_stats["motion_level"])
        metric_labels["status"].config(text="ALERT" if live_stats["intruder"] else "WATCHING",
                                       fg=ACCENT_RED if live_stats["intruder"] else ACCENT_GREEN)
        metric_labels["alerts"].config(text=str(live_stats["night_alerts"]))
        metric_labels["score"].config(text="HIGH" if live_stats["intruder"] else "LOW")

    elif mode == "qr":
        verified = live_stats["qr_verified"]
        vc = ACCENT_GREEN if verified else ACCENT_ORANGE
        stat_card_data["s1"].config(text="VERIFIED" if verified else "SCANNING", fg=vc)
        stat_card_data["s2"].config(text=f"{int(time.time()-mode_start_time)//60:02}:{int(time.time()-mode_start_time)%60:02}", fg=ACCENT_CYAN)
        stat_card_data["s3"].config(text="—", fg=TEXT_DIM)
        stat_card_data["s4"].config(text="—", fg=TEXT_DIM)
        stat_card_data["s5"].config(text="—", fg=TEXT_DIM)
        stat_card_data["s6"].config(text="—", fg=TEXT_DIM)
        qd = live_stats["qr_data"]
        warn_banner.config(text=qd[:80] if qd != "SCANNING..." else "", fg=ACCENT_GREEN if verified else ACCENT_ORANGE)
        metric_labels["faces"].config(text="QR: " + ("OK" if verified else "—"))
        metric_labels["status"].config(text="VERIFIED" if verified else "SCANNING",
                                       fg=ACCENT_GREEN if verified else ACCENT_ORANGE)
        metric_labels["alerts"].config(text="0")
        metric_labels["score"].config(text="—")

    else:
        for k in stat_card_data:
            stat_card_data[k].config(text="—", fg=TEXT_DIM)
        warn_banner.config(text="")
        for k in metric_labels:
            metric_labels[k].config(text="—", fg=TEXT_DIM)

    root.after(40, update_ui)   # ~25 fps UI refresh

# ==========================================================
# MODE SWITCHER
# ==========================================================

MODE_COLORS = {
    "classroom": ACCENT_GREEN,
    "exam":      ACCENT_BLUE,
    "night":     ACCENT_PURPLE,
    "qr":        ACCENT_RED,
    None:        TEXT_DIM,
}

MODE_LABELS = {
    "classroom": "● CLASSROOM ACTIVE",
    "exam":      "● EXAM MODE ACTIVE",
    "night":     "● NIGHT SECURITY ACTIVE",
    "qr":        "● QR LOGIN ACTIVE",
    None:        "● IDLE",
}

def switch_mode(new_mode):
    global current_mode, camera_running, camera_thread, mode_start_time

    # Stop existing camera
    if camera_running:
        camera_running = False
        if camera_thread and camera_thread.is_alive():
            camera_thread.join(timeout=2.0)

    # Reset per-mode stats
    live_stats["suspicious_score"] = 0
    live_stats["head_movements"]   = 0
    live_stats["multi_face"]       = 0
    live_stats["warning_msg"]      = ""
    live_stats["night_alerts"]     = 0
    live_stats["qr_verified"]      = False
    live_stats["qr_data"]          = "SCANNING..."

    current_mode    = new_mode
    mode_start_time = time.time()

    # Update button highlights
    for key, btn in active_btn_refs.items():
        c = MODE_COLORS.get(key, ACCENT_CYAN)
        btn.config(bg=BG_CARD if key != new_mode else BG_HOVER,
                   relief="flat")

    # Update mode badge
    mode_badge.config(text=MODE_LABELS.get(new_mode, "● IDLE"),
                      fg=MODE_COLORS.get(new_mode, TEXT_DIM))

    if new_mode is None:
        # Show idle placeholder
        cam_label.config(
            image="",
            text="◈  NO MODE ACTIVE\n\nSelect a mode from the left panel\nto start the live camera feed.",
            font=("Courier New", 14), fg=TEXT_DIM
        )
        cam_label.image = None
        return

    # Start camera thread
    camera_running = True
    camera_thread  = threading.Thread(target=camera_worker, daemon=True)
    camera_thread.start()

    # Switch to camera tab
    notebook.select(cam_tab)

# ==========================================================
# EXIT
# ==========================================================

def on_exit():
    global camera_running
    camera_running = False
    root.after(300, root.destroy)

root.protocol("WM_DELETE_WINDOW", on_exit)

# ==========================================================
# START
# ==========================================================

update_clock()
load_table()
update_ui()
root.mainloop()

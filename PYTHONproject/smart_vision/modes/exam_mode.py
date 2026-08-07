# ==========================================================
# EXAM MODE — POLISHED PROCTORING HUD
# AI SMART EXAM PROCTORING SYSTEM
# WITH FACE RECOGNITION (mediapipe tasks API)
# ==========================================================

import cv2
import mediapipe as mp
import numpy as np
import time
import os
import sys
from datetime import datetime

# ==========================================================
# PROJECT PATH FIX
# ==========================================================

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

try:
    from ai.face_recognition_module import detect_face
except Exception:
    def detect_face(frame):
        return []

# ==========================================================
# CREATE FOLDERS
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "..")

for folder in ["logs", "evidence", "attendance"]:
    os.makedirs(os.path.join(PROJECT_DIR, folder), exist_ok=True)

# ==========================================================
# CAMERA
# ==========================================================

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

# ==========================================================
# MEDIAPIPE FACE DETECTION (new tasks API)
# ==========================================================

MODEL_PATH = os.path.join(PROJECT_DIR, "blaze_face_short_range.tflite")

BaseOptions = mp.tasks.BaseOptions
FaceDetector = mp.tasks.vision.FaceDetector
FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = FaceDetectorOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.IMAGE,
    min_detection_confidence=0.5,
)

face_detector = FaceDetector.create_from_options(options)

# ==========================================================
# HUD COLORS
# ==========================================================

HUD_CYAN = (255, 212, 0)
HUD_GREEN = (0, 255, 150)
HUD_RED = (60, 60, 255)
HUD_YELLOW = (0, 255, 255)
HUD_WHITE = (240, 240, 240)
HUD_ORANGE = (0, 160, 255)
HUD_PANEL_BG = (25, 20, 15)

# ==========================================================
# VARIABLES
# ==========================================================

student_name = "NOT VERIFIED"
student_usn = "4XX22AI001"
suspicious_score = 0
MAX_SUSPICIOUS = 100
SCORE_DECAY_RATE = 0.1
warning_message = ""
warning_timer = 0
exam_start_time = time.time()
multiple_face_count = 0
head_movement_count = 0
last_evidence_time = 0
EVIDENCE_COOLDOWN = 5

# ==========================================================
# SAVE LOG
# ==========================================================

def save_log(message):
    current = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    log_path = os.path.join(PROJECT_DIR, "logs", "exam_logs.txt")
    with open(log_path, "a") as file:
        file.write(f"[{current}] {message}\n")

# ==========================================================
# SAVE EVIDENCE (with cooldown)
# ==========================================================

def save_evidence(frame, reason):
    global last_evidence_time
    current = time.time()
    if current - last_evidence_time < EVIDENCE_COOLDOWN:
        return
    last_evidence_time = current
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    filename = os.path.join(PROJECT_DIR, "evidence", f"{reason}_{timestamp}.jpg")
    cv2.imwrite(filename, frame)
    print("Saved:", filename)

# ==========================================================
# HUD DRAWING HELPERS
# ==========================================================

def draw_overlay_panel(frame, x, y, w, h, alpha=0.75):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), HUD_PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), HUD_CYAN, 1)

def draw_hud_text(frame, text, pos, color=HUD_WHITE, scale=0.55, thickness=1):
    x, y = pos
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

def draw_risk_bar(frame, x, y, w, h, value, max_val):
    ratio = min(value / max(max_val, 1), 1.0)
    fill_w = int(w * ratio)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (40, 40, 40), -1)
    if ratio < 0.25:
        bar_color = HUD_GREEN
    elif ratio < 0.5:
        bar_color = HUD_YELLOW
    elif ratio < 0.75:
        bar_color = HUD_ORANGE
    else:
        bar_color = HUD_RED
    if fill_w > 0:
        cv2.rectangle(frame, (x, y), (x + fill_w, y + h), bar_color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (100, 100, 100), 1)

def draw_corner_brackets(frame, x, y, w, h, color, length=15, thickness=2):
    cv2.line(frame, (x, y), (x + length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + length), color, thickness)
    cv2.line(frame, (x + w, y), (x + w - length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + length), color, thickness)
    cv2.line(frame, (x, y + h), (x + length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - length), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w - length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - length), color, thickness)

# ==========================================================
# MAIN LOOP
# ==========================================================

while True:
    ret, frame = cap.read()
    if not ret:
        print("Camera Error")
        break

    frame = cv2.resize(frame, (1400, 800))
    h_frame, w_frame = frame.shape[:2]

    # Decay suspicious score
    suspicious_score = max(0, suspicious_score - SCORE_DECAY_RATE)
    suspicious_score = min(suspicious_score, MAX_SUSPICIOUS)

    # ======================================================
    # FACE DETECTION (new tasks API)
    # ======================================================

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    results = face_detector.detect(mp_image)

    # ======================================================
    # FACE RECOGNITION
    # ======================================================

    try:
        people = detect_face(frame)
    except Exception:
        people = []

    for person in people:
        name, x, y, w, h = person
        if name != "UNKNOWN":
            student_name = name.upper()
        else:
            warning_message = "UNKNOWN PERSON DETECTED"
            warning_timer = 60
            suspicious_score = min(suspicious_score + 5, MAX_SUSPICIOUS)
            save_log("UNKNOWN PERSON DETECTED")

        box_color = HUD_GREEN if name != "UNKNOWN" else HUD_RED
        draw_corner_brackets(frame, x, y, w, h, box_color, 12, 2)

        (tw, th), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x, y - th - 12), (x + tw + 8, y - 2), box_color, -1)
        cv2.putText(frame, name, (x + 4, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    total_faces = 0
    attentive_students = 0
    distracted_students = 0

    for detection in results.detections:
        total_faces += 1
        bbox = detection.bounding_box
        x = bbox.origin_x
        y = bbox.origin_y
        bw = bbox.width
        bh = bbox.height

        center_x = x + bw // 2
        frame_center = w_frame // 2
        difference = abs(center_x - frame_center)

        if difference < 200:
            attentive_students += 1
            status = "FOCUSED"
            color = HUD_GREEN
        else:
            distracted_students += 1
            suspicious_score = min(suspicious_score + 2, MAX_SUSPICIOUS)
            head_movement_count += 1
            status = "LOOKING SIDE"
            color = HUD_RED
            warning_message = "HEAD MOVEMENT DETECTED"
            warning_timer = 60
            save_evidence(frame, "HEAD_MOVEMENT")
            save_log("HEAD MOVEMENT DETECTED")

        draw_corner_brackets(frame, x, y, bw, bh, color, 10, 1)
        draw_hud_text(frame, status, (x, y - 10), color, 0.5)

    # Multiple / No face
    if total_faces > 1:
        suspicious_score = min(suspicious_score + 5, MAX_SUSPICIOUS)
        multiple_face_count += 1
        warning_message = "MULTIPLE PERSONS DETECTED"
        warning_timer = 90
        save_evidence(frame, "MULTIPLE_FACE")
        save_log("MULTIPLE PERSON DETECTED")

    if total_faces == 0:
        suspicious_score = min(suspicious_score + 3, MAX_SUSPICIOUS)
        warning_message = "NO FACE DETECTED"
        warning_timer = 30

    # Engagement / Timer / Risk
    engagement = int((attentive_students / max(total_faces, 1)) * 100)
    elapsed_time = int(time.time() - exam_start_time)
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60

    risk_level = "SAFE"
    risk_color = HUD_GREEN
    if suspicious_score > 25:
        risk_level = "WARNING"
        risk_color = HUD_YELLOW
    if suspicious_score > 50:
        risk_level = "HIGH RISK"
        risk_color = HUD_ORANGE
    if suspicious_score > 75:
        risk_level = "CRITICAL"
        risk_color = HUD_RED

    # ======================================================
    # GLASSMORPHISM SIDE PANEL
    # ======================================================

    draw_overlay_panel(frame, 0, 0, 430, h_frame, 0.8)

    draw_hud_text(frame, "AI EXAM PROCTORING SYSTEM", (15, 35), HUD_CYAN, 0.7, 2)
    cv2.line(frame, (15, 48), (415, 48), HUD_CYAN, 1)

    y_offset = 80
    line_height = 40
    labels = [
        ("MODE", "EXAM PROCTORING", HUD_WHITE),
        ("STUDENT", student_name, HUD_WHITE),
        ("USN", student_usn, HUD_WHITE),
        ("TIMER", f"{minutes:02d}:{seconds:02d}", HUD_YELLOW),
        ("FACES", str(total_faces), HUD_GREEN),
        ("FOCUS", f"{engagement}%", HUD_YELLOW),
        ("RISK", risk_level, risk_color),
        ("MULTI-FACE", str(multiple_face_count), HUD_ORANGE),
        ("HEAD MOVES", str(head_movement_count), HUD_ORANGE),
    ]

    for lbl, val, clr in labels:
        draw_hud_text(frame, f"{lbl}", (20, y_offset), (120, 140, 160), 0.5)
        draw_hud_text(frame, f": {val}", (160, y_offset), clr, 0.55)
        y_offset += line_height

    # Risk meter bar
    draw_hud_text(frame, "RISK METER", (20, y_offset + 10), HUD_CYAN, 0.5)
    draw_risk_bar(frame, 20, y_offset + 20, 390, 20, suspicious_score, MAX_SUSPICIOUS)
    draw_hud_text(frame, f"{int(suspicious_score)}/{MAX_SUSPICIOUS}", (180, y_offset + 55), HUD_WHITE, 0.4)

    # Control hints
    cv2.rectangle(frame, (20, h_frame - 70), (170, h_frame - 30), HUD_GREEN, -1)
    cv2.putText(frame, "S = SAVE", (42, h_frame - 43), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.rectangle(frame, (190, h_frame - 70), (370, h_frame - 30), HUD_RED, -1)
    cv2.putText(frame, "ESC = EXIT", (207, h_frame - 43), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Warning banner (pulsing)
    if warning_timer > 0:
        warning_timer -= 1
        if int(time.time() * 3) % 2 == 0:
            draw_overlay_panel(frame, 450, 10, w_frame - 460, 50, 0.7)
            draw_hud_text(frame, f"WARNING: {warning_message}", (465, 42), HUD_RED, 0.7, 2)

    # ======================================================
    # SHOW WINDOW
    # ======================================================

    cv2.imshow("AI EXAM PROCTORING MODE", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        save_evidence(frame, "MANUAL_CAPTURE")
    elif key == 27:
        print("Exiting Exam Mode")
        break

# ==========================================================
# CLEAN EXIT
# ==========================================================

face_detector.close()
cap.release()
cv2.destroyAllWindows()
# ==========================================================
# CLASSROOM MODE — POLISHED HUD
# AI SMART CLASSROOM SURVEILLANCE SYSTEM
# WITH FACE RECOGNITION + DATABASE
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

# ==========================================================
# DATABASE IMPORTS
# ==========================================================

from database.attendance_db import save_student_attendance
from database.alerts_db import save_alert

# ==========================================================
# FACE RECOGNITION IMPORT
# ==========================================================

try:
    from ai.face_recognition_module import recognize_best_name
except Exception:
    def recognize_best_name(frame):
        return "UNKNOWN"

# ==========================================================
# CREATE FOLDERS
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "..")

for folder in ["logs", "alerts", "attendance", "teacher_attendance", "evidence"]:
    os.makedirs(os.path.join(PROJECT_DIR, folder), exist_ok=True)

# ==========================================================
# CAMERA
# ==========================================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("CAMERA NOT FOUND")
    exit()

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
# VARIABLES
# ==========================================================

teacher_name = "Dr Ravi"
lecture_start = time.time()
attendance_saved = set()
last_alert_time = 0
ALERT_COOLDOWN = 30  # seconds between alerts for same type

# ==========================================================
# HUD COLORS
# ==========================================================

HUD_GREEN = (0, 255, 150)
HUD_CYAN = (255, 212, 0)
HUD_RED = (60, 60, 255)
HUD_YELLOW = (0, 255, 255)
HUD_WHITE = (240, 240, 240)
HUD_PANEL_BG = (25, 20, 15)

# ==========================================================
# SAVE LOG
# ==========================================================

def save_log(message):
    log_path = os.path.join(PROJECT_DIR, "logs", "classroom_log.txt")
    with open(log_path, "a") as file:
        file.write(f"{datetime.now()} : {message}\n")

# ==========================================================
# HUD DRAWING HELPERS
# ==========================================================

def draw_overlay_panel(frame, x, y, w, h, alpha=0.7):
    """Draw semi-transparent dark panel"""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), HUD_PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), HUD_CYAN, 1)

def draw_corner_brackets(frame, x, y, w, h, color, length=15, thickness=2):
    """Draw corner bracket accents around a rectangle"""
    cv2.line(frame, (x, y), (x + length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + length), color, thickness)
    cv2.line(frame, (x + w, y), (x + w - length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + length), color, thickness)
    cv2.line(frame, (x, y + h), (x + length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - length), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w - length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - length), color, thickness)

def draw_hud_text(frame, text, pos, color=HUD_WHITE, scale=0.6, thickness=1):
    """Draw text with subtle shadow for readability"""
    x, y = pos
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

# ==========================================================
# MAIN LOOP
# ==========================================================

while True:
    success, frame = cap.read()
    if not success:
        print("FRAME ERROR")
        break

    h_frame, w_frame = frame.shape[:2]

    # ======================================================
    # FACE DETECTION (new API)
    # ======================================================

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    results = face_detector.detect(mp_image)

    student_count = 0

    for detection in results.detections:
        bbox = detection.bounding_box
        x = max(0, bbox.origin_x)
        y = max(0, bbox.origin_y)
        width = max(1, bbox.width)
        height = max(1, bbox.height)

        student_count += 1

        # ==================================================
        # FACE CROP + RECOGNITION
        # ==================================================

        face_crop = frame[y:y + height, x:x + width]

        try:
            detected_name = recognize_best_name(face_crop)
            if detected_name is None:
                detected_name = "UNKNOWN"
            else:
                detected_name = str(detected_name)
        except Exception as e:
            print(e)
            detected_name = "UNKNOWN"

        # ==================================================
        # DRAW FACE BOX — color-coded
        # ==================================================

        if detected_name != "UNKNOWN":
            box_color = HUD_GREEN
            draw_corner_brackets(frame, x, y, width, height, HUD_GREEN, 12, 2)
        else:
            box_color = HUD_RED
            draw_corner_brackets(frame, x, y, width, height, HUD_RED, 12, 2)

        # Semi-transparent face rectangle
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + width, y + height), box_color, 2)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        # Name tag with background
        label = detected_name
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x, y - th - 12), (x + tw + 8, y - 2), box_color, -1)
        cv2.putText(frame, label, (x + 4, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # ==================================================
        # SAVE ATTENDANCE
        # ==================================================

        if detected_name != "UNKNOWN":
            if detected_name not in attendance_saved:
                attendance_saved.add(detected_name)
                save_student_attendance(detected_name, "4VP22CS001", "CLASSROOM MODE")
                save_log(f"Attendance Saved : {detected_name}")
        else:
            # Alert with cooldown
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                save_alert("UNKNOWN PERSON", "HIGH", "CLASSROOM")
                last_alert_time = current_time

    # ======================================================
    # TIMER
    # ======================================================

    elapsed_time = int(time.time() - lecture_start)
    mins = elapsed_time // 60
    secs = elapsed_time % 60

    # ======================================================
    # HUD OVERLAY PANEL (top-left)
    # ======================================================

    draw_overlay_panel(frame, 8, 8, 350, 170, 0.75)

    draw_hud_text(frame, "SMART CLASSROOM ACTIVE", (18, 32), HUD_CYAN, 0.65, 2)
    cv2.line(frame, (18, 40), (340, 40), HUD_CYAN, 1)

    draw_hud_text(frame, f"TEACHER  :  {teacher_name}", (18, 65), HUD_WHITE, 0.55)
    draw_hud_text(frame, f"STUDENTS :  {student_count}", (18, 92), HUD_GREEN, 0.55)
    draw_hud_text(frame, f"LECTURE  :  {mins:02d}:{secs:02d}", (18, 119), HUD_YELLOW, 0.55)
    draw_hud_text(frame, f"SAVED    :  {len(attendance_saved)} attendance(s)", (18, 146), HUD_CYAN, 0.5)
    draw_hud_text(frame, datetime.now().strftime("%d-%m-%Y  %H:%M:%S"), (18, 168), (120, 120, 120), 0.4)

    # ======================================================
    # STATUS BAR (bottom)
    # ======================================================

    bar_y = h_frame - 35
    draw_overlay_panel(frame, 0, bar_y, w_frame, 35, 0.8)
    draw_hud_text(frame, "SMART VISION v3.0  |  CLASSROOM MODE  |  Press 'Q' to exit", (12, bar_y + 22), HUD_CYAN, 0.45)

    # Blinking record indicator
    if int(time.time()) % 2 == 0:
        cv2.circle(frame, (w_frame - 30, bar_y + 18), 6, (0, 0, 255), -1)
        draw_hud_text(frame, "REC", (w_frame - 65, bar_y + 23), HUD_RED, 0.4)

    # ======================================================
    # SHOW WINDOW
    # ======================================================

    cv2.imshow("SMART VISION CLASSROOM MODE", frame)

    key = cv2.waitKey(1)
    if key == ord("q"):
        break

# ==========================================================
# RELEASE
# ==========================================================

face_detector.close()
cap.release()
cv2.destroyAllWindows()
print("CLASSROOM MODE CLOSED")

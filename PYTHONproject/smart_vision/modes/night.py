# ==========================================================
# AI SMART NIGHT SECURITY MODE — POLISHED HUD
# (mediapipe tasks API)
# ==========================================================

import cv2
import mediapipe as mp
import numpy as np
import time
import os
import winsound
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

for folder in ["evidence", "logs", "recordings"]:
    os.makedirs(os.path.join(PROJECT_DIR, folder), exist_ok=True)

# ==========================================================
# CAMERA
# ==========================================================

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# ==========================================================
# BACKGROUND SUBTRACTOR
# ==========================================================

motion_detector = cv2.createBackgroundSubtractorMOG2()

# ==========================================================
# VIDEO RECORDING
# ==========================================================

fourcc = cv2.VideoWriter_fourcc(*'XVID')
recording = False
video_writer = None

# ==========================================================
# HUD COLORS
# ==========================================================

NV_GREEN = (0, 255, 80)
NV_GREEN_DIM = (0, 180, 50)
HUD_CYAN = (255, 212, 0)
HUD_RED = (60, 60, 255)
HUD_WHITE = (220, 220, 220)
HUD_PANEL_BG = (15, 20, 10)

# ==========================================================
# VARIABLES
# ==========================================================

last_alarm_time = 0
ALARM_COOLDOWN = 3
last_evidence_time = 0
EVIDENCE_COOLDOWN = 5
intruder_total_count = 0

# ==========================================================
# SAVE EVIDENCE (with cooldown)
# ==========================================================

def save_evidence(frame, tag):
    global last_evidence_time
    current = time.time()
    if current - last_evidence_time < EVIDENCE_COOLDOWN:
        return
    last_evidence_time = current
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    filename = os.path.join(PROJECT_DIR, "evidence", f"{tag}_{timestamp}.jpg")
    cv2.imwrite(filename, frame)
    print("Evidence Saved:", filename)

# ==========================================================
# START / STOP RECORDING
# ==========================================================

def start_recording(frame):
    global video_writer, recording
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    filename = os.path.join(PROJECT_DIR, "recordings", f"security_{timestamp}.avi")
    height, width, _ = frame.shape
    video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
    recording = True
    print("Recording Started")

def stop_recording():
    global recording, video_writer
    if video_writer:
        video_writer.release()
    recording = False
    print("Recording Stopped")

# ==========================================================
# ALARM (with cooldown)
# ==========================================================

def trigger_alarm():
    global last_alarm_time
    current = time.time()
    if current - last_alarm_time < ALARM_COOLDOWN:
        return
    last_alarm_time = current
    winsound.Beep(1000, 700)

def suspicious_sound_detected():
    print("Suspicious Sound Detected!")
    winsound.Beep(1500, 1000)

# ==========================================================
# RISK SCORE
# ==========================================================

def calculate_risk(area):
    if area > 20000:
        return "HIGH RISK", HUD_RED
    elif area > 10000:
        return "MEDIUM RISK", (0, 180, 255)
    else:
        return "LOW RISK", NV_GREEN

# ==========================================================
# HUD DRAWING HELPERS
# ==========================================================

def draw_overlay_panel(frame, x, y, w, h, alpha=0.7):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), HUD_PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), NV_GREEN_DIM, 1)

def draw_hud_text(frame, text, pos, color=HUD_WHITE, scale=0.5, thickness=1):
    x, y = pos
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

def draw_corner_brackets(frame, x, y, w, h, color, length=12, thickness=2):
    cv2.line(frame, (x, y), (x + length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + length), color, thickness)
    cv2.line(frame, (x + w, y), (x + w - length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + length), color, thickness)
    cv2.line(frame, (x, y + h), (x + length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - length), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w - length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - length), color, thickness)

# ==========================================================
# NIGHT LOOP
# ==========================================================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h_frame, w_frame = frame.shape[:2]

    # ======================================================
    # NIGHT VISION GREEN TINT
    # ======================================================

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    nv_frame = np.zeros_like(frame)
    nv_frame[:, :, 1] = gray
    nv_frame[:, :, 0] = (gray * 0.15).astype(np.uint8)
    nv_frame[:, :, 2] = (gray * 0.05).astype(np.uint8)

    frame = cv2.addWeighted(frame, 0.3, nv_frame, 0.7, 0)

    # ======================================================
    # RESTRICTED ZONE
    # ======================================================

    zone_x1, zone_y1 = 100, 100
    zone_x2, zone_y2 = 500, 400

    draw_corner_brackets(frame, zone_x1, zone_y1, zone_x2 - zone_x1, zone_y2 - zone_y1, HUD_RED, 20, 2)
    draw_hud_text(frame, "RESTRICTED ZONE", (zone_x1 + 10, zone_y1 - 10), HUD_RED, 0.6, 2)

    # ======================================================
    # MOTION DETECTION
    # ======================================================

    mask = motion_detector.apply(gray)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    intruder_detected = False
    motion_count = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 5000:
            intruder_detected = True
            motion_count += 1
            x, y, w, h = cv2.boundingRect(contour)

            draw_corner_brackets(frame, x, y, w, h, NV_GREEN, 10, 2)

            overlay = frame.copy()
            cv2.rectangle(overlay, (x, y), (x + w, y + h), NV_GREEN, -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

            risk, risk_color = calculate_risk(area)
            draw_hud_text(frame, risk, (x, y - 10), risk_color, 0.6, 2)

            center_x = x + w // 2
            center_y = y + h // 2

            if zone_x1 < center_x < zone_x2 and zone_y1 < center_y < zone_y2:
                intruder_total_count += 1
                trigger_alarm()
                save_evidence(frame, "INTRUDER")

                if int(time.time() * 4) % 2 == 0:
                    draw_overlay_panel(frame, w_frame // 2 - 150, 10, 300, 45, 0.8)
                    draw_hud_text(frame, "!! INTRUDER ALERT !!", (w_frame // 2 - 130, 40), HUD_RED, 0.8, 2)

                if not recording:
                    start_recording(frame)

    # ======================================================
    # FACE RECOGNITION DISPLAY
    # ======================================================

    try:
        people = detect_face(frame)
        if isinstance(people, list):
            for person in people:
                name, fx, fy, fw, fh = person
                box_color = NV_GREEN if name != "UNKNOWN" else HUD_RED
                draw_corner_brackets(frame, fx, fy, fw, fh, box_color, 8, 1)
                draw_hud_text(frame, name, (fx, fy - 10), box_color, 0.5)
    except Exception:
        pass

    # Record video
    if recording and video_writer:
        video_writer.write(frame)

    # ======================================================
    # HUD OVERLAY PANEL (top-left)
    # ======================================================

    draw_overlay_panel(frame, 5, 5, 260, 140, 0.75)

    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%d-%m-%Y")

    draw_hud_text(frame, "NIGHT SECURITY MODE", (12, 25), NV_GREEN, 0.55, 2)
    cv2.line(frame, (12, 32), (250, 32), NV_GREEN_DIM, 1)

    draw_hud_text(frame, f"TIME  : {current_time}", (12, 55), NV_GREEN, 0.45)
    draw_hud_text(frame, f"DATE  : {current_date}", (12, 78), NV_GREEN, 0.45)
    draw_hud_text(frame, f"MOTION: {motion_count} zone(s)", (12, 101), NV_GREEN if motion_count == 0 else HUD_RED, 0.45)
    draw_hud_text(frame, f"ALERTS: {intruder_total_count}", (12, 124), HUD_RED if intruder_total_count > 0 else NV_GREEN, 0.45)

    # Blinking NV dot
    if int(time.time()) % 2 == 0:
        cv2.circle(frame, (w_frame - 20, 20), 6, NV_GREEN, -1)
    draw_hud_text(frame, "NV ACTIVE", (w_frame - 100, 25), NV_GREEN_DIM, 0.4)

    if recording:
        if int(time.time() * 2) % 2 == 0:
            cv2.circle(frame, (w_frame - 20, 45), 5, HUD_RED, -1)
            draw_hud_text(frame, "REC", (w_frame - 60, 50), HUD_RED, 0.4)

    # Bottom status bar
    bar_y = h_frame - 30
    draw_overlay_panel(frame, 0, bar_y, w_frame, 30, 0.8)
    draw_hud_text(frame, "SMART VISION v3.0  |  NIGHT MODE  |  Q=Exit  S=Screenshot  A=Alarm Test", (8, bar_y + 20), NV_GREEN_DIM, 0.4)

    # ======================================================
    # SHOW FRAME
    # ======================================================

    cv2.imshow("AI NIGHT SECURITY MODE", frame)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('s'):
        save_evidence(frame, "MANUAL")
    elif key == ord('a'):
        suspicious_sound_detected()

# ==========================================================
# CLEAN EXIT
# ==========================================================

stop_recording()
cap.release()
cv2.destroyAllWindows()
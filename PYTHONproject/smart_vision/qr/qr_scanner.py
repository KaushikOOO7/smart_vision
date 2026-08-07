# ==========================================================
# QR CODE SCANNER — POLISHED HUD
# SMART CLASSROOM LOGIN
# ==========================================================

import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import time

# ==========================================================
# HUD COLORS
# ==========================================================

HUD_CYAN = (255, 212, 0)
HUD_GREEN = (0, 255, 150)
HUD_RED = (60, 60, 255)
HUD_WHITE = (240, 240, 240)
HUD_PANEL_BG = (20, 18, 14)

# ==========================================================
# VARIABLES
# ==========================================================

scan_line_y = 0
scan_direction = 1
last_scan_data = ""
success_flash_timer = 0

# ==========================================================
# HUD HELPERS
# ==========================================================

def draw_overlay_panel(frame, x, y, w, h, alpha=0.7):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), HUD_PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), HUD_CYAN, 1)

def draw_hud_text(frame, text, pos, color=HUD_WHITE, scale=0.55, thickness=1):
    x, y = pos
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

def draw_scan_frame(frame, cx, cy, size, color):
    """Draw corner bracket scan guide"""
    half = size // 2
    length = 30
    thickness = 3
    x1, y1 = cx - half, cy - half
    x2, y2 = cx + half, cy + half

    # Corners
    cv2.line(frame, (x1, y1), (x1 + length, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + length), color, thickness)
    cv2.line(frame, (x2, y1), (x2 - length, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + length), color, thickness)
    cv2.line(frame, (x1, y2), (x1 + length, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - length), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - length, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - length), color, thickness)

# ==========================================================
# CAMERA
# ==========================================================

cap = cv2.VideoCapture(0)

# ==========================================================
# QR SCAN LOOP
# ==========================================================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h_frame, w_frame = frame.shape[:2]
    cx, cy = w_frame // 2, h_frame // 2

    # ======================================================
    # SCAN FRAME GUIDE (center)
    # ======================================================

    guide_size = min(w_frame, h_frame) // 2
    guide_color = HUD_CYAN if success_flash_timer <= 0 else HUD_GREEN
    draw_scan_frame(frame, cx, cy, guide_size, guide_color)

    # ======================================================
    # ANIMATED SCAN LINE
    # ======================================================

    scan_line_y += scan_direction * 3
    scan_top = cy - guide_size // 2
    scan_bot = cy + guide_size // 2

    if scan_line_y > scan_bot:
        scan_direction = -1
    elif scan_line_y < scan_top:
        scan_direction = 1

    # Keep in bounds
    scan_line_y = max(scan_top, min(scan_bot, scan_line_y))

    # Draw scan line with gradient fade
    overlay = frame.copy()
    cv2.line(overlay, (cx - guide_size // 2 + 5, scan_line_y),
             (cx + guide_size // 2 - 5, scan_line_y), HUD_CYAN, 2)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # ======================================================
    # SUCCESS FLASH EFFECT
    # ======================================================

    if success_flash_timer > 0:
        success_flash_timer -= 1
        flash_alpha = 0.15 * (success_flash_timer / 30)
        flash_overlay = frame.copy()
        flash_overlay[:] = (0, 255, 100)
        cv2.addWeighted(flash_overlay, flash_alpha, frame, 1 - flash_alpha, 0, frame)

    # ======================================================
    # DETECT QR
    # ======================================================

    qr_codes = decode(frame)

    for qr in qr_codes:
        data = qr.data.decode("utf-8")

        if data != last_scan_data:
            last_scan_data = data
            success_flash_timer = 30
            print("\n========== QR DETECTED ==========")
            print(data)
            print("Login Time:", datetime.now())

        # Draw QR bounding box
        points = qr.polygon
        if len(points) == 4:
            pts = [(point.x, point.y) for point in points]
            for i in range(4):
                cv2.line(frame, pts[i], pts[(i + 1) % 4], HUD_GREEN, 3)

        # Success overlay
        draw_overlay_panel(frame, cx - 160, cy - guide_size // 2 - 60, 320, 50, 0.8)
        draw_hud_text(frame, "LECTURER VERIFIED", (cx - 120, cy - guide_size // 2 - 30), HUD_GREEN, 0.75, 2)

        # Data display
        draw_overlay_panel(frame, 10, h_frame - 90, w_frame - 20, 80, 0.8)
        draw_hud_text(frame, "SCANNED DATA:", (20, h_frame - 65), HUD_CYAN, 0.5)
        draw_hud_text(frame, data[:60], (20, h_frame - 38), HUD_GREEN, 0.55)
        draw_hud_text(frame, datetime.now().strftime("Login: %d-%m-%Y  %H:%M:%S"), (20, h_frame - 15), (150, 150, 150), 0.4)

    # ======================================================
    # HUD TOP OVERLAY
    # ======================================================

    draw_overlay_panel(frame, 5, 5, 250, 65, 0.75)
    draw_hud_text(frame, "QR SCANNER ACTIVE", (12, 28), HUD_CYAN, 0.55, 2)
    draw_hud_text(frame, datetime.now().strftime("%H:%M:%S"), (12, 55), (150, 150, 150), 0.45)

    if not qr_codes:
        draw_hud_text(frame, "Waiting for QR code...", (cx - 100, cy + guide_size // 2 + 30), HUD_CYAN, 0.5)

    # ======================================================
    # BOTTOM BAR
    # ======================================================

    draw_overlay_panel(frame, 0, h_frame - 25, w_frame, 25, 0.8)
    draw_hud_text(frame, "SMART VISION v3.0  |  QR LOGIN  |  Press 'Q' to exit", (8, h_frame - 8), (100, 120, 100), 0.4)

    # ======================================================
    # SHOW WINDOW
    # ======================================================

    cv2.imshow("QR SCANNER", frame)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break

# ==========================================================
# CLEAN EXIT
# ==========================================================

cap.release()
cv2.destroyAllWindows()
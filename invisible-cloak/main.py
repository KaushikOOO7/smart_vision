import cv2
import numpy as np
import time

# ============================================================
#           INVISIBLE CLOAK - COMPUTER VISION
# ============================================================

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

CAMERA_INDEX = 0

FRAME_WIDTH = 960
FRAME_HEIGHT = 540

# Number of frames used for creating a stable background
BACKGROUND_FRAMES = 60

# ------------------------------------------------------------
# RED CLOAK HSV RANGE
# ------------------------------------------------------------
# Red occurs at both ends of OpenCV's HSV Hue range.

LOWER_RED_1 = np.array([0, 100, 70], dtype=np.uint8)
UPPER_RED_1 = np.array([10, 255, 255], dtype=np.uint8)

LOWER_RED_2 = np.array([170, 100, 70], dtype=np.uint8)
UPPER_RED_2 = np.array([180, 255, 255], dtype=np.uint8)

# Kernel used for removing noise from mask
KERNEL = np.ones((5, 5), np.uint8)


# ============================================================
# FUNCTION: RESIZE FRAME
# ============================================================

def prepare_frame(frame):
    """
    Flips the webcam image and resizes it to a fixed resolution.
    This guarantees that background, live frame and mask
    always have the same dimensions.
    """

    frame = cv2.flip(frame, 1)

    frame = cv2.resize(
        frame,
        (FRAME_WIDTH, FRAME_HEIGHT)
    )

    return frame


# ============================================================
# FUNCTION: CAPTURE BACKGROUND
# ============================================================

def capture_background(cap):
    """
    Captures multiple frames of the empty scene and calculates
    their median to obtain a clean and stable background.
    """

    print()
    print("=" * 60)
    print("BACKGROUND CAPTURE")
    print("=" * 60)
    print()
    print("Move completely OUT of the camera view.")
    print("Keep the camera stationary.")
    print()

    background_frames = []

    for i in range(BACKGROUND_FRAMES):

        ret, frame = cap.read()

        if not ret:
            print("ERROR: Could not read frame.")
            continue

        # IMPORTANT:
        # Resize BEFORE saving the background frame
        frame = prepare_frame(frame)

        background_frames.append(frame.copy())

        # Calculate progress
        progress = int(
            ((i + 1) / BACKGROUND_FRAMES) * 100
        )

        display = frame.copy()

        # Dark information panel
        cv2.rectangle(
            display,
            (15, 15),
            (500, 125),
            (20, 20, 20),
            -1
        )

        cv2.putText(
            display,
            "CAPTURING BACKGROUND",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2
        )

        cv2.putText(
            display,
            "Please stay OUT of camera view",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1
        )

        cv2.putText(
            display,
            f"Progress: {progress}%",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        cv2.imshow(
            "Invisible Cloak",
            display
        )

        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            return None


    # --------------------------------------------------------
    # Check if background frames were captured
    # --------------------------------------------------------

    if len(background_frames) == 0:

        print("ERROR: Background capture failed.")

        return None


    print()
    print("Processing background...")


    # --------------------------------------------------------
    # Calculate median background
    # --------------------------------------------------------

    background = np.median(
        np.array(background_frames),
        axis=0
    ).astype(np.uint8)


    # --------------------------------------------------------
    # FINAL SAFETY RESIZE
    # --------------------------------------------------------

    background = cv2.resize(
        background,
        (FRAME_WIDTH, FRAME_HEIGHT)
    )


    print("Background captured successfully!")
    print()

    return background


# ============================================================
# FUNCTION: CREATE CLOAK MASK
# ============================================================

def create_cloak_mask(frame):
    """
    Detects red-colored cloak from the current webcam frame.
    """

    # --------------------------------------------------------
    # Convert BGR image to HSV
    # --------------------------------------------------------

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )


    # --------------------------------------------------------
    # Detect first red range
    # --------------------------------------------------------

    mask1 = cv2.inRange(
        hsv,
        LOWER_RED_1,
        UPPER_RED_1
    )


    # --------------------------------------------------------
    # Detect second red range
    # --------------------------------------------------------

    mask2 = cv2.inRange(
        hsv,
        LOWER_RED_2,
        UPPER_RED_2
    )


    # --------------------------------------------------------
    # Combine masks
    # --------------------------------------------------------

    mask = cv2.bitwise_or(
        mask1,
        mask2
    )


    # ========================================================
    # MASK CLEANING
    # ========================================================

    # Remove small white noise
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        KERNEL
    )


    # Fill small black holes
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        KERNEL
    )


    # Expand detected cloak slightly
    mask = cv2.dilate(
        mask,
        KERNEL,
        iterations=1
    )


    # Smooth cloak edges
    mask = cv2.GaussianBlur(
        mask,
        (7, 7),
        0
    )


    # Ensure correct OpenCV mask datatype
    mask = mask.astype(np.uint8)

    return mask


# ============================================================
# FUNCTION: CREATE INVISIBILITY EFFECT
# ============================================================

def create_invisible_effect(
        frame,
        background,
        mask
):

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    # Ensure background and frame are same size
    if background.shape[:2] != frame.shape[:2]:

        background = cv2.resize(
            background,
            (
                frame.shape[1],
                frame.shape[0]
            )
        )


    # Ensure mask and frame are same size
    if mask.shape[:2] != frame.shape[:2]:

        mask = cv2.resize(
            mask,
            (
                frame.shape[1],
                frame.shape[0]
            ),
            interpolation=cv2.INTER_NEAREST
        )


    # Ensure mask datatype is uint8
    if mask.dtype != np.uint8:

        mask = mask.astype(
            np.uint8
        )


    # ========================================================
    # CREATE INVERSE MASK
    # ========================================================

    inverse_mask = cv2.bitwise_not(
        mask
    )


    # ========================================================
    # BACKGROUND PART
    # ========================================================
    # Wherever cloak exists, take pixels from background.

    background_part = cv2.bitwise_and(
        background,
        background,
        mask=mask
    )


    # ========================================================
    # FOREGROUND PART
    # ========================================================
    # Keep normal webcam image everywhere except cloak.

    foreground_part = cv2.bitwise_and(
        frame,
        frame,
        mask=inverse_mask
    )


    # ========================================================
    # COMBINE BOTH
    # ========================================================

    result = cv2.add(
        background_part,
        foreground_part
    )

    return result


# ============================================================
# FUNCTION: DRAW HIGH-TECH HUD
# ============================================================

def draw_hud(
        result,
        fps,
        cloak_percentage
):

    # --------------------------------------------------------
    # Cloak detection status
    # --------------------------------------------------------

    if cloak_percentage > 1:

        status = "CLOAK DETECTED"

        status_color = (
            0,
            255,
            0
        )

    else:

        status = "SEARCHING..."

        status_color = (
            0,
            165,
            255
        )


    # --------------------------------------------------------
    # Dark HUD panel
    # --------------------------------------------------------

    overlay = result.copy()

    cv2.rectangle(
        overlay,
        (15, 15),
        (420, 170),
        (15, 15, 15),
        -1
    )


    # Transparent HUD
    result = cv2.addWeighted(
        overlay,
        0.75,
        result,
        0.25,
        0
    )


    # --------------------------------------------------------
    # Project title
    # --------------------------------------------------------

    cv2.putText(
        result,
        "INVISIBLE CLOAK AI",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2
    )


    # --------------------------------------------------------
    # System status
    # --------------------------------------------------------

    cv2.putText(
        result,
        "SYSTEM : ONLINE",
        (30, 82),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0),
        2
    )


    # --------------------------------------------------------
    # Cloak status
    # --------------------------------------------------------

    cv2.putText(
        result,
        f"CLOAK  : {status}",
        (30, 108),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        status_color,
        2
    )


    # --------------------------------------------------------
    # FPS
    # --------------------------------------------------------

    cv2.putText(
        result,
        f"FPS    : {fps:.1f}",
        (30, 134),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1
    )


    # --------------------------------------------------------
    # Cloak area
    # --------------------------------------------------------

    cv2.putText(
        result,
        f"AREA   : {cloak_percentage:.2f}%",
        (30, 158),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1
    )


    # --------------------------------------------------------
    # Controls
    # --------------------------------------------------------

    cv2.putText(
        result,
        "Q:QUIT   B:BACKGROUND   M:MASK",
        (20, FRAME_HEIGHT - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
    )


    return result


# ============================================================
# START CAMERA
# ============================================================

print()
print("=" * 60)
print("        INVISIBLE CLOAK AI")
print("        COMPUTER VISION PROJECT")
print("=" * 60)
print()

print("Starting webcam...")


cap = cv2.VideoCapture(
    CAMERA_INDEX
)


# ============================================================
# CHECK CAMERA
# ============================================================

if not cap.isOpened():

    print()
    print("ERROR: Cannot access webcam.")
    print()
    print("Try:")
    print("1. Close Camera/Zoom/Meet applications.")
    print("2. Allow camera permission.")
    print("3. Change CAMERA_INDEX = 0 to 1.")

    exit()


# ============================================================
# CAMERA SETTINGS
# ============================================================

cap.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    FRAME_WIDTH
)

cap.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    FRAME_HEIGHT
)


# ============================================================
# WARM UP CAMERA
# ============================================================

print("Warming up camera...")

for i in range(30):

    ret, frame = cap.read()

    if not ret:
        continue

    cv2.waitKey(10)


# ============================================================
# CAPTURE INITIAL BACKGROUND
# ============================================================

background = capture_background(
    cap
)


if background is None:

    cap.release()

    cv2.destroyAllWindows()

    print("Program stopped.")

    exit()


# ============================================================
# INSTRUCTIONS
# ============================================================

print()
print("=" * 60)
print("INVISIBLE CLOAK READY")
print("=" * 60)

print()
print("Now enter the camera view with your RED cloak.")
print()

print("CONTROLS")
print("-" * 30)
print("Q = Quit")
print("B = Recapture Background")
print("M = Show/Hide Mask")
print()


# ============================================================
# VARIABLES
# ============================================================

previous_time = time.time()

fps = 0

show_mask = False


# ============================================================
# MAIN REAL-TIME LOOP
# ============================================================

while True:

    # --------------------------------------------------------
    # READ CAMERA
    # --------------------------------------------------------

    ret, frame = cap.read()

    if not ret:

        print("ERROR: Could not read webcam frame.")

        break


    # --------------------------------------------------------
    # PREPARE FRAME
    # --------------------------------------------------------

    frame = prepare_frame(
        frame
    )


    # --------------------------------------------------------
    # CREATE CLOAK MASK
    # --------------------------------------------------------

    mask = create_cloak_mask(
        frame
    )


    # ========================================================
    # FINAL SIZE SAFETY
    # ========================================================

    if background.shape[:2] != frame.shape[:2]:

        background = cv2.resize(
            background,
            (
                frame.shape[1],
                frame.shape[0]
            )
        )


    if mask.shape[:2] != frame.shape[:2]:

        mask = cv2.resize(
            mask,
            (
                frame.shape[1],
                frame.shape[0]
            ),
            interpolation=cv2.INTER_NEAREST
        )


    # ========================================================
    # INVISIBLE EFFECT
    # ========================================================

    result = create_invisible_effect(
        frame,
        background,
        mask
    )


    # ========================================================
    # CALCULATE FPS
    # ========================================================

    current_time = time.time()

    elapsed_time = (
        current_time -
        previous_time
    )

    if elapsed_time > 0:

        current_fps = (
            1 / elapsed_time
        )

        # Smooth FPS reading
        fps = (
            fps * 0.9 +
            current_fps * 0.1
        )

    previous_time = current_time


    # ========================================================
    # CALCULATE CLOAK AREA
    # ========================================================

    cloak_pixels = cv2.countNonZero(
        mask
    )

    total_pixels = (
        mask.shape[0] *
        mask.shape[1]
    )

    cloak_percentage = (
        cloak_pixels /
        total_pixels
    ) * 100


    # ========================================================
    # DRAW HUD
    # ========================================================

    result = draw_hud(
        result,
        fps,
        cloak_percentage
    )


    # ========================================================
    # DISPLAY MAIN WINDOW
    # ========================================================

    cv2.imshow(
        "Invisible Cloak",
        result
    )


    # ========================================================
    # DISPLAY MASK
    # ========================================================

    if show_mask:

        cv2.imshow(
            "Cloak Detection Mask",
            mask
        )


    # ========================================================
    # KEYBOARD INPUT
    # ========================================================

    key = cv2.waitKey(1) & 0xFF


    # ========================================================
    # Q → QUIT
    # ========================================================

    if key == ord("q"):

        print()
        print("Stopping Invisible Cloak...")

        break


    # ========================================================
    # M → MASK
    # ========================================================

    elif key == ord("m"):

        show_mask = not show_mask

        if not show_mask:

            try:

                cv2.destroyWindow(
                    "Cloak Detection Mask"
                )

            except cv2.error:

                pass


    # ========================================================
    # B → RECAPTURE BACKGROUND
    # ========================================================

    elif key == ord("b"):

        print()
        print("BACKGROUND RECALIBRATION")
        print()
        print("Move OUT of the camera view.")

        new_background = capture_background(
            cap
        )

        if new_background is not None:

            # Safety resize
            new_background = cv2.resize(
                new_background,
                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )
            )

            background = new_background

            print()
            print("New background activated!")


# ============================================================
# CLEANUP
# ============================================================

cap.release()

cv2.destroyAllWindows()


# ============================================================
# END MESSAGE
# ============================================================

print()
print("=" * 60)
print("INVISIBLE CLOAK AI STOPPED")
print("=" * 60)
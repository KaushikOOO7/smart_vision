import os

import cv2
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUDENT_FACE_DIR = os.path.join(BASE_DIR, "faces", "students")
LECTURER_FACE_DIR = os.path.join(BASE_DIR, "faces", "lecturers")

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

recognizer = None
label_map = {}
trained = False


def _create_recognizer():
    try:
        return cv2.face.LBPHFaceRecognizer_create()
    except AttributeError:
        print("OpenCV face recognizer is unavailable. Install opencv-contrib-python for recognition.")
        return None


def _iter_face_images():
    for folder in (STUDENT_FACE_DIR, LECTURER_FACE_DIR):
        if not os.path.isdir(folder):
            continue

        for file_name in os.listdir(folder):
            if not file_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                continue

            yield os.path.join(folder, file_name), os.path.splitext(file_name)[0]


def _train_recognizer():
    global recognizer, trained

    recognizer = _create_recognizer()
    if recognizer is None or face_detector.empty():
        return

    faces = []
    ids = []
    current_id = 0

    for path, name in _iter_face_images():
        gray_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if gray_img is None:
            continue

        detections = face_detector.detectMultiScale(gray_img, 1.3, 5)
        if len(detections) == 0:
            continue

        label_map[current_id] = name
        for x, y, w, h in detections:
            faces.append(gray_img[y : y + h, x : x + w])
            ids.append(current_id)
        current_id += 1

    if not faces:
        print("No usable training faces found. Recognition will return UNKNOWN.")
        return

    recognizer.train(faces, np.array(ids))
    trained = True


def detect_face(frame):
    if frame is None or frame.size == 0 or not trained or recognizer is None:
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = face_detector.detectMultiScale(gray, 1.3, 5)
    people = []

    for x, y, w, h in detections:
        label_id, confidence = recognizer.predict(gray[y : y + h, x : x + w])
        name = label_map.get(label_id, "UNKNOWN") if confidence < 70 else "UNKNOWN"
        people.append((name, x, y, w, h))

    return people


def recognize_best_name(frame):
    people = detect_face(frame)
    if not people:
        return "UNKNOWN"
    return people[0][0] or "UNKNOWN"


_train_recognizer()

# =========================================================
# ATTENDANCE DATABASE MODULE
# SMART VISION PROJECT
# =========================================================

from database.database import db, cursor

from datetime import datetime


# =========================================================
# SAVE TEACHER ATTENDANCE
# =========================================================

def save_teacher_attendance(

    teacher_name,

    subject_name
):

    try:

        query = """
        INSERT INTO teacher_attendance

        (
            teacher_name,
            subject_name,
            attendance_date,
            attendance_time
        )

        VALUES (%s,%s,%s,%s)
        """

        now = datetime.now()

        values = (

            teacher_name,

            subject_name,

            now.date(),

            now.time()
        )

        cursor.execute(query, values)

        db.commit()

        print("TEACHER ATTENDANCE SAVED")


    except Exception as e:

        print("DATABASE ERROR:", e)



# =========================================================
# SAVE STUDENT ATTENDANCE
# =========================================================

def save_student_attendance(

    student_name,

    usn,

    mode_name
):

    try:

        query = """
        INSERT INTO student_attendance

        (
            student_name,
            usn,
            mode_name,
            attendance_date,
            attendance_time
        )

        VALUES (%s,%s,%s,%s,%s)
        """

        now = datetime.now()

        values = (

            student_name,

            usn,

            mode_name,

            now.date(),

            now.time()
        )

        cursor.execute(query, values)

        db.commit()

        print("STUDENT ATTENDANCE SAVED")


    except Exception as e:

        print("DATABASE ERROR:", e)



# =========================================================
# SAVE QR LOGIN
# =========================================================

def save_qr_login(

    teacher_name,

    teacher_id,

    subject_name
):

    try:

        query = """
        INSERT INTO qr_login_logs

        (
            teacher_name,
            teacher_id,
            subject_name,
            login_time
        )

        VALUES (%s,%s,%s,%s)
        """

        values = (

            teacher_name,

            teacher_id,

            subject_name,

            datetime.now()
        )

        cursor.execute(query, values)

        db.commit()

        print("QR LOGIN SAVED")


    except Exception as e:

        print("DATABASE ERROR:", e)



# =========================================================
# SAVE CLASSROOM STATUS
# =========================================================

def save_classroom_status(

    classroom_name,

    current_subject,

    lecturer_name,

    status_value
):

    try:

        query = """
        INSERT INTO classroom_status

        (
            classroom_name,
            current_subject,
            lecturer_name,
            status_value,
            timestamp_value
        )

        VALUES (%s,%s,%s,%s,%s)
        """

        values = (

            classroom_name,

            current_subject,

            lecturer_name,

            status_value,

            datetime.now()
        )

        cursor.execute(query, values)

        db.commit()

        print("CLASSROOM STATUS SAVED")


    except Exception as e:

        print("DATABASE ERROR:", e)
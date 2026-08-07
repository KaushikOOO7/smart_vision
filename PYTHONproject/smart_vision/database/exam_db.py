from database.database import db, cursor

from datetime import datetime

def save_exam_event(

    student_name,

    malpractice,

    risk_level
):

    query = """
    INSERT INTO exam_reports

    (
        student_name,
        malpractice,
        risk_level,
        timestamp_value
    )

    VALUES (%s,%s,%s,%s)
    """

    values = (

        student_name,

        malpractice,

        risk_level,

        datetime.now()
    )

    cursor.execute(query, values)

    db.commit()

    print("EXAM EVENT SAVED")
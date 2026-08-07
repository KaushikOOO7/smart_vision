from database.database import db, cursor

from datetime import datetime

def save_night_event(

    event_name,

    risk_level,

    location_name
):

    query = """
    INSERT INTO night_security

    (
        event_name,
        risk_level,
        location_name,
        timestamp_value
    )

    VALUES (%s,%s,%s,%s)
    """

    values = (

        event_name,

        risk_level,

        location_name,

        datetime.now()
    )

    cursor.execute(query, values)

    db.commit()

    print("NIGHT EVENT SAVED")
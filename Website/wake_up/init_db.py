"""
DATABASE INITIALIZATION SCRIPT
------------------------------
Run this once on Heroku to set up the tables:
'heroku run python init_db.py'
"""
import os
import psycopg2

def initialize_database():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    print("[DB] Resetting tables...")
    cur.execute("DROP TABLE IF EXISTS drive_logs CASCADE;")
    cur.execute("DROP TABLE IF EXISTS drives CASCADE;")

    # Main sessions table
    cur.execute("""
        CREATE TABLE drives (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR(50),
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            total_alerts INTEGER DEFAULT 0,
            video_url TEXT
        );
    """)

    # Telemetry data table
    cur.execute("""
        CREATE TABLE drive_logs (
            id SERIAL PRIMARY KEY,
            drive_id INTEGER REFERENCES drives(id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ear_value FLOAT,
            mar_value FLOAT,
            perclos_score FLOAT,
            is_distracted BOOLEAN,
            head_yaw FLOAT,
            head_pitch FLOAT,
            head_roll FLOAT
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Schema initialized successfully.")

if __name__ == "__main__":
    initialize_database()
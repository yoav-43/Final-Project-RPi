"""
DATABASE INITIALIZATION SCRIPT
Resets the Postgres schema for a clean deployment.
"""
import os
import psycopg2

def init():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    
    print("[DB] Dropping old tables...")
    cur.execute("DROP TABLE IF EXISTS drive_logs CASCADE;")
    cur.execute("DROP TABLE IF EXISTS drives CASCADE;")

    # Table 1: High-level Session Data
    print("[DB] Creating 'drives' table...")
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

    # Table 2: Detailed Telemetry for Analytics
    print("[DB] Creating 'drive_logs' table...")
    cur.execute("""
        CREATE TABLE drive_logs (
            id SERIAL PRIMARY KEY,
            drive_id INTEGER REFERENCES drives(id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ear_value FLOAT,
            perclos_score FLOAT,
            is_distracted BOOLEAN,
            head_yaw FLOAT,
            head_pitch FLOAT
        );
    """)

    conn.commit()
    cur.close(); conn.close()
    print("[SUCCESS] Database Initialized Successfully!")

if __name__ == "__main__":
    init()
import os
import psycopg2

def init():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')
    cur = conn.cursor()
    
    print("Refreshing Database Schema...")
    cur.execute("DROP TABLE IF EXISTS drive_logs CASCADE;")
    cur.execute("DROP TABLE IF EXISTS drives CASCADE;")

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
    print("Database Ready!")

if __name__ == "__main__":
    init()
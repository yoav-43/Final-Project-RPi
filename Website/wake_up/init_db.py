import os
import psycopg2

def initialize_database():
    """
    Initializes the PostgreSQL database schema for the Fleet Management System.
    Creates two related tables:
    1. 'drives': Stores metadata for each driving session (including video links).
    2. 'drive_logs': Stores high-frequency telemetry data linked to a specific drive.
    """
    # Retrieve database URL from environment variables (Heroku)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Ensure the Postgres addon is provisioned.")

    print("[DB] Connecting to PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    # Drop existing tables to ensure a clean schema update
    print("[DB] Dropping old tables (if exist)...")
    cur.execute("DROP TABLE IF EXISTS drive_logs CASCADE;")
    cur.execute("DROP TABLE IF EXISTS drives CASCADE;")

    # Table 1: Drive Sessions
    # Added 'video_url' to store the Cloudinary link
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

    # Table 2: Telemetry Logs
    # This table stores the granular data for the graphs
    print("[DB] Creating 'drive_logs' table...")
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
    print("[DB] Initialization complete. Database is ready.")

if __name__ == "__main__":
    initialize_database()
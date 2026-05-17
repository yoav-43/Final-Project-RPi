"""
WakeUp — Database Initialisation Script
========================================
Drops and recreates the PostgreSQL schema for a clean deployment.
Run once on first deploy, or whenever a full schema reset is required.

Usage:
    heroku run python init_db.py
"""
import os
import psycopg2

def init():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    
    # Drop existing tables in reverse dependency order to respect foreign key constraints.
    print("[DB] Dropping old tables...")
    cur.execute("DROP TABLE IF EXISTS drive_logs CASCADE;")
    cur.execute("DROP TABLE IF EXISTS drives CASCADE;")

    # drives: one row per drive session, holds high-level session metadata.
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

    # drive_logs: one row per telemetry sample (~1 Hz), holds granular metrics
    # used to render the Chart.js time-series charts on the analytics dashboard.
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
            head_pitch FLOAT,
            latitude FLOAT,
            longitude FLOAT
        );
    """)

    conn.commit()
    cur.close(); conn.close()
    print("[SUCCESS] Database Initialized Successfully!")

if __name__ == "__main__":
    init()

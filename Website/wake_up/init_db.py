import os
import psycopg2

def initialize_database():
    """
    Connects to the PostgreSQL database and creates the 'drive_logs' table.
    This version includes columns for all 3 Head Pose angles (Yaw, Pitch, Roll)
    to support the advanced dashboard analytics.
    """
    # 1. Get Database URL from Environment Variables
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Ensure the Postgres addon is provisioned.")

    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    # 2. Clean up old tables to ensure schema consistency
    print("Dropping old tables if they exist...")
    cur.execute("DROP TABLE IF EXISTS drive_logs;")

    # 3. Create the new table with full telemetry columns
    print("Creating 'drive_logs' table with extended metrics...")
    cur.execute("""
        CREATE TABLE drive_logs (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR(50),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ear_value FLOAT,           -- Eye Aspect Ratio (Instantaneous)
            mar_value FLOAT,           -- Mouth Aspect Ratio (Yawning)
            perclos_score FLOAT,       -- Fatigue Score (%)
            is_distracted BOOLEAN,     -- Boolean Flag for distraction
            head_yaw FLOAT,            -- Head rotation (Left/Right)
            head_pitch FLOAT,          -- Head rotation (Up/Down)
            head_roll FLOAT            -- Head rotation (Tilt)
        );
    """)

    # 4. Commit and Close
    conn.commit()
    print("Database initialized successfully.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    initialize_database()
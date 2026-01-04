import os
import psycopg2

def initialize_database():
    """
    Connects to the PostgreSQL database and creates the necessary table
    for storing comprehensive driver monitoring data.
    """
    # 1. Get the database URL from Heroku environment variables
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Ensure the Postgres addon is provisioned.")

    print("Connecting to database...")
    # 2. Connect to the database (sslmode is required for Heroku)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    # 3. Drop old tables if they exist to ensure a fresh schema
    print("Dropping old tables if they exist...")
    cur.execute("DROP TABLE IF EXISTS fatigue_data;") # Cleanup old version
    cur.execute("DROP TABLE IF EXISTS drive_logs;")   # Cleanup previous attempts

    # 4. Create the new 'drive_logs' table with scientific metrics
    print("Creating 'drive_logs' table...")
    cur.execute("""
        CREATE TABLE drive_logs (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR(50),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ear_value FLOAT,           -- Eye Aspect Ratio (Instantaneous openness)
            mar_value FLOAT,           -- Mouth Aspect Ratio (Yawning detection)
            perclos_score FLOAT,       -- PERCLOS % (Percentage of Eye Closure over time)
            is_distracted BOOLEAN,     -- True if driver is looking away (Head Pose)
            head_yaw FLOAT             -- Head rotation angle (Left/Right)
        );
    """)

    # 5. Commit changes and close connection
    conn.commit()
    print("Table 'drive_logs' created successfully.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    initialize_database()
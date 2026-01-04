import os
import psycopg2

# Get database URL from cloud server settings
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Did you provision the Postgres addon?")

print("Connecting to database...")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

print("Creating 'fatigue_data' table...")
# Create the table to store data
cur.execute("""
    CREATE TABLE IF NOT EXISTS fatigue_data (
        id SERIAL PRIMARY KEY,
        device_id VARCHAR(50),
        fatigue_level FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

conn.commit()
print("Table created successfully.")

cur.close()
conn.close()
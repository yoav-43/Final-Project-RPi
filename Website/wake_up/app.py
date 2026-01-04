import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """
    Helper function to establish a connection to the Heroku PostgreSQL database.
    Returns: A database connection object.
    """
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# -----------------------------------------------------------------------------
# Route 1: Receive Telemetry (POST)
# This endpoint receives the full scientific data package from Raspberry Pi.
# -----------------------------------------------------------------------------
@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Receives JSON data containing fatigue metrics (EAR, MAR, PERCLOS, Head Pose).
    Stores the data into the 'drive_logs' table.
    """
    data = request.get_json()
    
    # Extract data safely with default values
    device_id = data.get('device_id', 'unknown')
    ear = data.get('ear', 0.0)
    mar = data.get('mar', 0.0)
    perclos = data.get('perclos', 0.0)
    is_distracted = data.get('is_distracted', False)
    head_yaw = data.get('head_yaw', 0.0)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert data into the database
        query = """
            INSERT INTO drive_logs 
            (device_id, ear_value, mar_value, perclos_score, is_distracted, head_yaw) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (device_id, ear, mar, perclos, is_distracted, head_yaw))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Telemetry saved"}), 201

    except Exception as e:
        print(f"[Error] Database insertion failed: {e}")
        return jsonify({"error": "Internal server error"}), 500

# -----------------------------------------------------------------------------
# Route 2: Get History (GET)
# This endpoint provides data for the frontend graphs.
# -----------------------------------------------------------------------------
@app.route('/api/history', methods=['GET'])
def get_history():
    """
    Fetches the last 50 recorded data points.
    Returns JSON formatted for Chart.js visualization.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Select relevant columns for the dashboard
        cur.execute("""
            SELECT timestamp, perclos_score, mar_value, is_distracted, head_yaw
            FROM drive_logs 
            ORDER BY timestamp DESC LIMIT 50
        """)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()

        # Format data: Convert timestamp to string and structure as list of dicts
        history_data = []
        for row in rows:
            history_data.append({
                "time": row[0].strftime("%H:%M:%S"),
                "perclos": row[1],
                "mar": row[2],
                "distracted": row[3],
                "head_yaw": row[4]
            })
        
        # Reverse list so the graph draws from Left (oldest) to Right (newest)
        return jsonify(list(reversed(history_data)))

    except Exception as e:
        print(f"[Error] Fetching history failed: {e}")
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Route 3: Main Dashboard (GET)
# Serves the HTML page.
# -----------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """
    Establishes a secure connection to the Heroku PostgreSQL database.
    """
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# -----------------------------------------------------------------------------
# API: Receive Telemetry (POST)
# Receives full JSON payload from Raspberry Pi and saves to DB.
# -----------------------------------------------------------------------------
@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    data = request.get_json()
    
    # Extract data with safe defaults
    device_id = data.get('device_id', 'unknown')
    ear = data.get('ear', 0.0)
    mar = data.get('mar', 0.0)
    perclos = data.get('perclos', 0.0)
    is_distracted = data.get('is_distracted', False)
    
    # Extract 3D Head Pose
    head_yaw = data.get('head_yaw', 0.0)
    head_pitch = data.get('head_pitch', 0.0)
    head_roll = data.get('head_roll', 0.0)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert all metrics into the database
        query = """
            INSERT INTO drive_logs 
            (device_id, ear_value, mar_value, perclos_score, is_distracted, head_yaw, head_pitch, head_roll) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (device_id, ear, mar, perclos, is_distracted, head_yaw, head_pitch, head_roll))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"status": "success"}), 201

    except Exception as e:
        print(f"[Error] DB Insert: {e}")
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# API: Get History (GET)
# Fetches recent history for the Dashboard Graphs.
# -----------------------------------------------------------------------------
@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Fetch last 100 records for a detailed graph history
        cur.execute("""
            SELECT timestamp, perclos_score, ear_value, mar_value, 
                   head_yaw, head_pitch, head_roll, is_distracted 
            FROM drive_logs 
            ORDER BY timestamp DESC LIMIT 100
        """)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()

        # Format data for JSON response
        history_data = []
        for row in rows:
            history_data.append({
                "time": row[0].strftime("%H:%M:%S"),
                "perclos": row[1],
                "ear": row[2],
                "mar": row[3],
                "yaw": row[4],
                "pitch": row[5],
                "roll": row[6],
                "distracted": row[7]
            })
        
        # Reverse to show chronological order (Left to Right)
        return jsonify(list(reversed(history_data)))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Route: Web Interface
# -----------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """Establishes secure connection to Heroku PostgreSQL."""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# -----------------------------------------------------------------------------
# API: Session Management (Start/End Drive)
# -----------------------------------------------------------------------------

@app.route('/api/start_drive', methods=['POST'])
def start_drive():
    """
    Initiates a new driving session.
    Returns: JSON containing the new 'drive_id'.
    """
    data = request.get_json()
    device_id = data.get('device_id', 'unknown')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create new drive record
    cur.execute("INSERT INTO drives (device_id) VALUES (%s) RETURNING id", (device_id,))
    drive_id = cur.fetchone()[0]
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "session_started", "drive_id": drive_id}), 201

@app.route('/api/end_drive', methods=['POST'])
def end_drive():
    """
    Finalizes a driving session by setting the end_time.
    """
    data = request.get_json()
    drive_id = data.get('drive_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Update end_time to current server time
    cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "session_ended"}), 200

# -----------------------------------------------------------------------------
# API: Telemetry Ingestion
# -----------------------------------------------------------------------------

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Receives logging data from RPi.
    Updates 'drive_logs' and also updates 'drives.end_time' (heartbeat mechanism).
    """
    data = request.get_json()
    
    drive_id = data.get('drive_id')
    if not drive_id:
        return jsonify({"error": "Missing drive_id"}), 400

    # Extract metrics
    ear = data.get('ear', 0.0)
    mar = data.get('mar', 0.0)
    perclos = data.get('perclos', 0.0)
    is_distracted = data.get('is_distracted', False)
    yaw = data.get('head_yaw', 0.0)
    pitch = data.get('head_pitch', 0.0)
    roll = data.get('head_roll', 0.0)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Insert Log
        cur.execute("""
            INSERT INTO drive_logs 
            (drive_id, ear_value, mar_value, perclos_score, is_distracted, head_yaw, head_pitch, head_roll) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (drive_id, ear, mar, perclos, is_distracted, yaw, pitch, roll))
        
        # 2. Update parent Drive record (increment alerts and update heartbeat/end_time)
        # We update 'end_time' on every log so if RPi crashes, we have the last known time.
        if perclos > 25 or is_distracted:
             cur.execute("""
                UPDATE drives 
                SET total_alerts = total_alerts + 1, end_time = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (drive_id,))
        else:
             cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# API: Data Retrieval for Charts
# -----------------------------------------------------------------------------

@app.route('/api/history/<int:drive_id>')
def get_drive_history(drive_id):
    """Fetches all logs for a specific drive session."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, perclos_score, ear_value, mar_value, 
               head_yaw, head_pitch, head_roll, is_distracted 
        FROM drive_logs 
        WHERE drive_id = %s
        ORDER BY timestamp ASC
    """, (drive_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

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
    return jsonify(history_data)

# -----------------------------------------------------------------------------
# Web Views (HTML)
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """Fleet Manager Home: Lists all drives."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch all drives ordered by start time (newest first)
    # Format dates inside SQL or Python. Here we select raw and format in template if needed, 
    # but for simplicity, we pass raw datetime objects.
    cur.execute("""
        SELECT id, device_id, start_time, end_time, total_alerts 
        FROM drives 
        ORDER BY start_time DESC
    """)
    drives = cur.fetchall()
    
    # Calculate global stats
    total_drives = len(drives)
    total_alerts = sum(d[4] for d in drives) if drives else 0
    
    cur.close()
    conn.close()
    return render_template('index.html', drives=drives, total_drives=total_drives, total_alerts=total_alerts)

@app.route('/drive/<int:drive_id>')
def drive_dashboard(drive_id):
    """Detailed dashboard for a specific drive."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch Drive Metadata (Start/End/ID)
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts FROM drives WHERE id = %s", (drive_id,))
    drive = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not drive:
        return "Drive not found", 404

    # Convert tuple to dictionary for easier Jinja access
    drive_data = {
        "id": drive[0],
        "device": drive[1],
        "start": drive[2].strftime("%Y-%m-%d %H:%M:%S") if drive[2] else "-",
        "end": drive[3].strftime("%Y-%m-%d %H:%M:%S") if drive[3] else "In Progress...",
        "alerts": drive[4]
    }

    return render_template('drive.html', drive=drive_data)

if __name__ == '__main__':
    app.run(debug=True)
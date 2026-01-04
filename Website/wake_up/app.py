"""
DRIVER MONITORING FLEET MANAGEMENT - BACKEND SERVER
---------------------------------------------------
Framework: Flask
Database: PostgreSQL (Heroku)
Description: 
    Central hub for the monitoring system. Ingests real-time telemetry,
    manages drive sessions, and serves the management dashboard with video links.
"""

import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """ Establishes a secure connection to Heroku PostgreSQL using SSL. """
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# --- SESSION MANAGEMENT ---

@app.route('/api/start_drive', methods=['POST'])
def start_drive():
    """ 
    Initiates a new drive session in the database. 
    Returns the unique 'drive_id' to the client. 
    """
    data = request.json
    device_id = data.get('device_id', 'unknown_device')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO drives (device_id, start_time) VALUES (%s, %s) RETURNING id",
        (device_id, datetime.now())
    )
    drive_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "success", "drive_id": drive_id})

@app.route('/api/end_drive', methods=['POST'])
def end_drive():
    """ 
    Finalizes a drive session by updating the end_time and storing 
     the permanent Cloudinary video link. 
    """
    data = request.json
    drive_id = data.get('drive_id')
    video_url = data.get('video_url')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE drives SET end_time = %s, video_url = %s WHERE id = %s",
        (datetime.now(), video_url, drive_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "drive_ended"})

# --- TELEMETRY INGESTION ---

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """ 
    Receives real-time metrics (EAR, PERCLOS, Pose) from the RPi 
    and logs them into the drive_logs table. 
    """
    data = request.json
    drive_id = data.get('drive_id')
    ear = data.get('ear', 0.0)
    is_distracted = data.get('is_distracted', False)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Log the specific telemetry entry
        cur.execute(
            "INSERT INTO drive_logs (drive_id, ear_value, is_distracted) VALUES (%s, %s, %s)",
            (drive_id, ear, is_distracted)
        )
        # Update session heartbeat and alert counts
        cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))
        if is_distracted:
            cur.execute("UPDATE drives SET total_alerts = total_alerts + 1 WHERE id = %s", (drive_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- DASHBOARD VIEWS ---

@app.route('/')
def index():
    """ Renders the main fleet manager overview with all sessions. """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, device_id, start_time, end_time, total_alerts, video_url 
        FROM drives ORDER BY start_time DESC
    """)
    drives = cur.fetchall()
    total_alerts = sum(d[4] for d in drives) if drives else 0
    cur.close()
    conn.close()
    return render_template('index.html', drives=drives, total_alerts=total_alerts)

@app.route('/drive/<int:drive_id>')
def drive_dashboard(drive_id):
    """ Renders detailed analytics and video player for a specific drive session. """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts, video_url FROM drives WHERE id = %s", (drive_id,))
    drive = cur.fetchone()
    cur.close()
    conn.close()
    
    if not drive: return "Drive not found", 404

    drive_data = {
        "id": drive[0],
        "device": drive[1],
        "start": drive[2].strftime("%Y-%m-%d %H:%M:%S") if drive[2] else "-",
        "end": drive[3].strftime("%H:%M:%S") if drive[3] else "Active",
        "alerts": drive[4],
        "video_url": drive[5]
    }
    return render_template('drive.html', drive=drive_data)

if __name__ == '__main__':
    app.run(debug=True)
"""
DRIVER MONITORING FLEET MANAGEMENT - BACKEND SERVER
---------------------------------------------------
Framework: Flask
Database: PostgreSQL (Heroku)
Description: 
    This server acts as a central hub for the Driver Monitoring System. 
    It ingests real-time telemetry from Raspberry Pi devices, manages 
    drive session lifecycles, and serves data to the management dashboard.
"""

import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """
    Establishes a secure connection to the Heroku PostgreSQL database.
    Uses 'sslmode=require' as mandated by Heroku for external connections.
    
    Returns:
        psycopg2.connection: A connection object to the database.
    """
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# -----------------------------------------------------------------------------
# API: SESSION MANAGEMENT (DRIVE LIFECYCLE)
# -----------------------------------------------------------------------------

@app.route('/api/start_drive', methods=['POST'])
def start_drive():
    """
    Endpoint: POST /api/start_drive
    Description: Initiates a new driving session when a driver is detected by the client.
    
    Expected JSON Payload:
        { "device_id": "string" }
        
    Returns:
        JSON: status and the newly generated 'drive_id'.
    """
    data = request.get_json()
    device_id = data.get('device_id', 'unknown')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Insert a new record into the 'drives' table and return the serial ID.
    cur.execute("INSERT INTO drives (device_id) VALUES (%s) RETURNING id", (device_id,))
    drive_id = cur.fetchone()[0]
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "session_started", "drive_id": drive_id}), 201

@app.route('/api/end_drive', methods=['POST'])
def end_drive():
    """
    Endpoint: POST /api/end_drive
    Description: Finalizes a driving session, records the end time, and links 
                 the Cloudinary video URL to the session record.
    
    Expected JSON Payload:
        { "drive_id": int, "video_url": "string" }
        
    Returns:
        JSON: Confirmation status and the saved video URL.
    """
    data = request.get_json()
    drive_id = data.get('drive_id')
    video_url = data.get('video_url') # URL provided after Cloudinary upload completion
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Atomic update of the session's end time and the permanent cloud storage link.
    cur.execute("""
        UPDATE drives 
        SET end_time = CURRENT_TIMESTAMP, video_url = %s 
        WHERE id = %s
    """, (video_url, drive_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "session_ended", "video_url": video_url}), 200

# -----------------------------------------------------------------------------
# API: TELEMETRY INGESTION (REAL-TIME DATA)
# -----------------------------------------------------------------------------

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Endpoint: POST /api/telemetry
    Description: Ingests granular sensor data from the Raspberry Pi. 
                 Updates the 'drive_logs' and maintains a heartbeat on the parent session.
    
    Key Metrics Ingested:
        - EAR/MAR: Facial aspect ratios for drowsiness detection.
        - PERCLOS: Percentage of eye closure score.
        - Head Pose: Yaw, Pitch, and Roll angles for distraction monitoring.
    """
    data = request.get_json()
    drive_id = data.get('drive_id')
    
    if not drive_id:
        return jsonify({"error": "Missing drive_id"}), 400

    # Extracting sensor values from the payload
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
        
        # 1. Archive the detailed log entry for historical analysis.
        cur.execute("""
            INSERT INTO drive_logs 
            (drive_id, ear_value, mar_value, perclos_score, is_distracted, head_yaw, head_pitch, head_roll) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (drive_id, ear, mar, perclos, is_distracted, yaw, pitch, roll))
        
        # 2. Update the parent 'drives' record.
        # This acts as a 'Heartbeat' mechanism to keep the session active and increments alerts.
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
# WEB VIEWS (SERVER-SIDE RENDERING)
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """
    Route: GET /
    Description: Fleet Manager Overview. Renders a summary of all recorded 
                 drive sessions and global statistics.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Retrieve all drive metadata including the new Cloudinary video link.
    cur.execute("""
        SELECT id, device_id, start_time, end_time, total_alerts, video_url 
        FROM drives 
        ORDER BY start_time DESC
    """)
    drives = cur.fetchall()
    
    # Calculate aggregate metrics for the dashboard header.
    total_drives = len(drives)
    total_alerts = sum(d[4] for d in drives) if drives else 0
    
    cur.close()
    conn.close()
    return render_template('index.html', drives=drives, total_drives=total_drives, total_alerts=total_alerts)

@app.route('/drive/<int:drive_id>')
def drive_dashboard(drive_id):
    """
    Route: GET /drive/<id>
    Description: Detailed analytics view for a specific session. 
                 Provides historical graphs and the recorded video playback link.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch session-specific metadata.
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts, video_url FROM drives WHERE id = %s", (drive_id,))
    drive = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not drive:
        return "Drive not found", 404

    # Structure data for Jinja2 template rendering.
    drive_data = {
        "id": drive[0],
        "device": drive[1],
        "start": drive[2].strftime("%Y-%m-%d %H:%M:%S") if drive[2] else "-",
        "end": drive[3].strftime("%Y-%m-%d %H:%M:%S") if drive[3] else "In Progress...",
        "alerts": drive[4],
        "video_url": drive[5]
    }

    return render_template('drive.html', drive=drive_data)

if __name__ == '__main__':
    # Flask development server initialization. 
    # In production (Heroku), Gunicorn is used instead.
    app.run(debug=True)
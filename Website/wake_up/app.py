"""
WakeUp — Driver Monitoring Backend
===================================
Flask application that serves as the central data hub for the WakeUp system.
Provides a REST API for the Raspberry Pi to register drive sessions and stream
telemetry, and renders HTML dashboards for fleet overview and per-session analytics.

Database: Heroku Postgres (psycopg2, SSL required)
Deployment: Heroku (gunicorn, see Procfile)
"""

import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """Opens a new SSL-secured connection to the Heroku Postgres database."""
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# =============================================================================
# Drive Session API
# =============================================================================

@app.route('/api/start_drive', methods=['POST'])
def start_drive():
    """
    Registers a new drive session in the database.

    Request body: {"device_id": str}
    Response:     {"status": "success", "drive_id": int}
    """
    data = request.json
    device_id = data.get('device_id', 'unknown_raspi')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO drives (device_id, start_time) VALUES (%s, CURRENT_TIMESTAMP) RETURNING id",
            (device_id,)
        )
        drive_id = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"status": "success", "drive_id": drive_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/end_drive', methods=['POST'])
def end_drive():
    """
    Finalizes a drive session by recording the end time and Cloudinary video URL.

    Request body: {"drive_id": int, "video_url": str}
    Response:     {"status": "success"}
    """
    data = request.json
    drive_id = data.get('drive_id')
    video_url = data.get('video_url')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE drives SET end_time = CURRENT_TIMESTAMP, video_url = %s WHERE id = %s",
            (video_url, drive_id)
        )
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =============================================================================
# Telemetry API
# =============================================================================

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """
    Ingests a real-time telemetry sample from the Raspberry Pi.
    Inserts a row into drive_logs and updates the session heartbeat
    and alert counter in the parent drives table.

    Request body: {"drive_id", "ear", "perclos", "is_distracted",
                   "head_yaw", "head_pitch", "latitude", "longitude"}
    Response:     {"status": "success"}
    """
    data = request.json
    drive_id = data.get('drive_id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert the granular telemetry record for chart rendering.
        cur.execute("""
            INSERT INTO drive_logs (drive_id, ear_value, perclos_score, is_distracted, head_yaw, head_pitch, latitude, longitude) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (drive_id, data.get('ear'), data.get('perclos'), data.get('is_distracted'), 
              data.get('head_yaw'), data.get('head_pitch'), data.get('latitude'), data.get('longitude')))
        
        # Update the session heartbeat so end_time reflects the last known activity.
        cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))

        # Increment the alert counter whenever a fatigue or distraction event is detected.
        if data.get('is_distracted') or data.get('perclos', 0) > 25:
            cur.execute("UPDATE drives SET total_alerts = total_alerts + 1 WHERE id = %s", (drive_id,))
        
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<int:drive_id>')
def get_drive_history(drive_id):
    """
    Returns all telemetry records for a session, ordered chronologically.
    Consumed by dashboard.js to render the Chart.js time-series charts.

    Response: JSON array of {time, ear, perclos, yaw, pitch, distracted}
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, ear_value, perclos_score, head_yaw, head_pitch, is_distracted 
        FROM drive_logs WHERE drive_id = %s ORDER BY timestamp ASC
    """, (drive_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    
    return jsonify([{
        "time": r[0].strftime("%H:%M:%S"),
        "ear": r[1], "perclos": r[2], "yaw": r[3], "pitch": r[4], "distracted": r[5]
    } for r in rows])

@app.route('/api/gps/<int:drive_id>')
def get_drive_gps(drive_id):
    """Returns ordered GPS coordinates for a drive session, skipping (0,0) points."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT latitude, longitude FROM drive_logs
        WHERE drive_id = %s AND latitude != 0 AND longitude != 0
        ORDER BY timestamp ASC
    """, (drive_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([{"lat": r[0], "lon": r[1]} for r in rows])

# =============================================================================
# Web Dashboards
# =============================================================================

@app.route('/')
def index():
    """
    Renders the fleet overview dashboard listing all drive sessions
    with summary statistics (total drives, total alerts).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts, video_url FROM drives ORDER BY start_time DESC")
    drives = cur.fetchall()
    total_drives = len(drives)
    total_alerts = sum(d[4] for d in drives) if drives else 0
    cur.close(); conn.close()
    return render_template('index.html', drives=drives, total_drives=total_drives, total_alerts=total_alerts)

@app.route('/drive/<int:drive_id>')
def drive_dashboard(drive_id):
    """
    Renders the per-session analytics dashboard with Chart.js charts,
    an embedded video player, and a detailed alert log table.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts, video_url FROM drives WHERE id = %s", (drive_id,))
    drive = cur.fetchone()
    cur.close(); conn.close()
    
    if not drive: return "Error: Session Not Found", 404
    
    d_view = {
        "id": drive[0], "device": drive[1], 
        "start": drive[2].strftime("%Y-%m-%d %H:%M:%S") if drive[2] else "N/A",
        "end": drive[3].strftime("%H:%M:%S") if drive[3] else "Active",
        "alerts": drive[4], "video": drive[5]
    }
    thresholds = {
        "perclos_fatigue_limit": 25,
        "ear": 0.25,
        "head_yaw": 22,
        "head_pitch": -15
    }
    return render_template('drive.html', drive=d_view, thresholds=thresholds)

if __name__ == '__main__':
    app.run(debug=True)

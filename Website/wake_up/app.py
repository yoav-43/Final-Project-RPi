"""
DRIVER MONITORING BACKEND - VERSION 4.0
---------------------------------------------------------------------------------------
Description:
    Flask-based API for session management, telemetry ingestion (PostgreSQL), 
    and rendering management dashboards.
---------------------------------------------------------------------------------------
"""

import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """ Establish secure connection to Heroku Postgres. """
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# =============================================================================
# DRIVE SESSION API
# =============================================================================

@app.route('/api/start_drive', methods=['POST'])
def start_drive():
    """ Registers a new drive session in the database. """
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
    """ Finalizes session and stores Cloudinary video URL. """
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
# TELEMETRY API
# =============================================================================

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """ Ingests real-time metrics and updates the session heartbeat. """
    data = request.json
    drive_id = data.get('drive_id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Log granular data for charts
        cur.execute("""
            INSERT INTO drive_logs (drive_id, ear_value, perclos_score, is_distracted, head_yaw, head_pitch) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (drive_id, data.get('ear'), data.get('perclos'), data.get('is_distracted'), 
              data.get('head_yaw'), data.get('head_pitch')))
        
        # Update heartbeat and alert counter in parent table
        cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))
        if data.get('is_distracted') or data.get('perclos', 0) > 25:
            cur.execute("UPDATE drives SET total_alerts = total_alerts + 1 WHERE id = %s", (drive_id,))
        
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<int:drive_id>')
def get_drive_history(drive_id):
    """ Returns data points for Chart.js rendering and alert tables. """
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

# =============================================================================
# WEB DASHBOARDS
# =============================================================================

@app.route('/')
def index():
    """ Fleet Overview Dashboard. """
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
    """ Detailed Analysis Dashboard for a specific session. """
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
    return render_template('drive.html', drive=d_view)

if __name__ == '__main__':
    app.run(debug=True)
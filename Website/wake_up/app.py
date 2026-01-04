"""
DRIVER MONITORING SYSTEM - CENTRAL SERVER (v3.0)
-----------------------------------------------
Author: Yoav Roy Project
Description: Flask server handling high-frequency telemetry, 
             PostgreSQL persistence, and real-time dashboard rendering.
"""

import os
import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """ Establish secure SSL connection to Heroku Postgres. """
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- TELEMETRY API ---

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """ Ingests multi-dimensional telemetry from RPi. """
    data = request.json
    drive_id = data.get('drive_id')
    
    # Payload Extraction
    metrics = {
        "ear": data.get('ear', 0.0),
        "perclos": data.get('perclos', 0.0),
        "distracted": data.get('is_distracted', False),
        "yaw": data.get('head_yaw', 0.0),
        "pitch": data.get('head_pitch', 0.0)
    }

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Insert detailed log
        cur.execute("""
            INSERT INTO drive_logs 
            (drive_id, ear_value, perclos_score, is_distracted, head_yaw, head_pitch) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (drive_id, metrics['ear'], metrics['perclos'], metrics['distracted'], metrics['yaw'], metrics['pitch']))
        
        # 2. Update parent session heartbeat
        cur.execute("UPDATE drives SET end_time = CURRENT_TIMESTAMP WHERE id = %s", (drive_id,))
        
        # 3. Increment alert count if fatigue/distraction detected
        if metrics['distracted'] or metrics['perclos'] > 25:
            cur.execute("UPDATE drives SET total_alerts = total_alerts + 1 WHERE id = %s", (drive_id,))
        
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        print(f"[DEBUG ERROR] Telemetry Ingestion Failed: {e}")
        return jsonify({"error": str(e)}), 500

# --- DATA FETCHING FOR CHARTS ---

@app.route('/api/history/<int:drive_id>')
def get_drive_history(drive_id):
    """ Returns all telemetry points for Chart.js rendering. """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, ear_value, perclos_score, head_yaw, head_pitch, is_distracted 
        FROM drive_logs WHERE drive_id = %s ORDER BY timestamp ASC
    """, (drive_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    
    history = [{
        "time": r[0].strftime("%H:%M:%S"),
        "ear": r[1], "perclos": r[2],
        "yaw": r[3], "pitch": r[4], "distracted": r[5]
    } for r in rows]
    return jsonify(history)

# --- VIEW ROUTES ---

@app.route('/')
def index():
    """ Main Fleet Dashboard Overview. """
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
    """ Detailed session analytics page. """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, device_id, start_time, end_time, total_alerts, video_url FROM drives WHERE id = %s", (drive_id,))
    drive = cur.fetchone()
    cur.close(); conn.close()
    
    if not drive: return "Drive Session Not Found", 404
    
    d = {"id": drive[0], "device": drive[1], "start": drive[2], "end": drive[3], "alerts": drive[4], "video": drive[5]}
    return render_template('drive.html', drive=d)

# Include /api/start_drive and /api/end_drive here as previously defined...

if __name__ == '__main__':
    app.run(debug=True)
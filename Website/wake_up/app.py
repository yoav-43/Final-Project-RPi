import os
import psycopg2
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Helper function to connect to the database
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")
    
    # Using sslmode='require' is essential for connecting to Heroku
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# Route 1: Receive data from Raspberry Pi (POST)
@app.route('/api/data', methods=['POST'])
def receive_data():
    data = request.get_json()
    
    if not data or 'device_id' not in data or 'fatigue' not in data:
        return jsonify({"error": "Invalid data format"}), 400
        
    device_id = data['device_id']
    fatigue_level = data['fatigue']
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Save data to the database
        cur.execute(
            "INSERT INTO fatigue_data (device_id, fatigue_level) VALUES (%s, %s)",
            (device_id, fatigue_level)
        )
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "message": "Data received"}), 201
        
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Route 2: Send data to dashboard (GET)
@app.route('/api/data', methods=['GET'])
def send_data_to_dashboard():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Fetch the last 100 records
        cur.execute("SELECT created_at, fatigue_level FROM fatigue_data ORDER BY created_at DESC LIMIT 100")
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Convert data to JSON format understood by the chart
        data_for_chart = [
            {"timestamp": row[0].isoformat(), "fatigue": row[1]} 
            for row in rows
        ]
        
        # Return data in chronological order (reversed)
        return jsonify(list(reversed(data_for_chart)))
        
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Route 3: Serve the main page (Dashboard)
@app.route('/')
def index():
    # Serve the HTML file from the 'templates' folder
    return render_template('index.html')

if __name__ == '__main__':
    # Local run for testing purposes
    app.run(debug=True)
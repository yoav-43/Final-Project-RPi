# WakeUp: Driver Fatigue & Distraction Monitoring System

**WakeUp** is an AI-powered system designed for real-time driver alertness monitoring. By leveraging Computer Vision, the system detects signs of fatigue and distraction, syncs telemetry data to the cloud, and provides a comprehensive management dashboard featuring analytics charts and video recordings.

---

## 📊 Biometric Metrics (Analytics)
The system calculates four primary metrics to determine the driver's state in real-time:

1. **EAR (Eye Aspect Ratio)**:
   * **Description**: A geometric measure of eye openness.
   * **Logic**: Calculated as the ratio between the vertical and horizontal distances of the eye using 6 facial landmarks.
   * **Threshold**: An `EAR < 0.25` is considered an eye closure event.

2. **PERCLOS (Percentage of Closure)**:
   * **Description**: The percentage of time the eyes are closed within a one-minute window.
   * **Logic**: Widely recognized as the most reliable professional metric for predicting drowsiness.
   * **Threshold**: A PERCLOS score above 25% triggers a "Critical Fatigue" alert on the dashboard.

3. **Head Yaw**:
   * **Description**: The horizontal rotation of the head (left/right).
   * **Logic**: Uses the `SolvePnP` algorithm to estimate 3D head pose.
   * **Threshold**: Rotations exceeding 22 degrees indicate the driver is not looking at the road.

4. **Head Pitch**:
   * **Description**: The vertical tilt of the head (up/down).
   * **Logic**: Detects when a driver looks down (e.g., at a phone) or tilts their head excessively.
   * **Threshold**: A downward pitch below -15 degrees triggers a distraction alert.



---

## 📂 Project Structure

### 🛰️ Client Side (Raspberry Pi)
* **`driver_monitor.py`**: The core monitoring script. It manages the camera stream, performs AI analysis, records video, and transmits 1Hz telemetry heartbeats to the server.

### ☁️ Server Side (Heroku Backend)
* **`app.py`**: The Flask-based backend API that handles session management, data ingestion, and dashboard rendering.
* **`init_db.py`**: A database initialization script that sets up the PostgreSQL schema (`drives` and `drive_logs` tables).
* **`static/dashboard.js`**: The front-end analytics engine that renders 4 interactive charts using `Chart.js`.
* **`templates/`**: HTML Jinja2 templates for the Fleet Overview and detailed Drive Analytics pages.

---

## 🛠️ Technology Stack
* **Languages**: Python (Backend/AI), JavaScript (Charts), HTML/CSS (UI).
* **Computer Vision**: OpenCV, Dlib (68-point landmark predictor), imutils.
* **Cloud Infrastructure**: Heroku (Hosting), Cloudinary (Video Storage), PostgreSQL (Database).

---

## 🔄 Data Flow
1. **Detection**: The Raspberry Pi recognizes the driver and initiates a new session via the API.
2. **Analysis**: The device calculates EAR and head pose angles, sending telemetry as JSON packets every second.
3. **Alerting**: The server monitors incoming data and increments the alert counter if thresholds are breached.
4. **Archiving**: Upon session termination, the recorded video is uploaded to Cloudinary and linked to the drive record.
5. **Visualization**: Managers can review the session, watch the synchronized video, and analyze behavior through the 4 primary metric charts.
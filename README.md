# WakeUp - Advanced Driver Monitoring System

**WakeUp** is a real-time IoT safety system designed to prevent car accidents caused by driver fatigue and distraction. Powered by a Raspberry Pi, Computer Vision, and Cloud connectivity, the system monitors the driver's state and issues immediate alerts while logging data for analysis.

## Features

* **Real-time Fatigue Detection:** Uses **EAR (Eye Aspect Ratio)** to detect drowsiness and prolonged eye closure.
* **Distraction Detection:** Uses **Head Pose Estimation** (Yaw/Pitch) to detect when the driver looks away from the road.
* **Crash-Safe Video Recording:** Records drive sessions in `.avi` (MJPG) format, ensuring video evidence is saved even if power is lost abruptly.
* **Hardware Alerts:** Integrated **Arduino + Buzzer** system for immediate, loud auditory feedback.
* **Location Tracking:** Real-time GPS logging (NMEA parsing) correlated with driver status.
* **Cloud Integration:**
    * **Cloudinary:** Automatic video evidence upload (transcoded to MP4 for web viewing).
    * **Heroku:** Telemetry synchronization to a remote database.
* **Web Dashboard:** A Flask-based website to view drive history, route maps, and safety statistics.

---

## Project Structure

```text
Final-Project-RPi/
│
├── archive/                     # Legacy code & backups
│   └── driver_monitor.py        # Old main script (unused)
│
├── buzzer/                      # Hardware Alert System
│   ├── buzzer.ino               # C++ Firmware for Arduino
│   └── buzzer.py                # Python Serial Controller
│
├── cloudinary_server_manager/   # Cloud Storage
│   └── cloudinary_server_manager.py # Uploads video evidence
│
├── gps/                         # Location Services
│   └── gps_manager.py           # Reads and parses NMEA GPS data
│
├── heroku_server_manager/       # Backend Communication
│   └── heroku_server_manager.py # Syncs telemetry to the database
│
├── image_processor/             # Computer Vision Core
│   └── image_processor.py       # Face detection, EAR, Pose, Video Recording
│
├── logger/                      # Utilities
│   └── logger.py                # System-wide color logging
│
├── monitor/                     # Main Application
│   ├── config.json              # System Config (Thresholds, Ports)
│   └── monitor.py               # MAIN ENTRY POINT (Run this file)
│
├── Website/                     # Web Dashboard
│   ├── wake_up/                 # Flask Application Source
│   │   ├── app.py               # Web Server Logic
│   │   ├── init_db.py           # Database Initializer
│   │   ├── Procfile             # Heroku deployment file
│   │   ├── requirements.txt     # Web dependencies
│   │   ├── static/              # CSS/JS Assets (dashboard.js)
│   │   └── templates/           # HTML Views (index.html, drive.html)
│   ├── mac_aliases.txt          # OS specific alias helpers
│   └── win_aliases.txt
│
├── .env                         # API Keys (Not tracked by Git)
├── .gitignore                   # Git configuration
└── README.md                    # Project Documentation
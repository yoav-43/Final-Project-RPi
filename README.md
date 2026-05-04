# WakeUp — Driver Monitoring System

WakeUp is a real-time IoT safety system that detects driver fatigue and distraction using computer vision, issues immediate hardware alerts, and logs every session to a cloud dashboard for review.

The system runs on a **Raspberry Pi** with a USB camera and an **Arduino-controlled buzzer**. At the end of each drive, the session video is uploaded to **Cloudinary** and all telemetry is stored in a **PostgreSQL** database accessible through a **Flask web dashboard** hosted on Heroku.

---

## How It Works

```
Camera → ImageProcessor → DriverMonitor → BuzzerController → Arduino → Buzzer
                                ↓
                         GPSManager (background thread)
                                ↓
                         HerokuClient → Flask API → PostgreSQL
                                ↓
                       CloudinaryManager → Cloudinary CDN
                                ↓
                         Web Dashboard (index / drive pages)
```

1. The camera captures frames at ~10 fps.
2. **dlib** detects the face and extracts 68 facial landmarks.
3. **EAR** (Eye Aspect Ratio) is computed each frame. If EAR < 0.25, the eye is counted as closed.
4. **PERCLOS** (% of closed-eye frames in the current window) is tracked. Above 25% → fatigue.
5. **Head pose** (yaw/pitch) is estimated via `cv2.solvePnP`. Yaw > ±22° or pitch < -15° → distraction.
6. The Arduino buzzer is commanded every frame: continuous tone for fatigue, double beep for distraction, silence for OK.
7. Every second, a telemetry payload (EAR, PERCLOS, yaw, pitch, GPS) is sent to the Heroku backend.
8. On shutdown, the `.avi` recording is uploaded to Cloudinary and the session is finalized on the server.

---

## Project Structure
## Project Structure

```
Final-Project-RPi/
│
├── monitor/                          # ★ MAIN ENTRY POINT
│   ├── monitor.py                    # DriverMonitor class — orchestrates everything
│   └── config.json                   # Thresholds, ports, device ID
│
├── image_processor/
│   └── image_processor.py            # Camera I/O, EAR, head pose, visual feedback
│
├── buzzer/
│   ├── buzzer.py                     # Python serial controller (RPi side)
│   └── buzzer.ino                    # Arduino firmware (flash to Arduino)
│
├── gps/
│   └── gps_manager.py                # Background thread, NMEA parser
│
├── heroku_server_manager/
│   └── heroku_server_manager.py      # HTTP client for the Flask backend
│
├── cloudinary_server_manager/
│   └── cloudinary_server_manager.py  # Cloudinary video uploader
│
├── logger/
│   └── logger.py                     # Color-coded console logger (used by all modules)
│
├── Website/
│   ├── wake_up/                      # Flask app (deployed to Heroku)
│   │   ├── app.py                    # API routes + HTML views
│   │   ├── init_db.py                # Database schema initializer
│   │   ├── Procfile                  # Heroku process file
│   │   ├── requirements.txt
│   │   ├── static/dashboard.js       # Chart.js rendering
│   │   └── templates/
│   │       ├── index.html            # Fleet overview dashboard
│   │       └── drive.html            # Per-session analytics dashboard
│   ├── mac_aliases.txt               # Shell aliases (macOS/Linux)
│   └── win_aliases.txt               # PowerShell functions (Windows)
│
├── shape_predictor_68_face_landmarks.dat   # dlib AI model (not in repo — download separately)
├── .env                              # Secret keys (not committed)
└── archive/
    └── driver_monitor.py             # Legacy monolithic script (reference only)
```

---

## Prerequisites

### Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi (3B+ or 4) | Any Linux-capable RPi works. |
| USB webcam | Tested with V4L2-compatible cameras. |
| Arduino Uno (or compatible) | Connected via USB to the RPi. |
| Passive buzzer | Wired to Arduino pin 6. |
| GPS module (e.g., NEO-6M) | Connected to RPi UART (`/dev/ttyAMA0`). Optional — system runs without it. |

### Software

- Python 3.9+
- Arduino IDE (to flash `buzzer.ino`)
- A [Cloudinary](https://cloudinary.com) account (free tier is sufficient)
- A [Heroku](https://heroku.com) account with the **Heroku Postgres** add-on

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Final-Project-RPi.git
cd Final-Project-RPi
```

### 2. Install Python dependencies

```bash
pip3 install opencv-python dlib imutils scipy python-dotenv pyserial requests cloudinary
```

> **Note:** Building `dlib` from source on a Raspberry Pi can take 20–30 minutes. Consider using a pre-built wheel if available for your OS/Python version.

### 3. Download the dlib model

The `shape_predictor_68_face_landmarks.dat` file is not included in the repository due to its size (~100 MB).

```bash
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bzip2 -d shape_predictor_68_face_landmarks.dat.bz2
```

Place the `.dat` file in the **project root** (same level as `monitor/`).

### 4. Flash the Arduino firmware

Open `buzzer/buzzer.ino` in the Arduino IDE, select your board and port, and click **Upload**.

### 5. Create the `.env` file

Create a file named `.env` in the project root:

```
HEROKU_API_URL=https://your-app-name.herokuapp.com/api
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

This file is listed in `.gitignore` and will never be committed.

### 6. Configure `monitor/config.json`

Edit the non-secret settings to match your hardware:

```json
{
    "device_id": "raspi_v1",
    "arduino_port": "/dev/ttyACM0",
    "gps_port": "/dev/ttyAMA0",
    "thresholds": {
        "ear": 0.25,
        "head_yaw": 22,
        "head_pitch": -15,
        "perclos_fatigue_limit": 25
    }
}
```

Check your Arduino port with `ls /dev/ttyACM*` and your GPS port with `ls /dev/ttyAMA*` or `ls /dev/ttyUSB*`.

### 7. Deploy the web dashboard (first time)

```bash
heroku git:remote -a your-app-name
git subtree push --prefix Website/wake_up heroku main
heroku run python init_db.py
```

---

## Running the System

From the **project root**:

```bash
python3 monitor/monitor.py
```

The working directory must be the project root so that `config.json` and the `.dat` model are found at their expected relative paths.

**Expected startup output:**
```
[INFO] [MainMonitor] 10:00:01 - Initializing Image Processor...
[INFO] [Buzzer] 10:00:01 - Connected to Arduino on /dev/ttyACM0
[INFO] [GPS] 10:00:01 - GPS Background thread started.
[INFO] [HerokuClient] 10:00:02 - Drive started. ID: 42
[INFO] [MainMonitor] 10:00:02 - Recording video to: drive_video.avi
[INFO] [MainMonitor] 10:00:02 - System Live. Waiting for driver...
[DEBUG] [MainMonitor] 10:00:03 - EAR:0.34 | PERCLOS:0.0% | Yaw:2.1
```

Press **Ctrl+C** to stop. The system will automatically upload the video and finalize the session.

---

## Detection Thresholds

| Metric | Threshold | Alert Triggered |
|--------|-----------|-----------------|
| EAR | < 0.25 | Eye counted as closed |
| PERCLOS | > 25% | Fatigue alert (`b'F'` to buzzer) |
| Head Yaw | > ±22° | Distraction alert (`b'D'` to buzzer) |
| Head Pitch | < -15° | Distraction alert (`b'D'` to buzzer) |

All thresholds are adjustable in `monitor/config.json`.

---

## Module Documentation

Each module has its own detailed README:

- [monitor/README.md](monitor/README.md) — Main loop, config reference, startup sequence
- [image_processor/README.md](image_processor/README.md) — EAR formula, head pose algorithm, camera setup
- [buzzer/README.md](buzzer/README.md) — Serial protocol, Arduino firmware, hardware wiring
- [gps/README.md](gps/README.md) — NMEA parsing, background thread, coordinate conversion
- [heroku_server_manager/README.md](heroku_server_manager/README.md) — API contract, async telemetry
- [cloudinary_server_manager/README.md](cloudinary_server_manager/README.md) — Video upload, credentials setup
- [logger/README.md](logger/README.md) — Log levels, color codes, usage
- [Website/README.md](Website/README.md) — Database schema, API endpoints, deployment guide

---

## Troubleshooting

**Camera not found:**
Run `ls /dev/video*` to confirm the camera is detected. Try changing `camera_index` to `1` if index `0` fails.

**Arduino not connecting:**
Check the port with `ls /dev/ttyACM*`. Ensure your user is in the `dialout` group: `sudo usermod -aG dialout $USER` (requires logout/login).

**dlib build fails:**
Install build dependencies first: `sudo apt-get install build-essential cmake libopenblas-dev liblapack-dev`.

**GPS shows (0.0, 0.0):**
The GPS module may need up to 60 seconds to acquire a fix outdoors. The system continues to function without GPS data.

**API keys not found error:**
Ensure `.env` exists in the project root and contains all four required variables. Run `cat .env` to verify.

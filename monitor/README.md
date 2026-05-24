# monitor — Main Application Entry Point

This is the top-level orchestrator of the WakeUp system. Run `monitor.py` to start the entire driver monitoring pipeline.

## Files

| File | Description |
|------|-------------|
| `monitor.py` | Main application class `DriverMonitor`. Wires all modules together and runs the detection loop. |
| `config.json` | Non-secret configuration: device ID, detection thresholds, serial ports, and placeholder keys. |

## How It Works

`DriverMonitor.__init__()` performs the following startup sequence:

1. Loads `.env` from the project root (secrets: Heroku URL, Cloudinary keys).
2. Loads `config.json` (structure, thresholds, ports).
3. Overwrites the `"ENV_VAR"` placeholders in config with the real values from `.env`.
4. Validates that API keys are present — exits with an error if not.
5. Instantiates all sub-modules: `BuzzerController`, `CloudinaryManager`, `HerokuClient`, `GPSManager`, `ImageProcessor`.

`DriverMonitor.run()` is the main loop:

- Opens the camera via `ImageProcessor`.
- Calls `HerokuClient.start_drive()` to register the session on the server (retries up to 3 times with a 15s timeout to handle cold Heroku dyno starts).
- Creates a `cv2.VideoWriter` using the **MJPG + .avi** codec (crash-safe: frames are flushed to disk immediately).
- On every frame:
  - Computes **FPS** (updated every second, independent of face detection).
  - Detects faces with dlib's frontal HOG detector.
  - If no face: silences buzzer, draws stats overlay, continues.
  - Calculates **EAR** (Eye Aspect Ratio) for drowsiness.
  - Calculates **PERCLOS** using a **sliding window** of the last `perclos_window_frames` frames (~1.5 seconds at 10fps) for fatigue detection.
  - Estimates **head yaw/pitch** via `solvePnP` for distraction.
  - Sends the appropriate command to the buzzer (`F` / `D` / `O`).
  - Draws a live stats overlay (EAR, PERCLOS, Yaw, Pitch, FPS) on the frame — green = OK, red = violation.
  - Writes the annotated frame to the video file.
  - Shows a live window if `DISPLAY` is set (headless-safe).
- Every 1 second: sends a telemetry payload (EAR, PERCLOS, yaw, pitch, GPS) to the backend in a background thread.
- On `KeyboardInterrupt` or loop exit: calls `cleanup()`.

`DriverMonitor.cleanup()`:

- Releases the camera and video writer.
- Closes the display window (if open).
- Stops GPS and closes the serial port.
- Uploads the `.avi` file to Cloudinary.
- Calls `HerokuClient.end_drive()` with the resulting video URL.

## config.json Reference

```json
{
    "device_id": "raspi_v1",
    "predictor_path": "shape_predictor_68_face_landmarks.dat",
    "video_temp_file": "drive_video.mp4",
    "thresholds": {
        "ear": 0.25,
        "head_yaw": 45,
        "head_pitch": -15,
        "perclos_fatigue_limit": 25
    },
    "perclos_window_frames": 15,
    "arduino_port": "/dev/ttyACM0",
    "gps_port": "/dev/ttyAMA0"
}
```

| Key | Description |
|-----|-------------|
| `device_id` | Identifier sent to the backend to tag this device's sessions. |
| `predictor_path` | Path to the dlib 68-landmark `.dat` model file (relative to project root). |
| `video_temp_file` | Base name for the local video file. Extension is forced to `.avi` at runtime. |
| `thresholds.ear` | EAR value below which an eye is considered closed (default: `0.25`). |
| `thresholds.head_yaw` | Absolute yaw angle (degrees) above which the driver is considered distracted (default: `45`). |
| `thresholds.head_pitch` | Pitch angle below which the driver is considered distracted (default: `-15`). |
| `thresholds.perclos_fatigue_limit` | PERCLOS percentage above which fatigue is declared (default: `25%`). |
| `perclos_window_frames` | Number of frames in the PERCLOS sliding window (default: `15` ≈ 1.5 seconds at 10fps). |
| `arduino_port` | Serial port for the Arduino buzzer (Linux: `/dev/ttyACM0`). |
| `gps_port` | Serial port for the GPS module (Linux: `/dev/ttyAMA0`). |

## Running

From the **project root**:

```bash
python3 monitor/monitor.py
```

Or use the shell alias (after sourcing `Website/mac_aliases.txt`):

```bash
start_drive
```

The working directory must be the project root so that `config.json` and `shape_predictor_68_face_landmarks.dat` are found at their expected relative paths.

All output is logged to the terminal and saved to `latest.log` in the project root. Each run overwrites the previous log.

## Dependencies

```
opencv-python
dlib
imutils
scipy
python-dotenv
pyserial
requests
cloudinary
```

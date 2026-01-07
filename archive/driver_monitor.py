"""
DRIVER MONITORING SYSTEM (CLIENT SIDE) - ARDUINO & FULL ANALYTICS
---------------------------------------------------------------------------------------
Features: Visual face box (Dynamic Colors), EAR, PERCLOS, Head Pose, Cloud Sync, 
          and Arduino Serial Communication for Buzzer Alerts.
---------------------------------------------------------------------------------------
"""

import cv2
import dlib
import numpy as np
import serial  # Required for Arduino communication
from scipy.spatial import distance as dist
from imutils import face_utils
import requests
import time
import threading
import sys
import atexit
import cloudinary
import cloudinary.uploader
import os

# =============================================================================
# SYSTEM CONFIGURATION
# =============================================================================
BASE_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api"
DEVICE_ID = "raspi_v1"
PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
VIDEO_TEMP_FILE = "drive_video.mp4" 

# Initialize Serial Connection to Arduino
try:
    # Port might be /dev/ttyUSB0 or /dev/ttyACM0 on Raspberry Pi
    arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
    time.sleep(2) # Allow connection to stabilize
except Exception as e:
    print(f"\033[91m[ERROR] Arduino not found: {e}\033[0m")
    arduino = None

cloudinary.config( 
    cloud_name = "dei1fd8k6", 
    api_key = "545933773654545", 
    api_secret = "434wCTl3T4jlwQKpjiX8Rp2Bc6s" 
)

# Thresholds for analytics
EAR_THRESHOLD = 0.25
HEAD_YAW_LIMIT = 22
HEAD_PITCH_LIMIT = -15

# Global session variables
CURRENT_DRIVE_ID = None
video_out = None
eye_closed_frames = 0
total_frames_in_minute = 0

# =============================================================================
# LOGGING & CLOUD SYNC
# =============================================================================

def log_event(level, message):
    colors = {
        "INFO": "\033[92m",    # Green
        "DEBUG": "\033[94m",   # Blue
        "WARNING": "\033[93m", # Yellow (Distraction)
        "ERROR": "\033[91m",   # Red (Fatigue)
        "END": "\033[0m"       
    }
    color = colors.get(level, colors["END"])
    print(f"{color}[{level}] {time.strftime('%H:%M:%S')} - {message}{colors['END']}")

def finalize_session():
    global CURRENT_DRIVE_ID, video_out
    log_event("INFO", "Starting termination cleanup...")
    if video_out is not None: video_out.release()
    if CURRENT_DRIVE_ID is None: return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            log_event("INFO", "Uploading MP4 to Cloudinary...")
            res = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = res.get("secure_url")
            os.remove(VIDEO_TEMP_FILE)
            log_event("INFO", f"Video available at: {video_url}")
    except Exception as e:
        log_event("ERROR", f"Cloudinary failed: {e}")

    try:
        requests.post(f"{BASE_URL}/end_drive", json={"drive_id": CURRENT_DRIVE_ID, "video_url": video_url}, timeout=20)
        log_event("INFO", "Backend session closed.")
    except:
        log_event("ERROR", "Backend sync failed.")

atexit.register(finalize_session)

# =============================================================================
# ANALYTICS HELPERS
# =============================================================================

def get_ear(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
    model_points = np.array([(0.0, 0.0, 0.0), (0.0, -330.0, -65.0), (-225.0, 170.0, -135.0),
                             (225.0, 170.0, -135.0), (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0)], dtype="double")
    image_points = np.array([shape[30], shape[8], shape[36], shape[45], shape[48], shape[54]], dtype="double")
    camera_matrix = np.array([[img_w, 0, img_w/2], [0, img_w, img_h/2], [0, 0, 1]], dtype="double")
    _, rv, _ = cv2.solvePnP(model_points, image_points, camera_matrix, np.zeros((4, 1)))
    rmat, _ = cv2.Rodrigues(rv)
    yaw = np.degrees(np.arctan2(-rmat[2, 0], np.sqrt(rmat[0, 0]**2 + rmat[1, 0]**2)))
    pitch = np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2]))
    return yaw, pitch

# =============================================================================
# MAIN LOOP
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out, eye_closed_frames, total_frames_in_minute
    
    log_event("INFO", "Loading AI Models...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

    log_event("INFO", "Waiting for Driver Detection...")
    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        if len(detector(gray, 0)) > 0: break
        time.sleep(0.5)

    log_event("INFO", "Opening Session on Heroku...")
    resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID})
    CURRENT_DRIVE_ID = resp.json().get("drive_id")
    log_event("INFO", f"Drive #{CURRENT_DRIVE_ID} is LIVE.")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video_out = cv2.VideoWriter(VIDEO_TEMP_FILE, fourcc, 10.0, (640, 480))

    last_send = time.time()
    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            
            # --- Reset States ---
            is_distracted = len(rects) == 0
            is_fatigued = False
            ear, yaw, pitch = 0.0, 0.0, 0.0
            total_frames_in_minute += 1

            if not is_distracted:
                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                ear = (get_ear(shape[lS:lE]) + get_ear(shape[rS:rE])) / 2.0
                yaw, pitch = get_head_pose(shape, 480, 640)
                
                # Fatigue Analysis (Real-time PERCLOS)
                if ear < EAR_THRESHOLD: eye_closed_frames += 1
                perclos = (eye_closed_frames / total_frames_in_minute) * 100
                if perclos > 25: is_fatigued = True #
                
                # Distraction Analysis (Head Pose)
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT:
                    is_distracted = True

            # --- Visual & Arduino Feedback ---
            # Priority: Fatigue is higher priority for the buzzer
            if is_fatigued:
                box_color, box_label = (0, 0, 255), "CRITICAL FATIGUE!"
                if arduino: arduino.write(b'F') # Send 'F' to Arduino
            elif is_distracted:
                box_color, box_label = (0, 0, 255), "DISTRACTED!"
                if arduino: arduino.write(b'D') # Send 'D' to Arduino
            else:
                box_color, box_label = (0, 255, 0), "DRIVER FOCUSED"
                if arduino: arduino.write(b'O') # Send 'O' (OK) to Arduino

            for rect in rects:
                (x, y, w, h) = face_utils.rect_to_bb(rect)
                cv2.rectangle(frame, (x, y), (x + w, y + h), box_color, 2)
                cv2.putText(frame, box_label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

            video_out.write(frame)

            # Heartbeat - 1Hz
            if time.time() - last_send > 1.0:
                perclos = (eye_closed_frames / total_frames_in_minute) * 100
                payload = {
                    "drive_id": CURRENT_DRIVE_ID, "ear": round(ear, 2), 
                    "perclos": round(perclos, 2), "is_distracted": is_distracted,
                    "head_yaw": round(yaw, 2), "head_pitch": round(pitch, 2)
                }
                threading.Thread(target=lambda p: requests.post(f"{BASE_URL}/telemetry", json=p), args=(payload,)).start()
                
                # Color-coded Terminal Debug
                log_lvl = "ERROR" if is_fatigued else ("WARNING" if is_distracted else "DEBUG")
                log_msg = f"Sync: EAR={ear:.2f} | PERCLOS={perclos:.1f}% | Yaw={yaw:.1f} | Dist={is_distracted}"
                log_event(log_lvl, log_msg)
                last_send = time.time()

    except KeyboardInterrupt:
        log_event("INFO", "Stopped by user.")
    finally:
        cap.release()

if __name__ == "__main__":
    start_monitoring()
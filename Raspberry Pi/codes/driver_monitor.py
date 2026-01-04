"""
DRIVER MONITORING SYSTEM (CLIENT SIDE) - VERSION 3.0
---------------------------------------------------------------------------------------
Description:
    Captures video, detects face landmarks, draws bounding boxes, analyzes fatigue 
    (EAR/PERCLOS) and distraction (Head Pose), and syncs telemetry to a Flask backend.
---------------------------------------------------------------------------------------
"""

import cv2
import dlib
import numpy as np
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

# Cloudinary Setup for permanent video storage
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
    """ Custom logger for real-time debugging. """
    print(f"[{level}] {time.strftime('%H:%M:%S')} - {message}")

def finalize_session():
    """ 
    Triggered on script exit. Releases video resources and uploads 
    the recorded MP4 file to Cloudinary.
    """
    global CURRENT_DRIVE_ID, video_out
    log_event("INFO", "Starting termination cleanup...")
    
    if video_out is not None:
        video_out.release()
        log_event("DEBUG", "VideoWriter released.")
    
    if CURRENT_DRIVE_ID is None: return

    video_url = None
    try:
        if os.path.exists(VIDEO_TEMP_FILE):
            log_event("UPLOAD", "Uploading recorded session to Cloudinary...")
            res = cloudinary.uploader.upload(VIDEO_TEMP_FILE, resource_type="video")
            video_url = res.get("secure_url")
            os.remove(VIDEO_TEMP_FILE)
            log_event("SUCCESS", f"Video synced: {video_url}")
    except Exception as e:
        log_event("ERROR", f"Cloudinary upload failed: {e}")

    try:
        # Inform backend that the drive has ended and provide the video link
        requests.post(f"{BASE_URL}/end_drive", json={
            "drive_id": CURRENT_DRIVE_ID,
            "video_url": video_url
        }, timeout=20)
        log_event("SUCCESS", "Heroku session closed successfully.")
    except Exception as e:
        log_event("ERROR", f"Failed to notify backend: {e}")

atexit.register(finalize_session)

# =============================================================================
# COMPUTER VISION HELPERS
# =============================================================================

def get_ear(eye):
    """ Calculate Eye Aspect Ratio to detect blinks/closure. """
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def get_head_pose(shape, img_h, img_w):
    """ Estimate head orientation (Yaw/Pitch) using SolvePnP. """
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
# MAIN MONITORING LOOP
# =============================================================================

def start_monitoring():
    global CURRENT_DRIVE_ID, video_out, eye_closed_frames, total_frames_in_minute
    
    log_event("INFO", "Initializing AI Models and Video Stream...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

    # Phase 1: Standby - Wait for face detection to start the session
    log_event("INFO", "Standby Mode: Waiting for driver detection...")
    while True:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2GRAY)
        if len(detector(gray, 0)) > 0: 
            log_event("SUCCESS", "Driver recognized. Starting session.")
            break
        time.sleep(0.5)

    # Phase 2: Session Initiation
    try:
        resp = requests.post(f"{BASE_URL}/start_drive", json={"device_id": DEVICE_ID}, timeout=10)
        CURRENT_DRIVE_ID = resp.json().get("drive_id")
        log_event("SUCCESS", f"Live Session Started. ID: {CURRENT_DRIVE_ID}")
    except Exception as e:
        log_event("ERROR", f"Backend initialization failed: {e}")
        sys.exit(1)

    # Configure Video Writer (MP4 format for browser support)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video_out = cv2.VideoWriter(VIDEO_TEMP_FILE, fourcc, 10.0, (640, 480))

    last_send = time.time()
    (lS, lE) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (rS, rE) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

    # Phase 3: Real-time Analysis Loop
    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            
            is_distracted = len(rects) == 0
            ear, yaw, pitch = 0.0, 0.0, 0.0
            total_frames_in_minute += 1

            if not is_distracted:
                # DETECT FACE AND DRAW TRACKING BOX
                for rect in rects:
                    (x, y, w, h) = face_utils.rect_to_bb(rect)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "DRIVER DETECTED", (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Analyze landmarks
                shape = face_utils.shape_to_np(predictor(gray, rects[0]))
                ear = (get_ear(shape[lS:lE]) + get_ear(shape[rS:rE])) / 2.0
                yaw, pitch = get_head_pose(shape, 480, 640)
                
                # Monitor Fatigue
                if ear < EAR_THRESHOLD: eye_closed_frames += 1
                
                # Detect Distraction via Pose
                if abs(yaw) > HEAD_YAW_LIMIT or pitch < HEAD_PITCH_LIMIT:
                    is_distracted = True

            # Save the frame with the bounding box to the video file
            video_out.write(frame)

            # TRANSMIT TELEMETRY (1Hz Heartbeat)
            if time.time() - last_send > 1.0:
                perclos = (eye_closed_frames / total_frames_in_minute) * 100 if total_frames_in_minute > 0 else 0
                payload = {
                    "drive_id": CURRENT_DRIVE_ID, 
                    "ear": round(ear, 2), 
                    "perclos": round(perclos, 2),
                    "is_distracted": is_distracted,
                    "head_yaw": round(yaw, 2),
                    "head_pitch": round(pitch, 2)
                }
                # Async send to maintain FPS
                threading.Thread(target=lambda p: requests.post(f"{BASE_URL}/telemetry", json=p), args=(payload,)).start()
                log_event("DEBUG", f"Telemetry Synced | EAR: {ear:.2f} | Distracted: {is_distracted}")
                last_send = time.time()

    except KeyboardInterrupt:
        log_event("INFO", "Monitoring manually interrupted.")
    finally:
        cap.release()

if __name__ == "__main__":
    start_monitoring()